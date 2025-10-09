from backend.app.core.logging import get_logger
from fastapi import APIRouter
logger = get_logger()
router = APIRouter(prefix="/home")

@router.get("/")
def home():
    logger.info("Home page accessed")
    logger.debug("Home page accessed")
    logger.error("Home page accessed")
    logger.warning("Home page accessed")
    logger.critical("Home page accessed")
    return {"message": "Welcome to the NextGen Bank API"}