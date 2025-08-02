import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    app = FastAPI(title="Auth Service API")
    logger.info("Application starting")
    
    # CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True
    )

    # Include routers
    app.include_router(auth.router)
    logger.info("Routers initialized")

except Exception as e:
    logger.critical(f"Application initialization failed: {e}")
    raise

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info"
    )