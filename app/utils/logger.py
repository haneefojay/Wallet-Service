import logging
import sys
from typing import Any
import json
from datetime import datetime


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "transaction_id"):
            log_data["transaction_id"] = record.transaction_id
        if hasattr(record, "amount"):
            log_data["amount"] = record.amount
        if hasattr(record, "reference"):
            log_data["reference"] = record.reference
        if hasattr(record, "event"):
            log_data["event"] = record.event
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def setup_logger(name: str = "wallet_service") -> logging.Logger:
    """Setup application logger with JSON formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger


# Global logger instance
logger = setup_logger()
