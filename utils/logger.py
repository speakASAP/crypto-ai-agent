"""
Centralized Logging System for Crypto AI Agent
Provides consistent logging across all project modules
"""

import os
import logging
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CentralLogger:
    """
    Centralized logging system for the entire crypto AI agent project.
    Provides consistent logging configuration and utilities across all modules.
    """
    
    _instance = None
    _logger = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CentralLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            self._initialized = True
    
    def _setup_logging(self):
        """Setup comprehensive logging configuration"""
        # Get configuration from environment variables with proper defaults
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_file = os.getenv("LOG_FILE", "logs/crypto_agent.log")
        log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format,
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()  # Also log to console
            ],
            force=True  # Override any existing configuration
        )
        
        # Create logger instance
        self._logger = logging.getLogger("crypto_ai_agent")
        
        # Log startup information
        self._logger.info("=" * 80)
        self._logger.info("CENTRAL LOGGING SYSTEM INITIALIZED")
        self._logger.info("=" * 80)
        self._logger.info(f"Log Level: {log_level}")
        self._logger.info(f"Log File: {log_file}")
        self._logger.info(f"Log Format: {log_format}")
        self._logger.info(f"Initialization Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    @property
    def logger(self):
        """Get the logger instance"""
        return self._logger
    
    def get_module_logger(self, module_name: str) -> logging.Logger:
        """Get a logger for a specific module"""
        return logging.getLogger(f"crypto_ai_agent.{module_name}")
    
    def log_function_entry(self, function_name: str, module_name: str, **kwargs):
        """Log function entry with parameters"""
        logger = self.get_module_logger(module_name)
        params = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.debug(f"ENTERING {function_name}({params})")
    
    def log_function_exit(self, function_name: str, module_name: str, result: Any = None):
        """Log function exit with result"""
        logger = self.get_module_logger(module_name)
        if result is not None:
            logger.debug(f"EXITING {function_name} -> {result}")
        else:
            logger.debug(f"EXITING {function_name}")
    
    def log_database_operation(self, operation: str, table: str, module_name: str, **kwargs):
        """Log database operations"""
        logger = self.get_module_logger(module_name)
        params = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.info(f"DB {operation.upper()} on {table} - {params}")
    
    def log_api_call(self, api_name: str, endpoint: str, module_name: str, status_code: Optional[int] = None):
        """Log API calls"""
        logger = self.get_module_logger(module_name)
        if status_code:
            logger.info(f"API {api_name} {endpoint} -> HTTP {status_code}")
        else:
            logger.info(f"API {api_name} {endpoint}")
    
    def log_performance(self, operation: str, duration: float, module_name: str, **kwargs):
        """Log performance metrics"""
        logger = self.get_module_logger(module_name)
        extra_info = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.info(f"PERFORMANCE {operation} took {duration:.3f}s - {extra_info}")
    
    def log_user_action(self, action: str, user_data: Dict[str, Any], module_name: str):
        """Log user actions"""
        logger = self.get_module_logger(module_name)
        user_info = ", ".join([f"{k}={v}" for k, v in user_data.items()])
        logger.info(f"USER ACTION {action} - {user_info}")
    
    def log_system_event(self, event: str, module_name: str, **kwargs):
        """Log system events"""
        logger = self.get_module_logger(module_name)
        extra_info = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.info(f"SYSTEM EVENT {event} - {extra_info}")
    
    def log_error_with_context(self, error: Exception, context: str, module_name: str, **kwargs):
        """Log errors with full context"""
        logger = self.get_module_logger(module_name)
        extra_info = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        
        logger.error(f"ERROR in {context} - {str(error)} - {extra_info}")
        logger.error(f"Traceback: {traceback.format_exc()}")
    
    def log_warning_with_context(self, message: str, context: str, module_name: str, **kwargs):
        """Log warnings with context"""
        logger = self.get_module_logger(module_name)
        extra_info = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.warning(f"WARNING in {context} - {message} - {extra_info}")
    
    def log_info_with_context(self, message: str, context: str, module_name: str, **kwargs):
        """Log info messages with context"""
        logger = self.get_module_logger(module_name)
        extra_info = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        logger.info(f"INFO in {context} - {message} - {extra_info}")

# Global logger instance
central_logger = CentralLogger()

# Convenience functions for easy access
def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for a specific module"""
    return central_logger.get_module_logger(module_name)

def log_function_entry(function_name: str, module_name: str, **kwargs):
    """Log function entry"""
    central_logger.log_function_entry(function_name, module_name, **kwargs)

def log_function_exit(function_name: str, module_name: str, result: Any = None):
    """Log function exit"""
    central_logger.log_function_exit(function_name, module_name, result)

def log_database_operation(operation: str, table: str, module_name: str, **kwargs):
    """Log database operation"""
    central_logger.log_database_operation(operation, table, module_name, **kwargs)

def log_api_call(api_name: str, endpoint: str, module_name: str, status_code: Optional[int] = None):
    """Log API call"""
    central_logger.log_api_call(api_name, endpoint, module_name, status_code)

def log_performance(operation: str, duration: float, module_name: str, **kwargs):
    """Log performance metric"""
    central_logger.log_performance(operation, duration, module_name, **kwargs)

def log_user_action(action: str, user_data: Dict[str, Any], module_name: str):
    """Log user action"""
    central_logger.log_user_action(action, user_data, module_name)

def log_system_event(event: str, module_name: str, **kwargs):
    """Log system event"""
    central_logger.log_system_event(event, module_name, **kwargs)

def log_error_with_context(error: Exception, context: str, module_name: str, **kwargs):
    """Log error with context"""
    central_logger.log_error_with_context(error, context, module_name, **kwargs)

def log_warning_with_context(message: str, context: str, module_name: str, **kwargs):
    """Log warning with context"""
    central_logger.log_warning_with_context(message, context, module_name, **kwargs)

def log_info_with_context(message: str, context: str, module_name: str, **kwargs):
    """Log info with context"""
    central_logger.log_info_with_context(message, context, module_name, **kwargs)

# Decorator for automatic function logging
def log_function_calls(module_name: str):
    """Decorator to automatically log function entry and exit"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            log_function_entry(func.__name__, module_name, **kwargs)
            try:
                result = func(*args, **kwargs)
                log_function_exit(func.__name__, module_name, result)
                return result
            except Exception as e:
                log_error_with_context(e, f"{func.__name__} execution", module_name)
                raise
        return wrapper
    return decorator

# Performance timing decorator
def log_performance_timing(operation_name: str, module_name: str):
    """Decorator to log function execution time"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            try:
                result = func(*args, **kwargs)
                duration = (datetime.now() - start_time).total_seconds()
                log_performance(operation_name, duration, module_name, function=func.__name__)
                return result
            except Exception as e:
                duration = (datetime.now() - start_time).total_seconds()
                log_performance(operation_name, duration, module_name, function=func.__name__, error=str(e))
                raise
        return wrapper
    return decorator