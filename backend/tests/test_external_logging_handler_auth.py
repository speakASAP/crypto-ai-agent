import importlib.util
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch


MODULE_PATH = Path(__file__).resolve().parents[2] / "utils" / "logging_handler.py"


def load_handler_module():
    spec = importlib.util.spec_from_file_location("logging_handler", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_record():
    return logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="central auth smoke",
        args=(),
        exc_info=None,
    )


def test_external_logging_handler_adds_auth_header_when_token_is_set(monkeypatch):
    monkeypatch.setenv("LOGGING_SERVICE_TOKEN", "unit-token")
    module = load_handler_module()
    handler = module.ExternalLoggingHandler(service_url="http://logging-microservice:3367")
    client = MagicMock()
    client.post.return_value.status_code = 201

    with patch.object(module.httpx, "Client") as client_factory:
        client_factory.return_value.__enter__.return_value = client
        handler._send_log(make_record())

    headers = client.post.call_args.kwargs["headers"]
    assert headers["Content-Type"] == "application/json"
    assert headers["Authorization"] == "Bearer unit-token"


def test_external_logging_handler_omits_auth_header_when_token_is_unset(monkeypatch):
    monkeypatch.delenv("LOGGING_SERVICE_TOKEN", raising=False)
    module = load_handler_module()
    handler = module.ExternalLoggingHandler(service_url="http://logging-microservice:3367")
    client = MagicMock()
    client.post.return_value.status_code = 201

    with patch.object(module.httpx, "Client") as client_factory:
        client_factory.return_value.__enter__.return_value = client
        handler._send_log(make_record())

    headers = client.post.call_args.kwargs["headers"]
    assert headers["Content-Type"] == "application/json"
    assert "Authorization" not in headers
