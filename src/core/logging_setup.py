"""
Logging Setup

Configures logging based on app config.
"""
import logging
import sys
from pathlib import Path
from pythonjsonlogger import jsonlogger


def setup_logging(config):
    """
    Setup logging configuration.

    Args:
        config: Config object with logging settings
    """
    log_level = config.get('logging.level', 'INFO')
    log_format = config.get('logging.format', 'standard')
    log_file = config.get('logging.file', 'logs/icarus.log')

    # Create logs directory
    Path(log_file).parent.mkdir(exist_ok=True)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, log_level))

    # Format
    if log_format == 'json':
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={'timestamp': '@timestamp', 'level': 'severity'}
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Logging configured successfully")
