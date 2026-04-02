"""
Модуль для работы с базой данных MongoDB
"""

from bot.database.db import get_db, close_db_connection, init_db
from bot.database.users import add_user, get_user, get_all_users, update_user, get_users_by_filter, update_user_status, count_users, get_city_stats
from bot.database.invite_links import create_invite_link, get_invite_link, get_source_by_link, get_all_invite_links
from bot.database.contests import (
    create_contest,
    delete_contest,
    delete_contest_participants,
    get_contest,
    get_active_contests,
    update_contest,
    add_participant,
    get_participant,
    get_contest_participants,
    get_random_participant,
) 