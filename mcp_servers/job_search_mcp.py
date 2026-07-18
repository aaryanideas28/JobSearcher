class JobSearchTool:
    def __init__(self):
        self.name = "job_search_tool"

    async def search_jobs(self, query: str):
        print(f"Executing search for: {query}")
        return [
            {"id": "1", "title": "Software Engineer", "company": "Google", "url": "https://google.com"},
            {"id": "2", "title": "Backend Developer", "company": "Amazon", "url": "https://amazon.com"}
        ]