"""
Performance Monitoring Service
"""
import time
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import psutil
import os

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """
    Performance monitoring service for tracking system metrics
    """
    
    def __init__(self):
        self.metrics = {
            'api_calls': defaultdict(list),
            'database_queries': defaultdict(list),
            'cache_operations': defaultdict(list),
            'websocket_connections': 0,
            'memory_usage': deque(maxlen=100),
            'cpu_usage': deque(maxlen=100),
            'response_times': defaultdict(list),
            'error_counts': defaultdict(int)
        }
        self.start_time = datetime.now()
        self.monitoring_active = False
    
    def start_monitoring(self):
        """Start performance monitoring"""
        self.monitoring_active = True
        asyncio.create_task(self._collect_system_metrics())
        logger.info("📊 Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring_active = False
        logger.info("📊 Performance monitoring stopped")
    
    async def _collect_system_metrics(self):
        """Collect system metrics periodically"""
        while self.monitoring_active:
            try:
                # Memory usage
                memory_info = psutil.virtual_memory()
                self.metrics['memory_usage'].append({
                    'timestamp': datetime.now().isoformat(),
                    'used_mb': memory_info.used / 1024 / 1024,
                    'available_mb': memory_info.available / 1024 / 1024,
                    'percent': memory_info.percent
                })
                
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self.metrics['cpu_usage'].append({
                    'timestamp': datetime.now().isoformat(),
                    'percent': cpu_percent
                })
                
                # Clean old metrics (keep last 100 entries)
                for key in ['api_calls', 'database_queries', 'cache_operations', 'response_times']:
                    if key in self.metrics:
                        for subkey in self.metrics[key]:
                            if len(self.metrics[key][subkey]) > 100:
                                self.metrics[key][subkey] = self.metrics[key][subkey][-100:]
                
                await asyncio.sleep(10)  # Collect every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Error collecting system metrics: {e}")
                await asyncio.sleep(10)
    
    def record_api_call(self, endpoint: str, method: str, response_time: float, status_code: int):
        """Record API call metrics"""
        self.metrics['api_calls'][f"{method} {endpoint}"].append({
            'timestamp': datetime.now().isoformat(),
            'response_time': response_time,
            'status_code': status_code
        })
        
        # Record response time
        self.metrics['response_times'][f"{method} {endpoint}"].append(response_time)
        
        # Record errors
        if status_code >= 400:
            self.metrics['error_counts'][f"{method} {endpoint}"] += 1
    
    def record_database_query(self, query_type: str, execution_time: float, rows_affected: int = 0):
        """Record database query metrics"""
        self.metrics['database_queries'][query_type].append({
            'timestamp': datetime.now().isoformat(),
            'execution_time': execution_time,
            'rows_affected': rows_affected
        })
    
    def record_cache_operation(self, operation: str, hit: bool, response_time: float):
        """Record cache operation metrics"""
        self.metrics['cache_operations'][operation].append({
            'timestamp': datetime.now().isoformat(),
            'hit': hit,
            'response_time': response_time
        })
    
    def record_websocket_connection(self, connected: bool):
        """Record WebSocket connection changes"""
        if connected:
            self.metrics['websocket_connections'] += 1
        else:
            self.metrics['websocket_connections'] = max(0, self.metrics['websocket_connections'] - 1)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        uptime = datetime.now() - self.start_time
        
        # Calculate API metrics
        api_summary = {}
        for endpoint, calls in self.metrics['api_calls'].items():
            if calls:
                response_times = [call['response_time'] for call in calls]
                api_summary[endpoint] = {
                    'total_calls': len(calls),
                    'avg_response_time': sum(response_times) / len(response_times),
                    'min_response_time': min(response_times),
                    'max_response_time': max(response_times),
                    'error_count': self.metrics['error_counts'].get(endpoint, 0)
                }
        
        # Calculate database metrics
        db_summary = {}
        for query_type, queries in self.metrics['database_queries'].items():
            if queries:
                execution_times = [query['execution_time'] for query in queries]
                db_summary[query_type] = {
                    'total_queries': len(queries),
                    'avg_execution_time': sum(execution_times) / len(execution_times),
                    'min_execution_time': min(execution_times),
                    'max_execution_time': max(execution_times)
                }
        
        # Calculate cache metrics
        cache_summary = {}
        for operation, ops in self.metrics['cache_operations'].items():
            if ops:
                hits = sum(1 for op in ops if op['hit'])
                total = len(ops)
                response_times = [op['response_time'] for op in ops]
                cache_summary[operation] = {
                    'total_operations': total,
                    'hit_rate': (hits / total * 100) if total > 0 else 0,
                    'avg_response_time': sum(response_times) / len(response_times) if response_times else 0
                }
        
        # Get current system metrics
        current_memory = self.metrics['memory_usage'][-1] if self.metrics['memory_usage'] else {}
        current_cpu = self.metrics['cpu_usage'][-1] if self.metrics['cpu_usage'] else {}
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'uptime_human': str(uptime),
            'api_metrics': api_summary,
            'database_metrics': db_summary,
            'cache_metrics': cache_summary,
            'websocket_connections': self.metrics['websocket_connections'],
            'system_metrics': {
                'memory_usage_mb': current_memory.get('used_mb', 0),
                'memory_percent': current_memory.get('percent', 0),
                'cpu_percent': current_cpu.get('percent', 0)
            },
            'total_errors': sum(self.metrics['error_counts'].values())
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status"""
        current_memory = self.metrics['memory_usage'][-1] if self.metrics['memory_usage'] else {}
        current_cpu = self.metrics['cpu_usage'][-1] if self.metrics['cpu_usage'] else {}
        
        # Health checks
        memory_usage = current_memory.get('percent', 0)
        cpu_usage = current_cpu.get('percent', 0)
        total_errors = sum(self.metrics['error_counts'].values())
        
        health_status = "healthy"
        warnings = []
        
        if memory_usage > 90:
            health_status = "critical"
            warnings.append(f"High memory usage: {memory_usage:.1f}%")
        elif memory_usage > 80:
            health_status = "warning"
            warnings.append(f"Elevated memory usage: {memory_usage:.1f}%")
        
        if cpu_usage > 90:
            health_status = "critical"
            warnings.append(f"High CPU usage: {cpu_usage:.1f}%")
        elif cpu_usage > 80:
            health_status = "warning"
            warnings.append(f"Elevated CPU usage: {cpu_usage:.1f}%")
        
        if total_errors > 100:
            health_status = "warning"
            warnings.append(f"High error count: {total_errors}")
        
        return {
            'status': health_status,
            'warnings': warnings,
            'memory_usage_percent': memory_usage,
            'cpu_usage_percent': cpu_usage,
            'total_errors': total_errors,
            'websocket_connections': self.metrics['websocket_connections']
        }
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = {
            'api_calls': defaultdict(list),
            'database_queries': defaultdict(list),
            'cache_operations': defaultdict(list),
            'websocket_connections': 0,
            'memory_usage': deque(maxlen=100),
            'cpu_usage': deque(maxlen=100),
            'response_times': defaultdict(list),
            'error_counts': defaultdict(int)
        }
        self.start_time = datetime.now()
        logger.info("📊 Performance metrics reset")

# Global performance monitor instance
performance_monitor = PerformanceMonitor()

# Decorator for monitoring function execution time
def monitor_performance(operation_type: str, operation_name: str = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                performance_monitor.record_database_query(
                    operation_name or func.__name__,
                    execution_time
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.record_database_query(
                    operation_name or func.__name__,
                    execution_time
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                performance_monitor.record_database_query(
                    operation_name or func.__name__,
                    execution_time
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.record_database_query(
                    operation_name or func.__name__,
                    execution_time
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
