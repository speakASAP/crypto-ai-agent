"""
Tests for alert recovery system
NOTE: These tests require PostgreSQL test database setup.
For now, they use mocking to test the alert recovery logic.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import psycopg

# Import the functions we want to test
from backend.app.services.notification_service import check_missed_alerts_on_startup, trigger_alert
from backend.app.services.price_service import PriceService


@pytest.fixture
def mock_db_connection():
    """Mock PostgreSQL database connection for testing"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def mock_price_service():
    """Mock price service for testing"""
    service = Mock(spec=PriceService)
    service.get_historical_prices_for_range = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_missed_alert_detection(mock_db_connection, mock_price_service):
    """Test that missed alerts are detected and triggered"""
    conn, cursor = mock_db_connection
    
    # Mock database queries
    cursor.fetchall.return_value = [
        (1, 1, 'BTC', 50000.0, 'ABOVE', 'Test alert', True, datetime.now(timezone.utc).isoformat() + "Z")
    ]
    
    # Mock price tracking query
    def mock_execute(query, params=None):
        if 'price_check_tracking' in query:
            cursor.fetchone.return_value = (
                'BTC',
                (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() + "Z",
                45000.0,
                (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() + "Z"
            )
    
    cursor.execute.side_effect = mock_execute
    
    # Mock historical price data that shows threshold was crossed
    mock_price_service.get_historical_prices_for_range.return_value = [
        {
            'timestamp': int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000),
            'high': 51000.0,  # Above threshold
            'low': 48100.0,
            'open': 49000.0,
            'close': 50000.0,
            'volume': 1000.0
        }
    ]
    
    # Mock the trigger_alert function and database connection
    with patch('backend.app.services.notification_service.trigger_alert') as mock_trigger:
        with patch('backend.app.services.notification_service.price_service', mock_price_service):
            with patch('backend.app.dependencies.auth.get_db_connection', return_value=conn):
                await check_missed_alerts_on_startup()
        
        # Verify that trigger_alert was called with correct parameters
        mock_trigger.assert_called_once()
        call_args = mock_trigger.call_args
        assert call_args[1]['symbol'] == 'BTC'
        assert call_args[1]['threshold_price'] == 50000.0
        assert call_args[1]['alert_type'] == 'ABOVE'
        assert call_args[1]['was_missed'] == True


@pytest.mark.asyncio
async def test_no_missed_alerts_when_threshold_not_crossed(mock_db_connection, mock_price_service):
    """Test that no alerts are triggered when threshold wasn't crossed"""
    conn, cursor = mock_db_connection
    
    # Mock no active alerts
    cursor.fetchall.return_value = []
    
    # Mock the trigger_alert function
    with patch('backend.app.services.notification_service.trigger_alert') as mock_trigger:
        with patch('backend.app.services.notification_service.price_service', mock_price_service):
            with patch('backend.app.dependencies.auth.get_db_connection', return_value=conn):
                await check_missed_alerts_on_startup()
        
        # Verify that trigger_alert was NOT called
        mock_trigger.assert_not_called()


@pytest.mark.asyncio
async def test_startup_recovery_with_multiple_alerts(mock_db_connection, mock_price_service):
    """Test startup recovery process with multiple missed alerts"""
    conn, cursor = mock_db_connection
    
    # Mock multiple alerts
    cursor.fetchall.return_value = [
        (1, 1, 'BTC', 50000.0, 'ABOVE', 'BTC alert', True, datetime.now(timezone.utc).isoformat() + "Z"),
        (2, 1, 'ETH', 3000.0, 'BELOW', 'ETH alert', True, datetime.now(timezone.utc).isoformat() + "Z"),
    ]
    
    # Mock price tracking queries
    def mock_execute(query, params=None):
        if 'price_check_tracking' in query:
            if 'BTC' in str(params):
                cursor.fetchone.return_value = (
                    'BTC',
                    (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() + "Z",
                    45000.0,
                    (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() + "Z"
                )
            elif 'ETH' in str(params):
                cursor.fetchone.return_value = (
                    'ETH',
                    (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() + "Z",
                    3200.0,
                    (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat() + "Z"
                )
    
    cursor.execute.side_effect = mock_execute
    
    # Mock historical price data for both symbols
    def mock_historical_prices(symbol, start_ms, end_ms):
        if symbol == 'BTC':
            return [{
                'timestamp': int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000),
                'high': 51000.0,  # Above threshold
                'low': 48100.0,
                'open': 49000.0,
                'close': 50000.0,
                'volume': 1000.0
            }]
        elif symbol == 'ETH':
            return [{
                'timestamp': int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000),
                'high': 3100.0,
                'low': 2900.0,  # Below threshold
                'open': 3000.0,
                'close': 2950.0,
                'volume': 1000.0
            }]
        return []
    
    mock_price_service.get_historical_prices_for_range.side_effect = mock_historical_prices
    
    # Mock the trigger_alert function
    with patch('backend.app.services.notification_service.trigger_alert') as mock_trigger:
        with patch('backend.app.services.notification_service.price_service', mock_price_service):
            with patch('backend.app.dependencies.auth.get_db_connection', return_value=conn):
                await check_missed_alerts_on_startup()
        
        # Verify that trigger_alert was called twice (once for each alert)
        assert mock_trigger.call_count == 2
        
        # Check that both alerts were triggered with was_missed=True
        calls = mock_trigger.call_args_list
        symbols_triggered = [call[1]['symbol'] for call in calls]
        assert 'BTC' in symbols_triggered
        assert 'ETH' in symbols_triggered
        
        for call in calls:
            assert call[1]['was_missed'] == True


@pytest.mark.asyncio
async def test_trigger_alert_function(mock_db_connection):
    """Test the trigger_alert function"""
    conn, cursor = mock_db_connection
    
    # Mock database queries
    cursor.fetchone.return_value = (1,)
    cursor.rowcount = 1
    
    # Mock the notification functions
    with patch('backend.app.services.notification_service.send_user_telegram_notification') as mock_telegram:
        with patch('backend.app.api.ws.manager') as mock_manager:
            with patch('backend.app.dependencies.auth.get_db_connection', return_value=conn):
                trigger_time = datetime.now(timezone.utc)
                await trigger_alert(
                    alert_id=1,
                    user_id=1,
                    symbol='BTC',
                    threshold_price=50000.0,
                    alert_type='ABOVE',
                    message='Test alert',
                    trigger_price=51000.0,
                    trigger_time=trigger_time,
                    was_missed=True
                )
    
    # Verify that alert deactivation was attempted
    assert cursor.execute.called


@pytest.mark.asyncio
async def test_no_alerts_to_check(mock_db_connection):
    """Test startup recovery when there are no active alerts"""
    conn, cursor = mock_db_connection
    cursor.fetchall.return_value = []
    
    with patch('backend.app.dependencies.auth.get_db_connection', return_value=conn):
        # This should not raise any exceptions
        await check_missed_alerts_on_startup()


@pytest.mark.asyncio
async def test_no_price_tracking_data(mock_db_connection):
    """Test startup recovery when there's no price tracking data"""
    conn, cursor = mock_db_connection
    
    # Mock alert exists but no price tracking
    cursor.fetchall.return_value = [
        (1, 1, 'BTC', 50000.0, 'ABOVE', 'Test alert', True, datetime.now(timezone.utc).isoformat() + "Z")
    ]
    cursor.fetchone.return_value = None  # No price tracking data
    
    with patch('backend.app.dependencies.auth.get_db_connection', return_value=conn):
        # This should not raise any exceptions and should skip the alert
        await check_missed_alerts_on_startup()


if __name__ == "__main__":
    pytest.main([__file__])
