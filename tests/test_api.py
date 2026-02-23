"""
Tests for the FastAPI API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestHealthEndpoint:
    def test_health_returns_200(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_returns_200(self):
        response = client.get("/")
        assert response.status_code == 200

class TestSessionEndpoint:
    def test_start_session(self):
        response = client.post("/api/sessions/start?user_id=test_user")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert "session_id" in data
