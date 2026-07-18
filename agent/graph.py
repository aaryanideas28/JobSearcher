from langgraph.graph import StateGraph, END
from agent.state import AgentState
from middleware.auth_guard import AuthGuard

from agent.node.search import search_node
from agent.node.draft import draft_node

def review_node(state: AgentState):
    # This node pauses execution until human intervention
    if not AuthGuard.check_approval(state):
        return {"messages": ["Paused for review"]}
    return {"messages": ["Approved and proceeding"]}

workflow = StateGraph(AgentState)

workflow.add_node("search", search_node)
workflow.add_node("draft", draft_node)
workflow.add_node("review", review_node)

workflow.set_entry_point("search")
workflow.add_edge("search", "draft")
workflow.add_edge("draft", "review")
workflow.add_edge("review", END)

app = workflow.compile()