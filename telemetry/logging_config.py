"""
Hierarchical Log Management & Security Audit Logging for Mac-Control.

Log Levels:
- DEBUG: Low-level socket, regex, audio frame diagnostics.
- INFO: Normal system activity, command completions, state transitions.
- WARNING: SLA latency warnings (>1.5s), tier fallbacks, non-fatal errors.
- ERROR: Execution failures, model connection timeouts.
- SECURITY_AUDIT: Dedicated, tamper-evident security audit log for safety evaluations.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import contextvars
from typing import Optional

# Context variable for distributed trace correlation
current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_trace_id", default="-")

LOGS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "logs"
)
os.makedirs(LOGS_DIR, exist_ok=True)

APP_LOG_PATH = os.path.join(LOGS_DIR, "app.log")
SECURITY_AUDIT_LOG_PATH = os.path.join(LOGS_DIR, "security_audit.log")

class TraceContextFilter(logging.Filter):
    """Injects current_trace_id into all log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = current_trace_id.get()
        return True

def setup_logging(log_level: int = logging.INFO) -> None:
    """Configures application-wide hierarchical logging."""
    root_logger = logging.getLogger("mac_control")
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False

    # Clear existing handlers
    root_logger.handlers.clear()

    trace_filter = TraceContextFilter()

    # 1. Console Handler (Clean formatting)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(trace_id)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_fmt)
    console_handler.addFilter(trace_filter)
    root_logger.addHandler(console_handler)

    # 2. Application Rotating File Handler (10MB per file, 5 backups)
    app_file_handler = RotatingFileHandler(
        APP_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    app_file_handler.setLevel(logging.DEBUG)
    file_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | trace=%(trace_id)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    app_file_handler.setFormatter(file_fmt)
    app_file_handler.addFilter(trace_filter)
    root_logger.addHandler(app_file_handler)

    # 3. Dedicated Security Audit Logger
    security_logger = logging.getLogger("mac_control.security")
    security_logger.setLevel(logging.INFO)
    security_logger.propagate = False
    security_logger.handlers.clear()

    audit_file_handler = RotatingFileHandler(
        SECURITY_AUDIT_LOG_PATH, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    audit_file_handler.setLevel(logging.INFO)
    audit_fmt = logging.Formatter(
        "%(asctime)s | SECURITY_AUDIT | trace=%(trace_id)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    audit_file_handler.setFormatter(audit_fmt)
    audit_file_handler.addFilter(trace_filter)
    security_logger.addHandler(audit_file_handler)
    security_logger.addHandler(console_handler)

def get_logger(name: str = "mac_control") -> logging.Logger:
    """Returns a namespaced logger."""
    if not name.startswith("mac_control"):
        name = f"mac_control.{name}"
    return logging.getLogger(name)

def get_security_logger() -> logging.Logger:
    """Returns the dedicated security audit logger."""
    return logging.getLogger("mac_control.security")

# Initialize default logging on module import
setup_logging(log_level=logging.INFO)
