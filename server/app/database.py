import os
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.models.job import Job
from app.logger import logger


class Database:
    client: AsyncIOMotorClient = None
    database = None

    @classmethod
    async def connect(cls):
        mongodb_url = os.getenv(
            "MONGODB_URL", "mongodb://localhost:27017/phylogenetic_jobs"
        )
        try:
            cls.client = AsyncIOMotorClient(mongodb_url)
            cls.database = cls.client.get_default_database()
            await init_beanie(database=cls.database, document_models=[Job])
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
            logger.info("Disconnected from MongoDB")


database = Database()
