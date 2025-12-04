"""
External Logging Handler for Crypto AI Agent
Sends logs to external logging microservice while maintaining local file logging
"""

import logging
import httpx
import threading
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Service name constant
SERVICE_NAME = "crypto-ai-agent"


class ExternalLoggingHandler(logging.Handler):
    """
    Custom logging handler that sends logs to external logging microservice.
    Uses threading for non-blocking HTTP requests.
    Always falls back to local file logging if external service is unavailable.
    """

    def __init__(self, service_name: str = SERVICE_NAME, service_url: Optional[str] = None):
        """
        Initialize the external logging handler.

        Args:
            service_name: Name of the service sending logs (default: crypto-ai-agent)
            service_url: URL of the logging microservice (e.g., http://logging-microservice:${PORT:-3367}/api/logs, port configured in logging-microservice/.env)
        """
        super().__init__()
        self.service_name = service_name
        self.service_url = service_url or os.getenv("LOGGING_SERVICE_URL")
        self.timeout = 2.0  # 2 second timeout for HTTP requests

    def _map_log_level(self, level: int) -> str:
        """
        Map Python logging levels to microservice log levels.

        Args:
            level: Python logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Returns:
            Microservice log level (debug, info, warn, error)
        """
        level_mapping = {
            logging.DEBUG: "debug",
            logging.INFO: "info",
            logging.WARNING: "warn",
            logging.ERROR: "error",
            logging.CRITICAL: "error",
        }
        return level_mapping.get(level, "info")

    def _extract_metadata(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Extract metadata from log record including context, stack traces, etc.

        Args:
            record: Log record from Python logging

        Returns:
            Dictionary containing metadata
        """
        metadata: Dict[str, Any] = {}

        # Extract module, function, and line information
        if hasattr(record, "module"):
            metadata["module"] = record.module
        if hasattr(record, "funcName"):
            metadata["function"] = record.funcName
        if hasattr(record, "lineno"):
            metadata["line"] = record.lineno
        if hasattr(record, "pathname"):
            metadata["pathname"] = record.pathname

        # Extract stack trace if available
        if record.exc_info:
            metadata["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))

        # Extract any additional context from record
        if hasattr(record, "context"):
            metadata["context"] = record.context

        # Extract any additional metadata from record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]:
                metadata[key] = value

        return metadata

    def _format_log_payload(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Format log record into JSON payload for external service.

        Args:
            record: Log record from Python logging

        Returns:
            Dictionary containing formatted log payload
        """
        # Format message
        message = self.format(record)

        # Map log level
        level = self._map_log_level(record.levelno)

        # Extract metadata
        metadata = self._extract_metadata(record)

        # Create payload
        payload = {
            "level": level,
            "message": message,
            "service": self.service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "metadata": metadata,
        }

        return payload

    def _send_log(self, record: logging.LogRecord) -> None:
        """
        Send log to external service via HTTP POST.
        Silently fails if service is unavailable (fallback to local logging only).

        Args:
            record: Log record from Python logging
        """
        if not self.service_url:
            return

        try:
            payload = self._format_log_payload(record)

            # Send HTTP POST request with timeout
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.service_url}/api/logs",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                # Check response status (but don't log errors - avoid infinite loops)
                if response.status_code not in [200, 201]:
                    # Silently fail - fallback to local logging only
                    pass
        except Exception:
            # Silently fail - fallback to local logging only
            # Do not log errors about logging service (avoid infinite loops)
            pass

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.
        Always logs locally first, then sends to external service in background thread.

        Args:
            record: Log record from Python logging
        """
        # Always log locally first (this is handled by other handlers)
        # Then send to external service in background thread (non-blocking)
        if self.service_url:
            thread = threading.Thread(target=self._send_log, args=(record,))
            thread.daemon = True
            thread.start()
