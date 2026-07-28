import asyncio
import httpx
from config.settings import get_settings

async def main():
    settings = get_settings()
    print("Tavily API Key:", settings.tavily_api_key)
    
    payload = {
        "api_key": settings.tavily_api_key,
        "query": "Software Engineer jobs",
        "search_depth": "advanced",
        "max_results": 5,
        "include_answer": False,
        "include_raw_content": True,
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            print("Status Code:", response.status_code)
            print("Response text:", response.text[:500])
            response.raise_for_status()
            data = response.json()
            print("Success! Discovered", len(data.get("results", [])), "jobs")
    except Exception as e:
        print("Error details:", type(e), str(e))

if __name__ == "__main__":
    asyncio.run(main())
