import os
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.job import Job


class Database:
    client: AsyncIOMotorClient = None
    database = None

    @classmethod
    async def connect(cls):
        mongodb_url = os.getenv(
            "MONGODB_URL", "mongodb://localhost:27017/phylogenetic_jobs"
        )
        cls.client = AsyncIOMotorClient(mongodb_url)
        cls.database = cls.client.get_default_database()

        await init_beanie(database=cls.database, document_models=[Job])
        print("Connected to mongodb")

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
            print("Disconnected from mongodb")


database = Database()
