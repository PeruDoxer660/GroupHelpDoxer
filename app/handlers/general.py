from time import perf_counter

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.database import get_settings, get_group_stats

router = Router()


HELP_TEXT = """
🤖 *Bot Moderador Pro*

*Comandos generales*
/start - iniciar bot
/help - ayuda completa
/ping - comprobar si el bot responde
/id - ver tu ID o el de otro usuario respondiendo
/rules - ver reglas del grupo
/stats - estadísticas rápidas del grupo

*Comandos de administración*
/panel - panel rápido con botones
/menu - alias de panel
/settings - ver configuración actual
/antilink on|off
/antiflood on|off
/captcha on|off
/setwarnlimit 3
/setautomute 60
/setflood 5 10
/setwelcome texto
/setrules texto
/addbadword palabra
/delbadword palabra

*Moderación*
/warn
/unwarn
/warns
/clearwarns
/mute 10m
/unmute
/ban
/unban 123456789
/logs
/logs 15

📌 En comandos como /warn, /mute, /ban, /unmute y /clearwarns debes responder al mensaje del usuario.
""".strip()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Hola.\n\n"
        "Soy tu bot moderador para grupos de Telegram.\n"
        "Usa /help para ver todos los comandos.\n"
        "Usa /panel para abrir el menú rápido de administración."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.reply(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("ping"))
async def cmd_ping(message: Message):
    start = perf_counter()
    reply = await message.reply("🏓 Probando respuesta...")
    end = perf_counter()
    ms = int((end - start) * 1000)

    try:
        await reply.edit_text(f"🏓 Pong\n⚡ Tiempo de respuesta aproximado: {ms} ms")
    except Exception:
        pass


@router.message(Command("id"))
async def cmd_id(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        await message.reply(
            f"🆔 Usuario: {user.full_name}\n"
            f"ID: `{user.id}`",
            parse_mode="Markdown"
        )
        return

    if message.from_user:
        await message.reply(
            f"🆔 Tu ID es: `{message.from_user.id}`\n"
            f"🧩 Chat ID: `{message.chat.id}`",
            parse_mode="Markdown"
        )


@router.message(Command("rules"))
async def cmd_rules(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("📜 Este comando está pensado para grupos.")
        return

    settings = await get_settings(message.chat.id)
    await message.reply(settings["rules_text"])


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("📊 Este comando solo funciona en grupos.")
        return

    settings = await get_settings(message.chat.id)
    stats = await get_group_stats(message.chat.id)

    text = (
        "📊 Estadísticas del grupo\n\n"
        f"🔗 Anti-link: {'ON' if settings['anti_link'] else 'OFF'}\n"
        f"⚡ Antiflood: {'ON' if settings['antiflood'] else 'OFF'}\n"
        f"🛡 Captcha: {'ON' if settings['captcha_enabled'] else 'OFF'}\n"
        f"🚨 Límite de warns: {settings['warn_limit']}\n"
        f"🔇 Auto mute: {settings['auto_mute_minutes']} min\n"
        f"🧹 Palabras bloqueadas: {stats['bad_words_count']}\n"
        f"👥 Usuarios con warns: {stats['warned_users_count']}\n"
        f"🧾 Logs registrados: {stats['logs_count']}"
    )
    await message.reply(text)