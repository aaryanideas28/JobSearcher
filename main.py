from fastapi import FastAPI
from agent.graph import app as agent_app

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "System is running"}

@app.post("/start-search")
async def start_search():
    initial_state = {"messages": ["Search for jobs"], "jobs": []}
    result = await agent_app.ainvoke(initial_state)
    return {"status": "success", "result": result["messages"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)