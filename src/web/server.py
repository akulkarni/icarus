"""
Web Server Runner

Runs FastAPI application in a separate thread for integration with main app.
"""
import asyncio
import logging
import uvicorn
from threading import Thread

logger = logging.getLogger(__name__)


class WebServer:
    """Web server wrapper for FastAPI app"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8000):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start web server in background thread"""
        logger.info(f"Starting web server on {self.host}:{self.port}")

        def run_server():
            from src.web.api import app
            uvicorn.run(
                app,
                host=self.host,
                port=self.port,
                log_level="info"
            )

        self.thread = Thread(target=run_server, daemon=True)
        self.thread.start()
        logger.info("Web server started")

    def stop(self):
        """Stop web server"""
        logger.info("Stopping web server")
        # Uvicorn handles cleanup on daemon thread termination


def start_web_server(host: str = "0.0.0.0", port: int = 8000) -> WebServer:
    """
    Convenience function to start web server

    Args:
        host: Host to bind to
        port: Port to bind to

    Returns:
        WebServer instance
    """
    server = WebServer(host, port)
    server.start()
    return server
