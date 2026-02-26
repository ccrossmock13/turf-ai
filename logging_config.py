import json
import logging
import os
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
LOG_DIR = os.environ.get('LOG_DIR', 'logs')
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except OSError:
        LOG_DIR = '.'  # Fall back to current directory

# Log format with more detail for production debugging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# JSON structured formatter for production use
class JsonFormatter(logging.Formatter):
    """Outputs log records as single-line JSON objects."""

    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "lineno": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


# Create formatters
formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

# Console handler (always enabled)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# File handler with rotation (5MB max, keep 5 backups)
try:
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'greenside.log'),
        maxBytes=5*1024*1024,  # 5MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
except Exception:
    file_handler = None

# Error-only file handler for quick issue identification
try:
    error_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, 'errors.log'),
        maxBytes=2*1024*1024,  # 2MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
except Exception:
    error_handler = None

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(console_handler)
if file_handler:
    root_logger.addHandler(file_handler)
if error_handler:
    root_logger.addHandler(error_handler)

# Create app logger
logger = logging.getLogger('greenside')
logger.setLevel(logging.DEBUG)

# Reduce noise from third-party libraries
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('pinecone').setLevel(logging.WARNING)

# Switch all handlers to JSON formatter when LOG_FORMAT=json
if os.environ.get('LOG_FORMAT', 'text').lower() == 'json':
    json_formatter = JsonFormatter()
    console_handler.setFormatter(json_formatter)
    if file_handler:
        file_handler.setFormatter(json_formatter)
    if error_handler:
        error_handler.setFormatter(json_formatter)

# Log startup
logger.info("Greenside logging initialized")
