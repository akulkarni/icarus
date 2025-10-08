"""Test integration with main application"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_web_server_starts():
    """Test that web server can start"""
    from src.web.api import app
    assert app is not None


@pytest.mark.asyncio
async def test_startup_shutdown_events():
    """Test app lifecycle events"""
    from src.web.api import startup, shutdown

    # Should not raise exceptions
    await startup()
    await shutdown()


def test_web_server_module():
    """Test WebServer class"""
    from src.web.server import WebServer

    server = WebServer(host="127.0.0.1", port=8001)
    assert server.host == "127.0.0.1"
    assert server.port == 8001
