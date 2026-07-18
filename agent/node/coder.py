from agent.state import AgentState

def coder_node(state: AgentState):
    print("Coder node: Drafting cover letter for job...")
    # This is where the LLM call will eventually go
    return {
        "messages": ["Draft completed successfully"],
        "current_draft": {
            "job_id": "1", 
            "cover_letter": "Dear Hiring Manager...", 
            "resume_version": "v1"
        }
    }