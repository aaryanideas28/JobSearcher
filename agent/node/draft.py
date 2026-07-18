from agent.state import AgentState

def draft_node(state: AgentState):
    print("Drafting application...")
    return {"messages": ["Draft completed"], "is_approved": False}