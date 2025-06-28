import logging
import os
import sys

def setup_logger(debug_mode=False):
    """
    Sets up the application logger based on debug mode setting.
    
    Args:
        debug_mode (bool): If True, creates log file and enables detailed logging.
                          If False, only shows critical errors in console.
    """
    # Clear any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Set base logging level
    if debug_mode:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        
        # Determine the directory for log files
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as PyInstaller bundle
            log_dir = os.path.dirname(sys.executable)
        else:
            # Running as normal Python script
            log_dir = os.path.dirname(os.path.abspath(__file__))
        
        log_file_path = os.path.join(log_dir, 'app.log')
        
        # Create file handler
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_formatter)
        
        # Create console handler for debug mode
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to root logger
        logging.getLogger().addHandler(file_handler)
        logging.getLogger().addHandler(console_handler)
        
        logging.info(f"Debug mode enabled. Logging to: {log_file_path}")
    else:
        # Only show critical errors in console when debug mode is off
        logging.basicConfig(level=logging.CRITICAL, format='%(levelname)s - %(message)s')

def get_logger(name):
    """
    Get a logger instance for a specific module.
    
    Args:
        name (str): Usually __name__ from the calling module
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name) 