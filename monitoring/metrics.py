from agent.state import AgentState

def update_metrics(state: AgentState):
    # Logic to record how many jobs were found in this run
    job_count = len(state.get("jobs", []))
    print(f"Metrics: Processed {job_count} jobs.")
    return {"messages": [f"Processed {job_count} jobs"]}