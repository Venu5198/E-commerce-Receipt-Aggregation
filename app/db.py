from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings


class MongoDBManager:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

    def connect(self, uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
        mongo_uri = uri or settings.MONGO_URI
        database_name = db_name or settings.MONGO_DB_NAME
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[database_name]

    def close(self) -> None:
        if self.client is not None:
            self.client.close()
            self.client = None
            self.db = None

    def get_database(self) -> AsyncIOMotorDatabase:
        if self.db is None:
            self.connect()
        return self.db


db_manager = MongoDBManager()


def get_db() -> AsyncIOMotorDatabase:
    return db_manager.get_database()
