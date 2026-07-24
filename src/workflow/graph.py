# File: src/workflow/graph.py
from __future__ import annotations

from typing import Any, Callable

from src.workflow.state import AgentState

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    END = "__end__"

    class _CompiledGraph:
        def __init__(self, entrypoint: Callable[[AgentState], AgentState] | None = None) -> None:
            self.entrypoint = entrypoint

        def invoke(self, state: AgentState) -> AgentState:
            if self.entrypoint is None:
                return state
            return self.entrypoint(state)

    class StateGraph:  # type: ignore[no-redef]
        """Tiny compatibility shim for import-only test environments."""

        def __init__(self, state_schema: type[AgentState]) -> None:
            self.state_schema = state_schema
            self.nodes: dict[str, Callable[[AgentState], AgentState]] = {}
            self.entrypoint: str | None = None

        def add_node(self, name: str, action: Callable[[AgentState], AgentState]) -> None:
            self.nodes[name] = action

        def add_edge(self, start_key: str, end_key: str) -> None:
            _ = (start_key, end_key)

        def set_entry_point(self, key: str) -> None:
            self.entrypoint = key

        def compile(self) -> _CompiledGraph:
            action = self.nodes.get(self.entrypoint or "")
            return _CompiledGraph(action)


def validate_input_node(state: AgentState) -> AgentState:
    """Validate initial workflow input."""

    state.workflow_status = "validated"
    return state


def discover_jobs_node(state: AgentState) -> AgentState:
    """Discover candidate job postings."""

    return state


def optimize_resume_node(state: AgentState) -> AgentState:
    """Optimize resume text for the selected job target."""

    state.optimized_resume = state.resume_text
    return state


def score_ats_node(state: AgentState) -> AgentState:
    """Score optimized resume against the job description."""

    state.ats_score = 0.0
    return state


def build_outreach_node(state: AgentState) -> AgentState:
    """Build cover letter and email payload artifacts."""

    state.cover_letter = ""
    state.email_payload = {}
    return state


def dispatch_outreach_node(state: AgentState) -> AgentState:
    """Queue final outreach dispatch."""

    state.workflow_status = "dispatch_ready"
    return state


def build_workflow_graph() -> Any:
    """Assemble and compile the resume automation workflow graph."""

    graph = StateGraph(AgentState)
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("discover_jobs", discover_jobs_node)
    graph.add_node("optimize_resume", optimize_resume_node)
    graph.add_node("score_ats", score_ats_node)
    graph.add_node("build_outreach", build_outreach_node)
    graph.add_node("dispatch_outreach", dispatch_outreach_node)

    graph.set_entry_point("validate_input")
    graph.add_edge("validate_input", "discover_jobs")
    graph.add_edge("discover_jobs", "optimize_resume")
    graph.add_edge("optimize_resume", "score_ats")
    graph.add_edge("score_ats", "build_outreach")
    graph.add_edge("build_outreach", "dispatch_outreach")
    graph.add_edge("dispatch_outreach", END)
    return graph.compile()
