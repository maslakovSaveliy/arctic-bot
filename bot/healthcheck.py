"""
Healthcheck-скрипт для Docker.
Проверяет подключение к MongoDB. Код возврата 0 = healthy, 1 = unhealthy.
"""

import sys
import os

from dotenv import load_dotenv

load_dotenv()


def check() -> bool:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure

    uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        client.close()
        return True
    except (ConnectionFailure, Exception):
        return False


if __name__ == "__main__":
    sys.exit(0 if check() else 1)
