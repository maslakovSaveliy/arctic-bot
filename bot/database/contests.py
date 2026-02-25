"""
CRUD-операции для конкурсов и участников
"""

import logging
import random
from datetime import datetime
from typing import Optional

from bot.database.db import get_db
from bot.config.config import CONTESTS_COLLECTION, CONTEST_PARTICIPANTS_COLLECTION


async def create_contest(
    contest_id: str,
    title: str,
    description: str,
    end_time: datetime,
    created_by: int,
    photo_file_id: Optional[str] = None,
) -> dict:
    db = get_db()
    contest_data = {
        "contest_id": contest_id,
        "title": title,
        "description": description,
        "end_time": end_time,
        "status": "active",
        "created_at": datetime.utcnow(),
        "created_by": created_by,
        "winner_user_id": None,
        "channel_message_id": None,
        "participants_count": 0,
        "photo_file_id": photo_file_id,
    }
    await db[CONTESTS_COLLECTION].insert_one(contest_data)
    logging.info(f"Конкурс создан: {contest_id} — {title}")
    return contest_data


async def get_contest(contest_id: str) -> Optional[dict]:
    db = get_db()
    return await db[CONTESTS_COLLECTION].find_one({"contest_id": contest_id})


async def get_active_contests() -> list:
    db = get_db()
    cursor = db[CONTESTS_COLLECTION].find({"status": "active"}).sort("created_at", -1)
    return await cursor.to_list(length=None)


async def update_contest(contest_id: str, update_data: dict) -> bool:
    db = get_db()
    result = await db[CONTESTS_COLLECTION].update_one(
        {"contest_id": contest_id},
        {"$set": update_data},
    )
    return result.modified_count > 0


async def add_participant(
    contest_id: str,
    user_id: int,
    username: Optional[str],
    first_name: Optional[str],
    car_model: str,
    city: str,
) -> dict:
    db = get_db()
    participant_data = {
        "contest_id": contest_id,
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "car_model": car_model,
        "city": city,
        "joined_at": datetime.utcnow(),
    }
    await db[CONTEST_PARTICIPANTS_COLLECTION].insert_one(participant_data)

    await db[CONTESTS_COLLECTION].update_one(
        {"contest_id": contest_id},
        {"$inc": {"participants_count": 1}},
    )

    logging.info(f"Участник {user_id} добавлен в конкурс {contest_id}")
    return participant_data


async def get_participant(contest_id: str, user_id: int) -> Optional[dict]:
    db = get_db()
    return await db[CONTEST_PARTICIPANTS_COLLECTION].find_one(
        {"contest_id": contest_id, "user_id": user_id}
    )


async def get_contest_participants(contest_id: str) -> list:
    db = get_db()
    cursor = db[CONTEST_PARTICIPANTS_COLLECTION].find({"contest_id": contest_id})
    return await cursor.to_list(length=None)


async def get_random_participant(contest_id: str) -> Optional[dict]:
    db = get_db()
    participants = await get_contest_participants(contest_id)
    if not participants:
        return None
    return random.choice(participants)
