import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("JobSearchAgent")

def log_event(message: str):
    logger.info(f"[AGENT EVENT]: {message}")