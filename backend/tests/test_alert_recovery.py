"""
Tests for alert recovery system
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
import sqlite3
import tempfile
import os

# Import the functions we want to test
from backend.app.main import check_missed_alerts_on_startup, trigger_alert, get_db_connection
from backend.app.services.price_service import PriceService


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    # Create test database
    conn = sqlite3.connect(temp_file.name)
    cursor = conn.cursor()
    
    # Create necessary tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            threshold_price REAL NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_check_tracking (
            symbol TEXT PRIMARY KEY,
            last_check_timestamp TEXT NOT NULL,
            last_check_price REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            triggered_price REAL NOT NULL,
            triggered_at TEXT NOT NULL,
            was_missed BOOLEAN DEFAULT 0,
            check_type TEXT DEFAULT 'realtime'
        )
    ''')
    
    conn.commit()
    conn.close()
    
    yield temp_file.name
    
    # Cleanup
    os.unlink(temp_file.name)


@pytest.fixture
def mock_price_service():
    """Mock price service for testing"""
    service = Mock(spec=PriceService)
    service.get_historical_prices_for_range = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_missed_alert_detection(temp_db, mock_price_service):
    """Test that missed alerts are detected and triggered"""
    # Set up test data
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Insert test alert
    cursor.execute('''
        INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (1, 'BTC', 50000.0, 'ABOVE', 'Test alert', 1, ?)
    ''', (datetime.now(timezone.utc).isoformat() + "Z",))
    
    # Insert price tracking data (last check was 2 hours ago)
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    cursor.execute('''
        INSERT INTO price_check_tracking (symbol, last_check_timestamp, last_check_price, updated_at)
        VALUES ('BTC', ?, 45000.0, ?)
    ''', (two_hours_ago.isoformat() + "Z", two_hours_ago.isoformat() + "Z"))
    
    conn.commit()
    conn.close()
    
    # Mock historical price data that shows threshold was crossed
    mock_price_service.get_historical_prices_for_range.return_value = [
        {
            'timestamp': int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000),
            'high': 51000.0,  # Above threshold
            'low': 48000.0,
            'open': 49000.0,
            'close': 50000.0,
            'volume': 1000.0
        }
    ]
    
    # Mock the trigger_alert function
    with patch('backend.app.main.trigger_alert') as mock_trigger:
        with patch('backend.app.main.price_service', mock_price_service):
            with patch('backend.app.main.DB_FILE', temp_db):
                await check_missed_alerts_on_startup()
        
        # Verify that trigger_alert was called with correct parameters
        mock_trigger.assert_called_once()
        call_args = mock_trigger.call_args
        assert call_args[1]['symbol'] == 'BTC'
        assert call_args[1]['threshold_price'] == 50000.0
        assert call_args[1]['alert_type'] == 'ABOVE'
        assert call_args[1]['was_missed'] == True


@pytest.mark.asyncio
async def test_no_missed_alerts_when_threshold_not_crossed(temp_db, mock_price_service):
    """Test that no alerts are triggered when threshold wasn't crossed"""
    # Set up test data
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Insert test alert
    cursor.execute('''
        INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (1, 'BTC', 50000.0, 'ABOVE', 'Test alert', 1, ?)
    ''', (datetime.now(timezone.utc).isoformat() + "Z",))
    
    # Insert price tracking data
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    cursor.execute('''
        INSERT INTO price_check_tracking (symbol, last_check_timestamp, last_check_price, updated_at)
        VALUES ('BTC', ?, 45000.0, ?)
    ''', (two_hours_ago.isoformat() + "Z", two_hours_ago.isoformat() + "Z"))
    
    conn.commit()
    conn.close()
    
    # Mock historical price data that shows threshold was NOT crossed
    mock_price_service.get_historical_prices_for_range.return_value = [
        {
            'timestamp': int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000),
            'high': 49000.0,  # Below threshold
            'low': 48000.0,
            'open': 48500.0,
            'close': 48800.0,
            'volume': 1000.0
        }
    ]
    
    # Mock the trigger_alert function
    with patch('backend.app.main.trigger_alert') as mock_trigger:
        with patch('backend.app.main.price_service', mock_price_service):
            with patch('backend.app.main.DB_FILE', temp_db):
                await check_missed_alerts_on_startup()
        
        # Verify that trigger_alert was NOT called
        mock_trigger.assert_not_called()


@pytest.mark.asyncio
async def test_startup_recovery_with_multiple_alerts(temp_db, mock_price_service):
    """Test startup recovery process with multiple missed alerts"""
    # Set up test data
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Insert multiple test alerts
    alerts_data = [
        (1, 'BTC', 50000.0, 'ABOVE', 'BTC alert', 1),
        (1, 'ETH', 3000.0, 'BELOW', 'ETH alert', 1),
    ]
    
    for user_id, symbol, threshold_price, alert_type, message, is_active in alerts_data:
        cursor.execute('''
            INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, symbol, threshold_price, alert_type, message, is_active, 
              datetime.now(timezone.utc).isoformat() + "Z"))
    
    # Insert price tracking data for both symbols
    two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
    tracking_data = [
        ('BTC', two_hours_ago.isoformat() + "Z", 45000.0, two_hours_ago.isoformat() + "Z"),
        ('ETH', two_hours_ago.isoformat() + "Z", 3200.0, two_hours_ago.isoformat() + "Z"),
    ]
    
    for symbol, timestamp, price, updated_at in tracking_data:
        cursor.execute('''
            INSERT INTO price_check_tracking (symbol, last_check_timestamp, last_check_price, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (symbol, timestamp, price, updated_at))
    
    conn.commit()
    conn.close()
    
    # Mock historical price data for both symbols
    def mock_historical_prices(symbol, start_ms, end_ms):
        if symbol == 'BTC':
            return [{
                'timestamp': int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp() * 1000),
                'high': 51000.0,  # Above threshold
                'low': 48000.0,
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
    with patch('backend.app.main.trigger_alert') as mock_trigger:
        with patch('backend.app.main.price_service', mock_price_service):
            with patch('backend.app.main.DB_FILE', temp_db):
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
async def test_trigger_alert_function(temp_db):
    """Test the trigger_alert function"""
    # Set up test data
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    # Insert test alert
    cursor.execute('''
        INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (1, 'BTC', 50000.0, 'ABOVE', 'Test alert', 1, ?)
    ''', (datetime.now(timezone.utc).isoformat() + "Z",))
    
    conn.commit()
    conn.close()
    
    # Mock the notification functions
    with patch('backend.app.main.send_user_telegram_notification') as mock_telegram:
        with patch('backend.app.main.manager') as mock_manager:
            with patch('backend.app.main.DB_FILE', temp_db):
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
    
    # Verify that alert was deactivated
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM alerts WHERE id = 1")
    is_active = cursor.fetchone()[0]
    conn.close()
    
    assert is_active == 0
    
    # Verify that alert history was recorded
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT was_missed, check_type FROM alert_history WHERE alert_id = 1")
    history = cursor.fetchone()
    conn.close()
    
    assert history[0] == 1  # was_missed = True
    assert history[1] == 'historical'  # check_type = 'historical'


@pytest.mark.asyncio
async def test_no_alerts_to_check(temp_db):
    """Test startup recovery when there are no active alerts"""
    with patch('backend.app.main.DB_FILE', temp_db):
        # This should not raise any exceptions
        await check_missed_alerts_on_startup()


@pytest.mark.asyncio
async def test_no_price_tracking_data(temp_db):
    """Test startup recovery when there's no price tracking data"""
    # Set up test data with alert but no price tracking
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO alerts (user_id, symbol, threshold_price, alert_type, message, is_active, created_at)
        VALUES (1, 'BTC', 50000.0, 'ABOVE', 'Test alert', 1, ?)
    ''', (datetime.now(timezone.utc).isoformat() + "Z",))
    
    conn.commit()
    conn.close()
    
    with patch('backend.app.main.DB_FILE', temp_db):
        # This should not raise any exceptions and should skip the alert
        await check_missed_alerts_on_startup()


if __name__ == "__main__":
    pytest.main([__file__])
