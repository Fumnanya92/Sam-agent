#!/usr/bin/env python3
"""
Test Sam logging system
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set log level for testing
os.environ['SAM_CONSOLE_LOG_LEVEL'] = 'DEBUG'

def test_logging():
    """Test the logging system across components"""
    print("🧪 Testing Sam Logging System")
    print("=" * 50)
    
    # Test basic logging
    from log.logger import get_logger, log_function_entry, log_function_exit, log_performance, log_state_change
    
    test_logger = get_logger("TEST")
    test_logger.info("Starting logging test")
    
    # Test function logging
    log_function_entry(test_logger, "test_function", param1="value1", param2=123)
    
    import time
    start = time.time()
    time.sleep(0.1)  # Simulate work
    duration = time.time() - start
    
    log_performance(test_logger, "test operation", duration)
    log_function_exit(test_logger, "test_function", "success")
    
    # Test state change logging
    log_state_change(test_logger, "IDLE", "LISTENING")
    log_state_change(test_logger, "LISTENING", "THINKING")
    
    # Test component loggers
    llm_logger = get_logger("LLM")
    llm_logger.info("LLM component test message")
    
    stt_logger = get_logger("STT")
    stt_logger.debug("STT debug message")
    
    tts_logger = get_logger("TTS")
    tts_logger.warning("TTS warning message")
    
    # Test error logging
    try:
        raise ValueError("Test error for logging")
    except Exception as e:
        from log.logger import log_error
        log_error(test_logger, "test_error_function", e)
    
    test_logger.info("Logging test completed")
    print("\n✅ Check the log files in the 'log' directory for detailed output")

if __name__ == "__main__":
    test_logging()