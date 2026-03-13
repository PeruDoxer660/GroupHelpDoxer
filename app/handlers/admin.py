from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, ChatPermissions, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.database import (
    get_settings,
    get_bad_words,
    set_anti_link,
    set_antiflood,
    set_captcha_enabled,
    set_warn_limit,
    set_auto_mute_minutes,
    set_flood_limit,
    set_welcome_text,
    set_rules_text,
    add_bad_word,
    del_bad_word,
    add_warn,
    remove_warn,
    get_warns,
    reset_warns,
    get_logs,
    add_log,
)
from app.services.filters import (
    is_admin,
    parse_duration_to_minutes,
    mute_until,
    parse_int,
    full_unrestrict_permissions,
)

router = Router()


async def require_admin(message: Message, bot) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Este comando solo funciona en grupos.")
        return False

    if not message.from_user:
        return False

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("⛔ Solo los administradores pueden usar este comando.")
        return False

    return True


async def require_admin_callback(callback: CallbackQuery) -> bool:
    if not callback.message or not callback.from_user:
        return False

    if not await is_admin(callback.bot, callback.message.chat.id, callback.from_user.id):
        await callback.answer("Solo admins.", show_alert=True)
        return False

    return True


def get_target_user(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None


def extract_user_id_from_args(args: str | None):
    if not args:
        return None

    raw = args.strip()
    if raw.startswith("@"):
        return None

    try:
        return int(raw)
    except Exception:
        return None


def panel_keyboard(settings: dict):
    builder = InlineKeyboardBuilder()

    builder.button(
        text=f"🔗 Anti-link: {'ON' if settings['anti_link'] else 'OFF'}",
        callback_data="panel:toggle_antilink"
    )
    builder.button(
        text=f"⚡ Antiflood: {'ON' if settings['antiflood'] else 'OFF'}",
        callback_data="panel:toggle_antiflood"
    )
    builder.button(
        text=f"🛡 Captcha: {'ON' if settings['captcha_enabled'] else 'OFF'}",
        callback_data="panel:toggle_captcha"
    )
    builder.button(
        text="🔄 Actualizar",
        callback_data="panel:refresh"
    )

    builder.adjust(1)
    return builder.as_markup()


def format_settings_text(settings: dict, bad_words: list[str]) -> str:
    return (
        "⚙️ Panel de configuración del grupo\n\n"
        f"🔗 Anti-link: {'ON' if settings['anti_link'] else 'OFF'}\n"
        f"⚡ Antiflood: {'ON' if settings['antiflood'] else 'OFF'}\n"
        f"🛡 Captcha: {'ON' if settings['captcha_enabled'] else 'OFF'}\n"
        f"🚨 Límite de warns: {settings['warn_limit']}\n"
        f"🔇 Auto mute: {settings['auto_mute_minutes']} min\n"
        f"📨 Flood: {settings['flood_max_messages']} mensajes / {settings['flood_window_seconds']} seg\n"
        f"👋 Bienvenida: {settings['welcome_text']}\n"
        f"📜 Reglas: {settings['rules_text']}\n"
        f"🧹 Palabras bloqueadas: {', '.join(bad_words) if bad_words else 'ninguna'}\n\n"
        "Usa los botones para activar o desactivar funciones rápidas."
    )


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        await message.reply("❌ Este comando solo funciona en grupos.")
        return

    settings = await get_settings(message.chat.id)
    bad_words = await get_bad_words(message.chat.id)
    await message.reply(format_settings_text(settings, bad_words))


@router.message(Command("panel"))
@router.message(Command("menu"))
async def cmd_panel(message: Message):
    if not await require_admin(message, message.bot):
        return

    settings = await get_settings(message.chat.id)
    bad_words = await get_bad_words(message.chat.id)

    await message.reply(
        format_settings_text(settings, bad_words),
        reply_markup=panel_keyboard(settings)
    )


@router.callback_query(F.data.startswith("panel:"))
async def panel_callbacks(callback: CallbackQuery):
    if not await require_admin_callback(callback):
        return

    if not callback.message:
        return

    action = callback.data.split(":", 1)[1]
    chat_id = callback.message.chat.id
    settings = await get_settings(chat_id)

    if action == "toggle_antilink":
        new_value = not settings["anti_link"]
        await set_anti_link(chat_id, new_value)
        await add_log(chat_id, "SET_ANTILINK", admin_id=callback.from_user.id, reason=f"anti_link={new_value}")
        await callback.answer(f"Anti-link {'ON' if new_value else 'OFF'}")

    elif action == "toggle_antiflood":
        new_value = not settings["antiflood"]
        await set_antiflood(chat_id, new_value)
        await add_log(chat_id, "SET_ANTIFLOOD", admin_id=callback.from_user.id, reason=f"antiflood={new_value}")
        await callback.answer(f"Antiflood {'ON' if new_value else 'OFF'}")

    elif action == "toggle_captcha":
        new_value = not settings["captcha_enabled"]
        await set_captcha_enabled(chat_id, new_value)
        await add_log(chat_id, "SET_CAPTCHA", admin_id=callback.from_user.id, reason=f"captcha={new_value}")
        await callback.answer(f"Captcha {'ON' if new_value else 'OFF'}")

    elif action == "refresh":
        await callback.answer("Panel actualizado")

    settings = await get_settings(chat_id)
    bad_words = await get_bad_words(chat_id)

    try:
        await callback.message.edit_text(
            format_settings_text(settings, bad_words),
            reply_markup=panel_keyboard(settings)
        )
    except Exception:
        pass


@router.message(Command("antilink"))
async def cmd_antilink(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args or command.args.lower() not in ("on", "off"):
        await message.reply("Uso: /antilink on o /antilink off")
        return

    enabled = command.args.lower() == "on"
    await set_anti_link(message.chat.id, enabled)
    await add_log(message.chat.id, "SET_ANTILINK", admin_id=message.from_user.id, reason=f"anti_link={enabled}")
    await message.reply(f"✅ Anti-link {'activado' if enabled else 'desactivado'}.")


@router.message(Command("antiflood"))
async def cmd_antiflood(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args or command.args.lower() not in ("on", "off"):
        await message.reply("Uso: /antiflood on o /antiflood off")
        return

    enabled = command.args.lower() == "on"
    await set_antiflood(message.chat.id, enabled)
    await add_log(message.chat.id, "SET_ANTIFLOOD", admin_id=message.from_user.id, reason=f"antiflood={enabled}")
    await message.reply(f"✅ Antiflood {'activado' if enabled else 'desactivado'}.")


@router.message(Command("captcha"))
async def cmd_captcha(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args or command.args.lower() not in ("on", "off"):
        await message.reply("Uso: /captcha on o /captcha off")
        return

    enabled = command.args.lower() == "on"
    await set_captcha_enabled(message.chat.id, enabled)
    await add_log(message.chat.id, "SET_CAPTCHA", admin_id=message.from_user.id, reason=f"captcha={enabled}")
    await message.reply(f"✅ Captcha {'activado' if enabled else 'desactivado'}.")


@router.message(Command("setwarnlimit"))
async def cmd_setwarnlimit(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /setwarnlimit 3")
        return

    value = parse_int(command.args, minimum=1, maximum=20)
    if value is None:
        await message.reply("❌ Número inválido. Usa un valor entre 1 y 20.")
        return

    await set_warn_limit(message.chat.id, value)
    await add_log(message.chat.id, "SET_WARN_LIMIT", admin_id=message.from_user.id, reason=f"warn_limit={value}")
    await message.reply(f"✅ Nuevo límite de warns: {value}")


@router.message(Command("setautomute"))
async def cmd_setautomute(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /setautomute 60")
        return

    value = parse_int(command.args, minimum=1, maximum=10080)
    if value is None:
        await message.reply("❌ Número inválido. Usa minutos entre 1 y 10080.")
        return

    await set_auto_mute_minutes(message.chat.id, value)
    await add_log(message.chat.id, "SET_AUTO_MUTE", admin_id=message.from_user.id, reason=f"minutes={value}")
    await message.reply(f"✅ Auto mute configurado en {value} minutos.")


@router.message(Command("setflood"))
async def cmd_setflood(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /setflood 5 10")
        return

    parts = command.args.split()
    if len(parts) != 2:
        await message.reply("Uso: /setflood 5 10")
        return

    max_messages = parse_int(parts[0], minimum=2, maximum=50)
    window_seconds = parse_int(parts[1], minimum=2, maximum=120)

    if max_messages is None or window_seconds is None:
        await message.reply("❌ Valores inválidos. Ejemplo válido: /setflood 5 10")
        return

    await set_flood_limit(message.chat.id, max_messages, window_seconds)
    await add_log(
        message.chat.id,
        "SET_FLOOD_LIMIT",
        admin_id=message.from_user.id,
        reason=f"{max_messages} mensajes / {window_seconds} seg"
    )
    await message.reply(f"✅ Flood configurado: {max_messages} mensajes en {window_seconds} segundos.")


@router.message(Command("setwelcome"))
async def cmd_setwelcome(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /setwelcome Bienvenido {name}")
        return

    await set_welcome_text(message.chat.id, command.args.strip())
    await add_log(message.chat.id, "SET_WELCOME", admin_id=message.from_user.id)
    await message.reply("✅ Mensaje de bienvenida actualizado.")


@router.message(Command("setrules"))
async def cmd_setrules(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /setrules Regla 1... Regla 2...")
        return

    await set_rules_text(message.chat.id, command.args.strip())
    await add_log(message.chat.id, "SET_RULES", admin_id=message.from_user.id)
    await message.reply("✅ Reglas actualizadas.")


@router.message(Command("addbadword"))
async def cmd_addbadword(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /addbadword palabra")
        return

    word = command.args.strip().lower()
    await add_bad_word(message.chat.id, word)
    await add_log(message.chat.id, "ADD_BAD_WORD", admin_id=message.from_user.id, reason=word)
    await message.reply(f"✅ Palabra bloqueada agregada: {word}")


@router.message(Command("delbadword"))
async def cmd_delbadword(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    if not command.args:
        await message.reply("Uso: /delbadword palabra")
        return

    word = command.args.strip().lower()
    await del_bad_word(message.chat.id, word)
    await add_log(message.chat.id, "DEL_BAD_WORD", admin_id=message.from_user.id, reason=word)
    await message.reply(f"✅ Palabra bloqueada eliminada: {word}")


@router.message(Command("warn"))
async def cmd_warn(message: Message):
    if not await require_admin(message, message.bot):
        return

    user = get_target_user(message)
    if not user:
        await message.reply("Responde al usuario que quieres advertir.")
        return

    if await is_admin(message.bot, message.chat.id, user.id):
        await message.reply("⛔ No puedo advertir a otro administrador.")
        return

    settings = await get_settings(message.chat.id)
    warns = await add_warn(message.chat.id, user.id)

    await add_log(
        message.chat.id,
        "WARN",
        user_id=user.id,
        admin_id=message.from_user.id,
        reason=f"warns={warns}"
    )

    if warns >= settings["warn_limit"]:
        await message.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=mute_until(settings["auto_mute_minutes"])
        )

        await add_log(
            message.chat.id,
            "AUTO_MUTE_BY_WARNS",
            user_id=user.id,
            admin_id=message.from_user.id,
            reason=f"{settings['auto_mute_minutes']} min"
        )

        await message.reply(
            f"🚨 {user.full_name} ahora tiene {warns} warn(s) y fue silenciado automáticamente "
            f"por {settings['auto_mute_minutes']} minutos."
        )
        return

    await message.reply(f"⚠️ {user.full_name} ahora tiene {warns} warn(s).")


@router.message(Command("unwarn"))
async def cmd_unwarn(message: Message):
    if not await require_admin(message, message.bot):
        return

    user = get_target_user(message)
    if not user:
        await message.reply("Responde al usuario.")
        return

    warns = await remove_warn(message.chat.id, user.id)
    await add_log(
        message.chat.id,
        "UNWARN",
        user_id=user.id,
        admin_id=message.from_user.id,
        reason=f"warns={warns}"
    )
    await message.reply(f"✅ {user.full_name} ahora tiene {warns} warn(s).")


@router.message(Command("warns"))
async def cmd_warns(message: Message):
    if not await require_admin(message, message.bot):
        return

    user = get_target_user(message)
    if not user:
        await message.reply("Responde al usuario.")
        return

    warns = await get_warns(message.chat.id, user.id)
    await message.reply(f"📌 {user.full_name} tiene {warns} warn(s).")


@router.message(Command("clearwarns"))
async def cmd_clearwarns(message: Message):
    if not await require_admin(message, message.bot):
        return

    user = get_target_user(message)
    if not user:
        await message.reply("Responde al usuario.")
        return

    await reset_warns(message.chat.id, user.id)
    await add_log(message.chat.id, "CLEAR_WARNS", user_id=user.id, admin_id=message.from_user.id)
    await message.reply(f"✅ Warns reiniciados para {user.full_name}.")


@router.message(Command("mute"))
async def cmd_mute(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    user = get_target_user(message)
    if not user:
        await message.reply("Responde al usuario que quieres silenciar.")
        return

    if await is_admin(message.bot, message.chat.id, user.id):
        await message.reply("⛔ No puedo silenciar a otro administrador.")
        return

    if not command.args:
        await message.reply("Uso: /mute 10m o /mute 1h o /mute 1d")
        return

    minutes = parse_duration_to_minutes(command.args)
    if minutes is None:
        await message.reply("❌ Formato inválido. Usa por ejemplo: /mute 10m")
        return

    await message.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=user.id,
        permissions=ChatPermissions(can_send_messages=False),
        until_date=mute_until(minutes)
    )

    await add_log(
        message.chat.id,
        "MUTE",
        user_id=user.id,
        admin_id=message.from_user.id,
        reason=f"{minutes} min"
    )

    await message.reply(f"🔇 {user.full_name} fue silenciado por {command.args}.")


@router.message(Command("unmute"))
async def cmd_unmute(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    target_user = get_target_user(message)
    target_user_id = target_user.id if target_user else extract_user_id_from_args(command.args)
    target_name = target_user.full_name if target_user else str(target_user_id)

    if not target_user_id:
        await message.reply("Uso: responde al usuario con /unmute o usa /unmute 123456789")
        return

    await message.bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=target_user_id,
        permissions=full_unrestrict_permissions()
    )

    await add_log(
        message.chat.id,
        "UNMUTE",
        user_id=target_user_id,
        admin_id=message.from_user.id
    )

    await message.reply(f"🔊 Usuario desmuteado: {target_name}")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not await require_admin(message, message.bot):
        return

    user = get_target_user(message)
    if not user:
        await message.reply("Responde al usuario que quieres banear.")
        return

    if await is_admin(message.bot, message.chat.id, user.id):
        await message.reply("⛔ No puedo banear a otro administrador.")
        return

    await message.bot.ban_chat_member(message.chat.id, user.id)
    await add_log(message.chat.id, "BAN", user_id=user.id, admin_id=message.from_user.id)
    await message.reply(f"⛔ {user.full_name} fue baneado.")


@router.message(Command("unban"))
async def cmd_unban(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    user_id = extract_user_id_from_args(command.args)
    if not user_id:
        await message.reply("Uso: /unban 123456789")
        return

    await message.bot.unban_chat_member(message.chat.id, user_id, only_if_banned=True)
    await add_log(message.chat.id, "UNBAN", user_id=user_id, admin_id=message.from_user.id)
    await message.reply(f"✅ Usuario desbaneado: {user_id}")


@router.message(Command("logs"))
async def cmd_logs(message: Message, command: CommandObject):
    if not await require_admin(message, message.bot):
        return

    limit = 10
    if command.args:
        maybe_limit = parse_int(command.args, minimum=1, maximum=30)
        if maybe_limit is None:
            await message.reply("Uso: /logs o /logs 10")
            return
        limit = maybe_limit

    logs = await get_logs(message.chat.id, limit=limit)
    if not logs:
        await message.reply("📝 No hay logs todavía.")
        return

    lines = []
    for row in logs:
        user_id, admin_id, action, reason, created_at = row
        line = f"• [{created_at}] {action}"
        if user_id:
            line += f" | user: {user_id}"
        if admin_id:
            line += f" | admin: {admin_id}"
        if reason:
            line += f" | {reason}"
        lines.append(line)

    await message.reply("🧾 Últimos logs:\n\n" + "\n".join(lines))