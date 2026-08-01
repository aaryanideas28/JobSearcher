# File: tests/test_graph.py
from __future__ import annotations

import pytest
from src.workflow.graph import build_workflow_graph, validate_input_node
from src.workflow.state import AgentState


def test_validate_input_node_sets_status() -> None:
    state: AgentState = {
        "session_id": "session-1",
        "user_id": 1,
        "resume_text": "Python engineer",
        "job_description": "Backend engineer",
    }
    result = validate_input_node(state)
    assert result is state
    assert result["workflow_status"] == "validated"
    assert result["validation_errors"] == []


def test_workflow_graph_compiles() -> None:
    graph = build_workflow_graph()
    assert graph is not None


@pytest.mark.anyio
async def test_job_discovery_node_forwards_preferences() -> None:
    from src.workflow.graph import job_discovery_node
    from unittest.mock import AsyncMock, patch

    state: AgentState = {
        "session_id": "session-1",
        "user_id": 1,
        "resume_text": "Python engineer",
        "job_description": "Backend engineer",
        "target_role": "Backend Engineer",
        "skills_to_highlight": ["FastAPI"],
        "preferred_locations": ["Mumbai", "Remote"],
        "work_mode": "Hybrid"
    }

    with patch("src.agents.job_discovery.JobDiscoveryAgent.discover", new_callable=AsyncMock) as mock_discover:
        mock_discover.return_value = []
        result = await job_discovery_node(state)
        mock_discover.assert_called_once_with(
            query="Backend Engineer jobs FastAPI",
            max_results=6,
            preferred_locations=["Mumbai", "Remote"],
            work_mode="Hybrid"
        )
        assert result["workflow_status"] == "jobs_discovered"

