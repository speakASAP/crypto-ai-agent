import logging
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Avoid recursive external logging noise from the HTTP client used by the
# external logging handler itself.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Import external logging handler
try:
    from .logging_handler import ExternalLoggingHandler, SERVICE_NAME
except ImportError:
    try:
        from utils.logging_handler import ExternalLoggingHandler, SERVICE_NAME
    except ImportError:
        ExternalLoggingHandler = None
        SERVICE_NAME = "crypto-ai-agent"

# Check if logging is already configured
_logging_configured = False
_file_handler = None

def _setup_file_handler():
    """Setup file handler and ensure it's added to root logger"""
    global _file_handler
    
    # Check if file handler already exists
    if _file_handler is not None:
        return _file_handler
    
    # Check DEBUG flag from environment
    debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    
    # Determine log level based on DEBUG flag
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Get configuration from environment
    log_file = os.getenv("LOG_FILE", "logs/crypto_agent.log")
    log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Create logs directory if it doesn't exist
    log_dir = Path(log_file).parent if log_file else Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create file handler
    _file_handler = logging.FileHandler(log_file, encoding='utf-8')
    _file_handler.setLevel(log_level)
    _file_handler.setFormatter(logging.Formatter(log_format))
    
    return _file_handler

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with proper configuration based on DEBUG flag"""
    global _logging_configured
    
    logger = logging.getLogger(name)
    
    # Always ensure file handler is set up
    file_handler = _setup_file_handler()
    
    # Add file handler to root logger if not already present
    root_logger = logging.getLogger()
    if file_handler not in root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.setLevel(file_handler.level)
    
    # Add external logging handler if URL is configured and handler doesn't already exist
    logging_service_url = os.getenv("LOGGING_SERVICE_URL")
    if logging_service_url and ExternalLoggingHandler:
        # Check if external handler already exists
        has_external = any(
            isinstance(h, ExternalLoggingHandler) for h in root_logger.handlers
        )
        if not has_external:
            external_handler = ExternalLoggingHandler(service_name=SERVICE_NAME, service_url=logging_service_url)
            external_handler.setLevel(file_handler.level)
            root_logger.addHandler(external_handler)
    
    if not _logging_configured:
        # Check DEBUG flag from environment
        debug = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        
        # Determine log level based on DEBUG flag
        log_level = logging.DEBUG if debug else logging.INFO
        
        log_format = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        
        # Only add console handler if DEBUG is enabled and not already present
        if debug:
            # Check if StreamHandler already exists
            has_console = any(isinstance(h, logging.StreamHandler) and 
                            not isinstance(h, logging.FileHandler) 
                            for h in root_logger.handlers)
            
            if not has_console:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(log_level)
                console_handler.setFormatter(logging.Formatter(log_format))
                root_logger.addHandler(console_handler)
        
        _logging_configured = True
        logger.info(f"Logger initialized - Debug: {debug}, Level: {logging.getLevelName(log_level)}, File: {file_handler.baseFilename}")
    
    return logger
