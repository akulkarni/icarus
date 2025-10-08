"""Basic API import tests"""
import pytest
from fastapi.testclient import TestClient


def test_fastapi_imports():
    """Verify FastAPI can be imported"""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import FastAPI: {e}")


def test_app_creation():
    """Test FastAPI app can be created"""
    from src.web.api import app
    assert app is not None
    assert app.title == "Icarus Trading System Dashboard"


def test_root_endpoint():
    """Test root endpoint returns status"""
    from src.web.api import app
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"
