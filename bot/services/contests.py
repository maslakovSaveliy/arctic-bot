"""
Бизнес-логика конкурсов: валидация участия, розыгрыш, публикация в канал
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytz
from aiogram import Bot, types

from bot.config.config import CHANNEL_ID, CHANNEL_USERNAME, MAX_USER_ID

MOSCOW_TZ = pytz.timezone("Europe/Moscow")

from bot.database.contests import (
    get_contest,
    get_participant,
    get_random_participant,
    update_contest,
)


@dataclass
class ValidationResult:
    is_valid: bool
    error_message: Optional[str] = None


async def validate_participation(
    user_id: int,
    contest_id: str,
    bot: Bot,
) -> ValidationResult:
    contest = await get_contest(contest_id)
    if not contest:
        return ValidationResult(False, "Конкурс не найден.")

    if contest["status"] != "active":
        return ValidationResult(False, "Этот конкурс уже завершён.")

    if contest["end_time"] <= datetime.utcnow():
        return ValidationResult(False, "Время участия в конкурсе истекло.")

    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ("left", "kicked"):
            channel_link = f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}" if CHANNEL_USERNAME else "канал Arctic Trucks"
            return ValidationResult(
                False,
                f"Для участия в конкурсе необходимо быть подписанным на канал Arctic Trucks.\n\n"
                f"Подписаться: {channel_link}",
            )
    except Exception as exc:
        logging.error(f"Ошибка проверки подписки user_id={user_id}: {exc}")
        return ValidationResult(False, "Не удалось проверить подписку на канал. Попробуйте позже.")

    # TODO: вернуть проверку возраста аккаунта
    # if user_id >= MAX_USER_ID:
    #     return ValidationResult(
    #         False,
    #         "Для участия в конкурсе аккаунт Telegram должен быть создан ранее 2024 года.",
    #     )

    existing = await get_participant(contest_id, user_id)
    if existing:
        return ValidationResult(False, "Вы уже участвуете в этом конкурсе!")

    return ValidationResult(True)


async def pick_winner(contest_id: str) -> Optional[dict]:
    winner = await get_random_participant(contest_id)
    if not winner:
        return None

    await update_contest(
        contest_id,
        {
            "winner_user_id": winner["user_id"],
            "status": "completed",
        },
    )
    logging.info(f"Победитель конкурса {contest_id}: user_id={winner['user_id']}")
    return winner


async def publish_contest_to_channel(
    bot: Bot,
    contest: dict,
    bot_username: str,
) -> Optional[int]:
    deep_link = f"https://t.me/{bot_username}?start=contest_{contest['contest_id']}"

    text = (
        f"🎉 *{contest['title']}*\n\n"
        f"{contest['description']}\n\n"
        f"⏰ Приём заявок до: {pytz.UTC.localize(contest['end_time']).astimezone(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M')} МСК\n\n"
        "Нажмите кнопку ниже, чтобы принять участие!"
    )

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🎯 Участвовать", url=deep_link),
    )

    try:
        photo_file_id = contest.get("photo_file_id")
        if photo_file_id:
            msg = await bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=photo_file_id,
                caption=text,
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        else:
            msg = await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode=types.ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )
        await update_contest(contest["contest_id"], {"channel_message_id": msg.message_id})
        logging.info(f"Пост конкурса {contest['contest_id']} опубликован в канале, msg_id={msg.message_id}")
        return msg.message_id
    except Exception as exc:
        logging.error(f"Ошибка публикации конкурса в канал: {exc}")
        return None


async def publish_winner_to_channel(
    bot: Bot,
    contest: dict,
    winner: dict,
) -> bool:
    winner_name = winner.get("first_name") or winner.get("username") or str(winner["user_id"])
    if winner.get("username"):
        winner_mention = f"@{winner['username']}"
    else:
        winner_mention = winner_name

    text = (
        f"🏆 *Результаты конкурса «{contest['title']}»*\n\n"
        f"Победитель: {winner_mention}\n"
        f"Всего участников: {contest.get('participants_count', 0)}\n\n"
        "Поздравляем! 🎉"
    )

    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=text,
            parse_mode=types.ParseMode.MARKDOWN,
        )
        logging.info(f"Результат конкурса {contest['contest_id']} опубликован в канале")
        return True
    except Exception as exc:
        logging.error(f"Ошибка публикации результата конкурса: {exc}")
        return False


async def delete_contest_channel_message(bot: Bot, contest: dict) -> bool:
    """Удаляет пост конкурса из канала, если он был опубликован."""
    message_id = contest.get("channel_message_id")
    if not message_id:
        return True
    try:
        await bot.delete_message(chat_id=CHANNEL_ID, message_id=message_id)
        logging.info(f"Пост конкурса {contest['contest_id']} удалён из канала (msg_id={message_id})")
        return True
    except Exception as exc:
        logging.error(f"Не удалось удалить пост конкурса из канала: {exc}")
        return False


async def notify_winner(bot: Bot, winner: dict, contest: dict) -> bool:
    text = (
        f"🎉 Поздравляем! Вы стали победителем конкурса «{contest['title']}»!\n\n"
        f"Приз: {contest['description']}\n\n"
        "Администратор скоро свяжется с вами для вручения приза."
    )
    try:
        await bot.send_message(chat_id=winner["user_id"], text=text)
        logging.info(f"Победитель {winner['user_id']} уведомлён о выигрыше в конкурсе {contest['contest_id']}")
        return True
    except Exception as exc:
        logging.error(f"Не удалось уведомить победителя {winner['user_id']}: {exc}")
        return False
