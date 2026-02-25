"""
Sam Logging Utility
Centralized logging configuration for all Sam components
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Create logs directory
LOG_DIR = Path(__file__).parent
LOG_DIR.mkdir(exist_ok=True)

class ColoredFormatter(logging.Formatter):
    """Custom formatter with color coding for different log levels"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # Add color to levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        
        return super().format(record)

class SamLogger:
    """Centralized logger for Sam components"""
    
    _loggers = {}
    _initialized = False
    
    @classmethod
    def cleanup_old_logs(cls, max_files=5):
        """Keep only the most recent log files"""
        try:
            log_files = list(LOG_DIR.glob("sam_*.log"))
            if len(log_files) > max_files:
                # Sort by creation time, keep newest
                log_files.sort(key=lambda f: f.stat().st_ctime, reverse=True)
                for old_file in log_files[max_files:]:
                    old_file.unlink()
                    # Silently cleanup old logs
        except Exception as e:
            pass  # Silently fail on cleanup errors
    
    @classmethod
    def setup(cls, level=logging.INFO, console_level=logging.INFO):
        """Initialize logging system once"""
        if cls._initialized:
            return
        
        # Create log files with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Main log file (everything)
        main_log_file = LOG_DIR / f"sam_main_{timestamp}.log"
        
        # Component-specific log files
        component_log_file = LOG_DIR / f"sam_components_{timestamp}.log"
        error_log_file = LOG_DIR / f"sam_errors_{timestamp}.log"
        
        # Root logger configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        root_logger.handlers = []
        
        # Console handler with minimal output (user/sam interactions only)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_level)
        console_formatter = ColoredFormatter(
            '%(message)s'  # Simple format for console
        )
        console_handler.setFormatter(console_formatter)
        
        # Add filter to only show specific messages on console
        class ConsoleFilter(logging.Filter):
            def filter(self, record):
                # Only show user input, Sam responses, and critical errors
                message = record.getMessage()
                return any([
                    'You:' in message,
                    'Sam:' in message, 
                    '🎙' in message,
                    record.levelno >= logging.ERROR
                ])
        
        console_handler.addFilter(ConsoleFilter())
        root_logger.addHandler(console_handler)
        
        # Main file handler (all logs)
        file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s │ %(name)-15s │ %(levelname)-8s │ %(funcName)-20s │ %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
        
        # Component file handler (INFO and above)
        component_handler = logging.FileHandler(component_log_file, encoding='utf-8')
        component_handler.setLevel(logging.INFO)
        component_handler.setFormatter(file_formatter)
        root_logger.addHandler(component_handler)
        
        # Error file handler (WARNING and above)
        error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)
        
        cls._initialized = True
        
        # Clean up old logs
        cls.cleanup_old_logs()
        
        # Log initialization
        init_logger = cls.get_logger("INIT")
        init_logger.info("Sam logging system initialized")
        init_logger.info(f"Main log: {main_log_file}")
        init_logger.info(f"Components log: {component_log_file}")
        init_logger.info(f"Errors log: {error_log_file}")
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """Get or create a logger for a specific component"""
        if not cls._initialized:
            cls.setup()
        
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = logger
        
        return cls._loggers[name]

# Convenience functions for common logging patterns
def get_logger(component_name: str) -> logging.Logger:
    """Get a logger for a component"""
    return SamLogger.get_logger(component_name)

def log_function_entry(logger: logging.Logger, func_name: str, **kwargs):
    """Log function entry with parameters"""
    if kwargs:
        params = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        logger.debug(f"→ {func_name}({params})")
    else:
        logger.debug(f"→ {func_name}()")

def log_function_exit(logger: logging.Logger, func_name: str, result=None):
    """Log function exit with result"""
    if result is not None:
        logger.debug(f"← {func_name}() → {result}")
    else:
        logger.debug(f"← {func_name}()")

def log_error(logger: logging.Logger, func_name: str, error: Exception):
    """Log error with context"""
    logger.error(f"✗ {func_name}() failed: {type(error).__name__}: {error}")

def log_performance(logger: logging.Logger, operation: str, duration: float):
    """Log performance metrics"""
    logger.info(f"⏱️ {operation} took {duration:.2f}s")

def log_state_change(logger: logging.Logger, old_state, new_state):
    """Log state transitions"""
    logger.info(f"🔄 State: {old_state} → {new_state}")

def log_api_call(logger: logging.Logger, api_name: str, status_code: int = None, duration: float = None):
    """Log API calls"""
    if status_code and duration:
        logger.info(f"🌐 {api_name} API: {status_code} ({duration:.2f}s)")
    elif status_code:
        logger.info(f"🌐 {api_name} API: {status_code}")
    else:
        logger.info(f"🌐 {api_name} API call started")

# Initialize logging when module is imported
def init_logging(level=logging.INFO, console_level=logging.INFO):
    """Initialize the logging system"""
    SamLogger.setup(level, console_level)

# Auto-initialize with environment variable support
if __name__ != "__main__":
    log_level_str = os.getenv('SAM_LOG_LEVEL', 'INFO').upper()
    console_level_str = os.getenv('SAM_CONSOLE_LOG_LEVEL', 'INFO').upper()
    
    level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    log_level = level_map.get(log_level_str, logging.INFO)
    console_level = level_map.get(console_level_str, logging.INFO)
    
    init_logging(log_level, console_level)