"""Basic API import tests"""
import pytest


def test_fastapi_imports():
    """Verify FastAPI can be imported"""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        assert True
    except ImportError as e:
        pytest.fail(f"Failed to import FastAPI: {e}")
