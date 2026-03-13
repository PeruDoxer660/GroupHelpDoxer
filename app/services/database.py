import aiosqlite
from app.config import (
    DB_PATH,
    DEFAULT_WARN_LIMIT,
    DEFAULT_AUTO_MUTE_MINUTES,
    DEFAULT_FLOOD_MAX_MESSAGES,
    DEFAULT_FLOOD_WINDOW_SECONDS,
    DEFAULT_RULES_TEXT,
)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS group_settings (
            chat_id INTEGER PRIMARY KEY,
            anti_link INTEGER DEFAULT 1,
            welcome_text TEXT DEFAULT '🎉 Bienvenido/a, {name} al grupo.',
            rules_text TEXT DEFAULT '📜 Aún no se han configurado las reglas del grupo.',
            antiflood INTEGER DEFAULT 1,
            captcha_enabled INTEGER DEFAULT 1,
            warn_limit INTEGER DEFAULT 3,
            auto_mute_minutes INTEGER DEFAULT 60,
            flood_max_messages INTEGER DEFAULT 5,
            flood_window_seconds INTEGER DEFAULT 10
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS bad_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            word TEXT NOT NULL
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            warns INTEGER DEFAULT 0,
            UNIQUE(chat_id, user_id)
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER,
            admin_id INTEGER,
            action TEXT NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS captcha_challenges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            UNIQUE(chat_id, user_id)
        )
        """)

        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN antiflood INTEGER DEFAULT 1")
        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN captcha_enabled INTEGER DEFAULT 1")
        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN warn_limit INTEGER DEFAULT 3")
        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN auto_mute_minutes INTEGER DEFAULT 60")
        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN flood_max_messages INTEGER DEFAULT 5")
        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN flood_window_seconds INTEGER DEFAULT 10")
        await _run_safe_alter(db, "ALTER TABLE group_settings ADD COLUMN rules_text TEXT DEFAULT '📜 Aún no se han configurado las reglas del grupo.'")

        await db.commit()


async def _run_safe_alter(db, sql: str):
    try:
        await db.execute(sql)
    except Exception:
        pass


async def ensure_group(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO group_settings (
                chat_id,
                anti_link,
                welcome_text,
                rules_text,
                antiflood,
                captcha_enabled,
                warn_limit,
                auto_mute_minutes,
                flood_max_messages,
                flood_window_seconds
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            1,
            '🎉 Bienvenido/a, {name} al grupo.',
            DEFAULT_RULES_TEXT,
            1,
            1,
            DEFAULT_WARN_LIMIT,
            DEFAULT_AUTO_MUTE_MINUTES,
            DEFAULT_FLOOD_MAX_MESSAGES,
            DEFAULT_FLOOD_WINDOW_SECONDS
        ))
        await db.commit()


async def get_settings(chat_id: int):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT
                anti_link,
                welcome_text,
                rules_text,
                antiflood,
                captcha_enabled,
                warn_limit,
                auto_mute_minutes,
                flood_max_messages,
                flood_window_seconds
            FROM group_settings
            WHERE chat_id = ?
        """, (chat_id,))
        row = await cursor.fetchone()

        return {
            "anti_link": bool(row[0]),
            "welcome_text": row[1],
            "rules_text": row[2],
            "antiflood": bool(row[3]),
            "captcha_enabled": bool(row[4]),
            "warn_limit": int(row[5]),
            "auto_mute_minutes": int(row[6]),
            "flood_max_messages": int(row[7]),
            "flood_window_seconds": int(row[8]),
        }


async def set_anti_link(chat_id: int, value: bool):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET anti_link = ? WHERE chat_id = ?",
            (1 if value else 0, chat_id)
        )
        await db.commit()


async def set_antiflood(chat_id: int, value: bool):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET antiflood = ? WHERE chat_id = ?",
            (1 if value else 0, chat_id)
        )
        await db.commit()


async def set_captcha_enabled(chat_id: int, value: bool):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET captcha_enabled = ? WHERE chat_id = ?",
            (1 if value else 0, chat_id)
        )
        await db.commit()


async def set_warn_limit(chat_id: int, value: int):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET warn_limit = ? WHERE chat_id = ?",
            (value, chat_id)
        )
        await db.commit()


async def set_auto_mute_minutes(chat_id: int, value: int):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET auto_mute_minutes = ? WHERE chat_id = ?",
            (value, chat_id)
        )
        await db.commit()


async def set_flood_limit(chat_id: int, max_messages: int, window_seconds: int):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE group_settings
            SET flood_max_messages = ?, flood_window_seconds = ?
            WHERE chat_id = ?
        """, (max_messages, window_seconds, chat_id))
        await db.commit()


async def set_welcome_text(chat_id: int, text: str):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET welcome_text = ? WHERE chat_id = ?",
            (text, chat_id)
        )
        await db.commit()


async def set_rules_text(chat_id: int, text: str):
    await ensure_group(chat_id)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE group_settings SET rules_text = ? WHERE chat_id = ?",
            (text, chat_id)
        )
        await db.commit()


async def add_bad_word(chat_id: int, word: str):
    word = word.strip().lower()
    if not word:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bad_words (chat_id, word) VALUES (?, ?)",
            (chat_id, word)
        )
        await db.commit()


async def del_bad_word(chat_id: int, word: str):
    word = word.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM bad_words WHERE chat_id = ? AND word = ?",
            (chat_id, word)
        )
        await db.commit()


async def get_bad_words(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT word FROM bad_words WHERE chat_id = ? ORDER BY word ASC",
            (chat_id,)
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def add_warn(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO warnings (chat_id, user_id, warns)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET warns = warns + 1
        """, (chat_id, user_id))
        await db.commit()

        cursor = await db.execute(
            "SELECT warns FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        row = await cursor.fetchone()
        return row[0]


async def remove_warn(chat_id: int, user_id: int):
    current = await get_warns(chat_id, user_id)
    if current <= 0:
        return 0

    new_value = current - 1
    async with aiosqlite.connect(DB_PATH) as db:
        if new_value == 0:
            await db.execute(
                "DELETE FROM warnings WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id)
            )
        else:
            await db.execute(
                "UPDATE warnings SET warns = ? WHERE chat_id = ? AND user_id = ?",
                (new_value, chat_id, user_id)
            )
        await db.commit()

    return new_value


async def get_warns(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT warns FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def reset_warns(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM warnings WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        await db.commit()


async def get_group_stats(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM bad_words WHERE chat_id = ?",
            (chat_id,)
        )
        bad_words_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM warnings WHERE chat_id = ?",
            (chat_id,)
        )
        warned_users_count = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM action_logs WHERE chat_id = ?",
            (chat_id,)
        )
        logs_count = (await cursor.fetchone())[0]

        return {
            "bad_words_count": bad_words_count,
            "warned_users_count": warned_users_count,
            "logs_count": logs_count,
        }


async def add_log(chat_id: int, action: str, user_id: int | None = None, admin_id: int | None = None, reason: str | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO action_logs (chat_id, user_id, admin_id, action, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (chat_id, user_id, admin_id, action, reason))
        await db.commit()


async def get_logs(chat_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT user_id, admin_id, action, reason, created_at
            FROM action_logs
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (chat_id, limit))
        return await cursor.fetchall()


async def create_or_update_captcha(chat_id: int, user_id: int, question: str, answer: str, expires_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO captcha_challenges (chat_id, user_id, question, answer, expires_at, verified)
            VALUES (?, ?, ?, ?, ?, 0)
            ON CONFLICT(chat_id, user_id)
            DO UPDATE SET
                question = excluded.question,
                answer = excluded.answer,
                expires_at = excluded.expires_at,
                verified = 0
        """, (chat_id, user_id, question, answer, expires_at))
        await db.commit()


async def get_captcha(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT question, answer, expires_at, verified
            FROM captcha_challenges
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
        row = await cursor.fetchone()
        if not row:
            return None

        return {
            "question": row[0],
            "answer": row[1],
            "expires_at": row[2],
            "verified": bool(row[3]),
        }


async def verify_captcha(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE captcha_challenges
            SET verified = 1
            WHERE chat_id = ? AND user_id = ?
        """, (chat_id, user_id))
        await db.commit()


async def delete_captcha(chat_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM captcha_challenges WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id)
        )
        await db.commit()