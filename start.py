#!/usr/bin/env python3
"""
Startup script for Render deployment
Handles environment setup and graceful startup
"""
import os
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required dependencies are available"""
    try:
        import weasyprint
        import fastapi
        import uvicorn
        logger.info("All dependencies are available")
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return False

def setup_environment():
    """Setup environment variables and paths"""
    # Set default port if not provided by Render
    if not os.environ.get("PORT"):
        os.environ["PORT"] = "8000"
    
    # Create temp directory if needed
    temp_dir = Path("/tmp")
    if not temp_dir.exists():
        temp_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Environment setup complete. PORT: {os.environ.get('PORT')}")

def main():
    """Main startup function"""
    logger.info("Starting SEO PDF Generator service...")
    
    # Check dependencies
    if not check_dependencies():
        logger.error("Dependency check failed")
        sys.exit(1)
    
    # Setup environment
    setup_environment()
    
    # Import and start the app
    try:
        from main import app
        import uvicorn
        
        port = int(os.environ.get("PORT", 8000))
        host = "0.0.0.0"
        
        logger.info(f"Starting server on {host}:{port}")
        
        # Start with production-ready settings
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
            use_colors=False,  # Better for cloud logging
            loop="asyncio"
        )
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
