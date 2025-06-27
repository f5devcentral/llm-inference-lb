"""
Log utility module
Implements scheduler logging functionality with support for different log levels
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    
    @classmethod
    def from_string(cls, level_str: str) -> 'LogLevel':
        """Convert from string to log level"""
        level_str = level_str.upper().strip()
        for level in cls:
            if level.value == level_str:
                return level
        # Support common aliases
        level_map = {
            'WARN': cls.WARNING,
            'FATAL': cls.CRITICAL,
            'CRIT': cls.CRITICAL
        }
        return level_map.get(level_str, cls.INFO)
    
    def to_logging_level(self) -> int:
        """Convert to Python logging module level"""
        level_map = {
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL
        }
        return level_map[self]


class SchedulerLogger:
    """Scheduler log manager"""
    
    def __init__(self, log_level: LogLevel = LogLevel.INFO, log_file: Optional[str] = None):
        self.log_level = log_level
        self.log_file = log_file or "scheduler.log"
        self.logger = None
        # Maintain backward compatibility
        self.debug_enabled = (log_level == LogLevel.DEBUG)
        # Support stdout-only logging for containers
        # Check if we should use stdout-only mode (when log_file is explicitly set to empty string)
        self.stdout_only = log_file == ""
        self.setup_logger()
    
    def setup_logger(self):
        """Setup logger"""
        # Create logger
        self.logger = logging.getLogger("scheduler")
        self.logger.setLevel(self.log_level.to_logging_level())
        
        # Clear existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level.to_logging_level())
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (only if not stdout-only mode)
        if not self.stdout_only:
            try:
                file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
                # Use the same log level as configured for consistency
                file_handler.setLevel(self.log_level.to_logging_level())
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            except Exception as e:
                self.logger.warning(f"Unable to create log file {self.log_file}: {e}")
    
    def _update_handler_levels(self):
        """Update log levels for all handlers"""
        if not self.logger:
            return
        
        # Update logger level
        self.logger.setLevel(self.log_level.to_logging_level())
        
        # Update all handler levels
        for handler in self.logger.handlers:
            # Both console and file handlers use the same configured log level
            handler.setLevel(self.log_level.to_logging_level())
    
    def set_log_level(self, log_level: LogLevel):
        """Dynamically set log level"""
        self.log_level = log_level
        self.debug_enabled = (log_level == LogLevel.DEBUG)
        self._update_handler_levels()
    
    def set_debug_mode(self, debug: bool):
        """Dynamically set debug mode (backward compatibility)"""
        self.log_level = LogLevel.DEBUG if debug else LogLevel.INFO
        self.debug_enabled = debug
        self._update_handler_levels()
    
    def debug(self, message: str):
        """Debug level log"""
        if self.logger:
            self.logger.debug(message)
    
    def info(self, message: str):
        """Info level log"""
        if self.logger:
            self.logger.info(message)
    
    def warning(self, message: str):
        """Warning level log"""
        if self.logger:
            self.logger.warning(message)
    
    def error(self, message: str):
        """Error level log"""
        if self.logger:
            self.logger.error(message)
    
    def critical(self, message: str):
        """Critical level log"""
        if self.logger:
            self.logger.critical(message)


# Global logger instance
_logger_instance: Optional[SchedulerLogger] = None


def get_logger() -> SchedulerLogger:
    """Get logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SchedulerLogger()
    return _logger_instance


def init_logger(debug: bool = False, log_file: Optional[str] = None, log_level: Optional[str] = None) -> SchedulerLogger:
    """
    Initialize logger
    
    Args:
        debug: Backward compatible debug switch
        log_file: Log file path
        log_level: Log level string (e.g. "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    """
    global _logger_instance
    
    # Determine log level
    if log_level:
        # If log level is explicitly specified, use the specified level
        level = LogLevel.from_string(log_level)
    elif debug:
        # If debug=True, set to DEBUG level
        level = LogLevel.DEBUG
    else:
        # Default to INFO level
        level = LogLevel.INFO
    
    if _logger_instance is None:
        _logger_instance = SchedulerLogger(log_level=level, log_file=log_file)
    else:
        # If logger already exists, check if we need to update settings
        need_reinit = False
        
        # Check if log level changed
        if _logger_instance.log_level != level:
            _logger_instance.set_log_level(level)
        
        # Check if log file path changed
        if log_file != _logger_instance.log_file:
            _logger_instance.log_file = log_file or "scheduler.log"
            _logger_instance.stdout_only = log_file == ""
            need_reinit = True
        
        # If file path changed, reinitialize the logger handlers
        if need_reinit:
            _logger_instance.setup_logger()
    
    return _logger_instance 