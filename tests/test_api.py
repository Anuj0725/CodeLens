import pytest
from fastapi.testclient import TestClient
from codelens.api.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_ok_status(self):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


class TestAskValidation:
    def test_rejects_short_query(self):
        response = client.post("/ask", json={"query": "hi"})
        assert response.status_code == 422

    def test_rejects_missing_query(self):
        response = client.post("/ask", json={"repo_filter": "test"})
        assert response.status_code == 422


class TestIngestValidation:
    def test_rejects_invalid_source_type(self):
        response = client.post("/ingest", json={"source_type": "ftp", "url": "ftp://example.com/repo"})
        assert response.status_code == 422

    def test_rejects_bad_github_url(self):
        response = client.post("/ingest", json={"source_type": "github", "url": "https://notgithub.com/repo"})
        assert response.status_code == 400
