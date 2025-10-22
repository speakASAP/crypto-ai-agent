"""
Unit tests for Performance Monitor
"""
import pytest
import time
from unittest.mock import patch, MagicMock
from app.services.performance_monitor import PerformanceMonitor, monitor_performance


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor"""
    
    @pytest.fixture
    def monitor(self):
        """Create performance monitor instance for testing"""
        return PerformanceMonitor()
    
    def test_initialization(self, monitor):
        """Test performance monitor initialization"""
        assert monitor.monitoring_active is False
        assert monitor.metrics['api_calls'] == {}
        assert monitor.metrics['database_queries'] == {}
        assert monitor.metrics['cache_operations'] == {}
        assert monitor.metrics['websocket_connections'] == 0
        assert len(monitor.metrics['memory_usage']) == 0
        assert len(monitor.metrics['cpu_usage']) == 0
    
    def test_start_monitoring(self, monitor):
        """Test starting performance monitoring"""
        monitor.start_monitoring()
        assert monitor.monitoring_active is True
    
    def test_stop_monitoring(self, monitor):
        """Test stopping performance monitoring"""
        monitor.start_monitoring()
        monitor.stop_monitoring()
        assert monitor.monitoring_active is False
    
    def test_record_api_call(self, monitor):
        """Test recording API call metrics"""
        monitor.record_api_call("GET /test", "GET", 0.1, 200)
        
        assert "GET /test" in monitor.metrics['api_calls']
        assert len(monitor.metrics['api_calls']["GET /test"]) == 1
        
        call_data = monitor.metrics['api_calls']["GET /test"][0]
        assert call_data['response_time'] == 0.1
        assert call_data['status_code'] == 200
        assert 'timestamp' in call_data
    
    def test_record_api_call_error(self, monitor):
        """Test recording API call with error status"""
        monitor.record_api_call("POST /error", "POST", 0.5, 500)
        
        assert monitor.metrics['error_counts']["POST /error"] == 1
    
    def test_record_database_query(self, monitor):
        """Test recording database query metrics"""
        monitor.record_database_query("SELECT * FROM users", 0.05, 10)
        
        assert "SELECT * FROM users" in monitor.metrics['database_queries']
        assert len(monitor.metrics['database_queries']["SELECT * FROM users"]) == 1
        
        query_data = monitor.metrics['database_queries']["SELECT * FROM users"][0]
        assert query_data['execution_time'] == 0.05
        assert query_data['rows_affected'] == 10
        assert 'timestamp' in query_data
    
    def test_record_cache_operation(self, monitor):
        """Test recording cache operation metrics"""
        monitor.record_cache_operation("get", True, 0.01)
        
        assert "get" in monitor.metrics['cache_operations']
        assert len(monitor.metrics['cache_operations']["get"]) == 1
        
        cache_data = monitor.metrics['cache_operations']["get"][0]
        assert cache_data['hit'] is True
        assert cache_data['response_time'] == 0.01
        assert 'timestamp' in cache_data
    
    def test_record_websocket_connection(self, monitor):
        """Test recording WebSocket connection changes"""
        assert monitor.metrics['websocket_connections'] == 0
        
        monitor.record_websocket_connection(True)
        assert monitor.metrics['websocket_connections'] == 1
        
        monitor.record_websocket_connection(True)
        assert monitor.metrics['websocket_connections'] == 2
        
        monitor.record_websocket_connection(False)
        assert monitor.metrics['websocket_connections'] == 1
        
        monitor.record_websocket_connection(False)
        assert monitor.metrics['websocket_connections'] == 0
    
    def test_get_performance_summary(self, monitor):
        """Test getting performance summary"""
        # Add some test data
        monitor.record_api_call("GET /test", "GET", 0.1, 200)
        monitor.record_api_call("GET /test", "GET", 0.2, 200)
        monitor.record_database_query("SELECT * FROM users", 0.05, 10)
        monitor.record_cache_operation("get", True, 0.01)
        
        summary = monitor.get_performance_summary()
        
        assert 'uptime_seconds' in summary
        assert 'api_metrics' in summary
        assert 'database_metrics' in summary
        assert 'cache_metrics' in summary
        assert 'system_metrics' in summary
        assert 'total_errors' in summary
        
        # Check API metrics
        assert "GET /test" in summary['api_metrics']
        api_metrics = summary['api_metrics']["GET /test"]
        assert api_metrics['total_calls'] == 2
        assert api_metrics['avg_response_time'] == 0.15
        assert api_metrics['min_response_time'] == 0.1
        assert api_metrics['max_response_time'] == 0.2
        assert api_metrics['error_count'] == 0
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    def test_get_health_status_healthy(self, mock_cpu, mock_memory, monitor):
        """Test health status when system is healthy"""
        mock_memory.return_value.percent = 50.0
        mock_cpu.return_value = 30.0
        
        health = monitor.get_health_status()
        
        assert health['status'] == 'healthy'
        assert health['memory_usage_percent'] == 50.0
        assert health['cpu_usage_percent'] == 30.0
        assert len(health['warnings']) == 0
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    def test_get_health_status_warning(self, mock_cpu, mock_memory, monitor):
        """Test health status when system has warnings"""
        mock_memory.return_value.percent = 85.0
        mock_cpu.return_value = 85.0
        
        health = monitor.get_health_status()
        
        assert health['status'] == 'warning'
        assert len(health['warnings']) == 2
        assert any('memory' in warning.lower() for warning in health['warnings'])
        assert any('cpu' in warning.lower() for warning in health['warnings'])
    
    @patch('psutil.virtual_memory')
    @patch('psutil.cpu_percent')
    def test_get_health_status_critical(self, mock_cpu, mock_memory, monitor):
        """Test health status when system is critical"""
        mock_memory.return_value.percent = 95.0
        mock_cpu.return_value = 95.0
        
        health = monitor.get_health_status()
        
        assert health['status'] == 'critical'
        assert len(health['warnings']) == 2
    
    def test_reset_metrics(self, monitor):
        """Test resetting metrics"""
        # Add some test data
        monitor.record_api_call("GET /test", "GET", 0.1, 200)
        monitor.record_database_query("SELECT * FROM users", 0.05, 10)
        monitor.memory_usage.append({"timestamp": "2023-01-01", "used_mb": 100})
        
        monitor.reset_metrics()
        
        assert monitor.metrics['api_calls'] == {}
        assert monitor.metrics['database_queries'] == {}
        assert monitor.metrics['cache_operations'] == {}
        assert monitor.metrics['websocket_connections'] == 0
        assert len(monitor.metrics['memory_usage']) == 0
        assert len(monitor.metrics['cpu_usage']) == 0
        assert monitor.cache_stats['hits'] == 0
        assert monitor.cache_stats['misses'] == 0


class TestMonitorPerformanceDecorator:
    """Test cases for monitor_performance decorator"""
    
    def test_sync_function_monitoring(self):
        """Test monitoring synchronous function"""
        @monitor_performance("database", "test_query")
        def sync_function():
            time.sleep(0.01)
            return "result"
        
        result = sync_function()
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_async_function_monitoring(self):
        """Test monitoring asynchronous function"""
        @monitor_performance("database", "test_async_query")
        async def async_function():
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await async_function()
        assert result == "async_result"
    
    def test_function_with_exception(self):
        """Test monitoring function that raises exception"""
        @monitor_performance("database", "test_error_query")
        def error_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            error_function()
