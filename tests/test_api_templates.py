# File: tests/test_api_templates.py
from __future__ import annotations

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_get_templates_endpoint() -> None:
    """Verify that the GET /api/v1/templates endpoint returns the correct list of presets."""
    response = client.get("/api/v1/templates")
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4
    
    # Assert exact structure of first template preset object
    first = data[0]
    assert "id" in first
    assert "name" in first
    assert "description" in first
    assert "preview_url" in first
    
    # Assert ids match our design presets
    ids = {t["id"] for t in data}
    assert ids == {"minimal_ats", "modern_tech", "classic_executive", "compact_onepage"}
