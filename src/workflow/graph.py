"""LangGraph workflow for candidate-to-job matching."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from src.workflow.state import AgentState

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover - dependency bootstrap fallback
    END = "__end__"

    class _CompiledGraph:
        def __init__(self, nodes: list[Callable[[AgentState], Any]]) -> None:
            self.nodes = nodes

        async def ainvoke(self, state: dict[str, Any] | AgentState) -> AgentState:
            current_state = state if isinstance(state, AgentState) else AgentState(**state)
            for node in self.nodes:
                result = node(current_state)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, AgentState):
                    current_state = result
                elif result:
                    current_state = current_state.model_copy(update=result)
            return current_state

    class StateGraph:  # type: ignore[no-redef]
        """Minimal compatibility shim for environments without LangGraph."""

        def __init__(self, state_schema: type[AgentState]) -> None:
            self.state_schema = state_schema
            self.nodes: dict[str, Callable[[AgentState], Any]] = {}
            self.entrypoint: str | None = None

        def add_node(self, name: str, action: Callable[[AgentState], Any]) -> None:
            self.nodes[name] = action

        def add_edge(self, start_key: str, end_key: str) -> None:
            _ = (start_key, end_key)

        def set_entry_point(self, key: str) -> None:
            self.entrypoint = key

        def compile(self) -> _CompiledGraph:
            return _CompiledGraph(list(self.nodes.values()))


def validate_input_node(state: AgentState) -> AgentState:
    """Mark the matching request as ready for analysis."""

    state.workflow_status = "validated"
    return state


async def analyzer_node(state: AgentState) -> dict[str, str]:
    """Placeholder for resume and job-description analysis."""

    _ = (state.job_description, state.resume_text)
    return {"workflow_status": "analyzed"}


async def scorer_node(state: AgentState) -> dict[str, float | str]:
    """Placeholder for the ATS matching-score calculation."""

    _ = (state.job_description, state.resume_text)
    return {"matching_score": 0.0, "workflow_status": "scored"}


def build_workflow_graph() -> Any:
    """Build and compile the candidate-to-job matching workflow."""

    workflow = StateGraph(AgentState)
    workflow.add_node("validate_input", validate_input_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("scorer", scorer_node)
    workflow.set_entry_point("validate_input")
    workflow.add_edge("validate_input", "analyzer")
    workflow.add_edge("analyzer", "scorer")
    workflow.add_edge("scorer", END)
    return workflow.compile()


graph = build_workflow_graph()


__all__ = [
    "AgentState",
    "analyzer_node",
    "build_workflow_graph",
    "graph",
    "scorer_node",
    "validate_input_node",
]
