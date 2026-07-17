import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

class PostgresClient:
    def __init__(self):
        self.dsn = f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@localhost:5432/{os.getenv('POSTGRES_DB')}"
        self.pool = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self.dsn)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def save_job(self, job_data):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO jobs (id, title, company, description, url, status) VALUES ($1, $2, $3, $4, $5, $6)",
                job_data.id, job_data.title, job_data.company, job_data.description, job_data.url, job_data.status
            )

    async def get_job_history(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM jobs")