from mcp_servers.job_search_mcp import JobSearchTool
from agent.state import AgentState

async def search_node(state: AgentState):
    tool = JobSearchTool()
    query = state["messages"][-1] if state["messages"] else "software engineer"
    results = await tool.search_jobs(query)
    
    return {"jobs": results, "messages": ["Search completed"]}