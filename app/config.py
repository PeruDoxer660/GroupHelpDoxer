import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "app/data/bot.db")

DEFAULT_WARN_LIMIT = 3
DEFAULT_AUTO_MUTE_MINUTES = 60
DEFAULT_FLOOD_MAX_MESSAGES = 5
DEFAULT_FLOOD_WINDOW_SECONDS = 10
DEFAULT_CAPTCHA_TIMEOUT_MINUTES = 5
DEFAULT_RULES_TEXT = "📜 Aún no se han configurado las reglas del grupo."