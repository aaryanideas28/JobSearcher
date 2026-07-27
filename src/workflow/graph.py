# File: src/workflow/graph.py
"""LangGraph workflow assembly for resume automation."""

from __future__ import annotations

from typing import Any, Protocol

from src.workflow.state import AgentState

try:
    from langgraph.graph import END, START, StateGraph
except Exception:  # pragma: no cover - fallback for minimal local installs
    START = "__start__"
    END = "__end__"

    class StateGraph:  # type: ignore[no-redef]
        """Tiny fallback graph builder used when langgraph is not installed."""

        def __init__(self, state_type: type[AgentState]) -> None:
            self.state_type = state_type
            self.nodes: dict[str, Any] = {}
            self.edges: list[tuple[str, str]] = []

        def add_node(self, name: str, node: Any) -> None:
            self.nodes[name] = node

        def add_edge(self, source: str, target: str) -> None:
            self.edges.append((source, target))

        def compile(self) -> "StateGraph":
            return self


class CompiledGraph(Protocol):
    """Protocol for compiled graph objects."""

    def invoke(self, input: AgentState) -> AgentState:
        """Invoke the graph."""
        ...


def intake_node(state: AgentState) -> AgentState:
    """Validate and normalize initial workflow state."""
    state["workflow_status"] = "intake_complete"
    state.setdefault("feedback", [])
    state.setdefault("attempt_count", 0)
    return state


def validate_input_node(state: AgentState) -> AgentState:
    """Backward-compatible validation node used by tests and older imports."""
    state["workflow_status"] = "validated"
    state["validation_errors"] = []
    return state


def resume_optimizer_node(state: AgentState) -> AgentState:
    """Placeholder resume optimization node."""
    state["optimized_resume"] = state.get("optimized_resume") or state["resume_text"]
    state["workflow_status"] = "resume_optimized"
    return state


def ats_scoring_node(state: AgentState) -> AgentState:
    """Placeholder ATS scoring node."""
    state["ats_score"] = float(state.get("ats_score", 0.0))
    state["workflow_status"] = "ats_scored"
    return state


def job_discovery_node(state: AgentState) -> AgentState:
    """Placeholder job discovery node."""
    state.setdefault("discovered_jobs", [])
    state["workflow_status"] = "jobs_discovered"
    return state


def outreach_node(state: AgentState) -> AgentState:
    """Placeholder outreach drafting node."""
    state.setdefault("email_payload", {})
    state["workflow_status"] = "outreach_drafted"
    return state


def validation_node(state: AgentState) -> AgentState:
    """Placeholder security and quality validation node."""
    state.setdefault("validation_errors", [])
    state.setdefault("quality_checks", {})
    state["workflow_status"] = "awaiting_human_review"
    return state


def build_workflow_graph() -> Any:
    """Assemble and compile the workflow graph."""
    graph = StateGraph(AgentState)
    graph.add_node("intake", intake_node)
    graph.add_node("resume_optimizer", resume_optimizer_node)
    graph.add_node("ats_scoring", ats_scoring_node)
    graph.add_node("job_discovery", job_discovery_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("validation", validation_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "resume_optimizer")
    graph.add_edge("resume_optimizer", "ats_scoring")
    graph.add_edge("resume_optimizer", "job_discovery")
    graph.add_edge("ats_scoring", "outreach")
    graph.add_edge("job_discovery", "outreach")
    graph.add_edge("outreach", "validation")
    graph.add_edge("validation", END)
    return graph.compile()


workflow_graph = build_workflow_graph()
graph = workflow_graph
