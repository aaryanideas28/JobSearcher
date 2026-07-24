# File: tests/test_graph.py
from __future__ import annotations

from src.workflow.graph import build_workflow_graph, validate_input_node
from src.workflow.state import AgentState


def test_validate_input_node_sets_status() -> None:
    state = AgentState(
        user_resume_json={"summary": "Python engineer"},
        job_target_json={"description": "Backend engineer"},
    )
    result = validate_input_node(state)
    assert result is state
    assert result.workflow_status == "validated"


def test_workflow_graph_compiles() -> None:
    graph = build_workflow_graph()
    assert graph is not None
