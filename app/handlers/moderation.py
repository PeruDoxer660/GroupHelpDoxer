from collections import defaultdict
from time import time

from aiogram import Router, F
from aiogram.types import Message, ChatMemberUpdated, ChatPermissions, CallbackQuery
from aiogram.enums import ChatMemberStatus
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import DEFAULT_CAPTCHA_TIMEOUT_MINUTES
from app.services.database import (
    get_settings,
    get_bad_words,
    add_warn,
    add_log,
    create_or_update_captcha,
    get_captcha,
    verify_captcha,
    delete_captcha,
)
from app.services.filters import (
    contains_link,
    contains_bad_word,
    is_admin,
    generate_captcha,
    future_iso_minutes,
    is_expired,
    mute_until,
    full_unrestrict_permissions,
)

router = Router()

FLOOD_CACHE = defaultdict(list)


def captcha_keyboard(user_id: int, options: list[str]):
    builder = InlineKeyboardBuilder()
    for option in options:
        builder.button(
            text=option,
            callback_data=f"captcha:{user_id}:{option}"
        )
    builder.adjust(3)
    return builder.as_markup()


@router.chat_member()
async def on_user_join(event: ChatMemberUpdated):
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    joined = (
        old_status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}
        and new_status in {ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED}
    )

    if not joined:
        return

    user = event.new_chat_member.user
    settings = await get_settings(event.chat.id)

    if settings["captcha_enabled"]:
        question, answer, options = generate_captcha()
        expires_at = future_iso_minutes(DEFAULT_CAPTCHA_TIMEOUT_MINUTES)

        await create_or_update_captcha(
            chat_id=event.chat.id,
            user_id=user.id,
            question=question,
            answer=answer,
            expires_at=expires_at
        )

        try:
            await event.bot.restrict_chat_member(
                chat_id=event.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
        except Exception:
            pass

        await add_log(
            event.chat.id,
            "CAPTCHA_CREATED",
            user_id=user.id,
            reason=f"question={question}"
        )

        await event.bot.send_message(
            event.chat.id,
            (
                f"🛡 Verificación para {user.full_name}\n\n"
                f"Resuelve este captcha tocando un botón:\n"
                f"👉 {question}\n\n"
                f"Tienes {DEFAULT_CAPTCHA_TIMEOUT_MINUTES} minutos."
            ),
            reply_markup=captcha_keyboard(user.id, options)
        )
        return

    welcome_text = settings["welcome_text"].replace("{name}", user.full_name)
    await add_log(event.chat.id, "USER_JOIN", user_id=user.id)
    await event.bot.send_message(event.chat.id, welcome_text)


@router.callback_query(F.data.startswith("captcha:"))
async def captcha_callback(callback: CallbackQuery):
    if not callback.message or not callback.from_user:
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Captcha inválido.", show_alert=True)
        return

    target_user_id = int(parts[1])
    selected_answer = parts[2]
    chat_id = callback.message.chat.id

    if callback.from_user.id != target_user_id:
        await callback.answer("Este captcha no es para ti.", show_alert=True)
        return

    captcha = await get_captcha(chat_id, callback.from_user.id)
    if not captcha:
        await callback.answer("No tienes captcha pendiente.", show_alert=True)
        return

    if captcha["verified"]:
        await callback.answer("Ya estás verificado.")
        return

    if is_expired(captcha["expires_at"]):
        try:
            await callback.bot.ban_chat_member(chat_id, callback.from_user.id)
            await callback.bot.unban_chat_member(chat_id, callback.from_user.id, only_if_banned=True)
        except Exception:
            pass

        await delete_captcha(chat_id, callback.from_user.id)
        await add_log(chat_id, "CAPTCHA_EXPIRED", user_id=callback.from_user.id)

        try:
            await callback.message.edit_text(
                f"⌛ El captcha de {callback.from_user.full_name} expiró."
            )
        except Exception:
            pass

        await callback.answer("Tu captcha expiró.", show_alert=True)
        return

    if selected_answer != captcha["answer"]:
        await add_log(chat_id, "CAPTCHA_FAILED", user_id=callback.from_user.id, reason=f"answer={selected_answer}")
        await callback.answer("❌ Respuesta incorrecta. Prueba otra vez.", show_alert=True)
        return

    await verify_captcha(chat_id, callback.from_user.id)
    await delete_captcha(chat_id, callback.from_user.id)

    try:
        await callback.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=callback.from_user.id,
            permissions=full_unrestrict_permissions(),
        )
    except Exception:
        pass

    settings = await get_settings(chat_id)
    welcome_text = settings["welcome_text"].replace("{name}", callback.from_user.full_name)

    await add_log(chat_id, "CAPTCHA_VERIFIED", user_id=callback.from_user.id)

    try:
        await callback.message.edit_text(
            f"✅ {callback.from_user.full_name} verificado correctamente."
        )
    except Exception:
        pass

    await callback.answer("Verificación completada")
    await callback.message.answer(welcome_text)


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def moderate_messages(message: Message):
    if not message.from_user:
        return

    if await is_admin(message.bot, message.chat.id, message.from_user.id):
        return

    text = message.text or message.caption or ""
    settings = await get_settings(message.chat.id)

    if settings["anti_link"] and contains_link(text):
        try:
            await message.delete()
        except Exception:
            pass

        warns = await add_warn(message.chat.id, message.from_user.id)
        await add_log(
            message.chat.id,
            "DELETE_LINK",
            user_id=message.from_user.id,
            reason=f"warns={warns}"
        )

        if warns >= settings["warn_limit"]:
            try:
                await message.bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until(settings["auto_mute_minutes"])
                )
            except Exception:
                pass

            await add_log(
                message.chat.id,
                "AUTO_MUTE_BY_LINK_WARNS",
                user_id=message.from_user.id,
                reason=f"{settings['auto_mute_minutes']} min"
            )

            await message.answer(
                f"🚫 {message.from_user.full_name}, no se permiten enlaces.\n"
                f"Has llegado al límite de warns y quedas silenciado por "
                f"{settings['auto_mute_minutes']} minutos."
            )
            return

        await message.answer(
            f"🚫 {message.from_user.full_name}, no se permiten enlaces.\n"
            f"Warns actuales: {warns}"
        )
        return

    bad_words = await get_bad_words(message.chat.id)
    matched = contains_bad_word(text, bad_words)

    if matched:
        try:
            await message.delete()
        except Exception:
            pass

        warns = await add_warn(message.chat.id, message.from_user.id)
        await add_log(
            message.chat.id,
            "DELETE_BAD_WORD",
            user_id=message.from_user.id,
            reason=f"word={matched} | warns={warns}"
        )

        if warns >= settings["warn_limit"]:
            try:
                await message.bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until(settings["auto_mute_minutes"])
                )
            except Exception:
                pass

            await add_log(
                message.chat.id,
                "AUTO_MUTE_BY_BAD_WORD_WARNS",
                user_id=message.from_user.id,
                reason=f"{settings['auto_mute_minutes']} min"
            )

            await message.answer(
                f"🧹 {message.from_user.full_name}, mensaje eliminado por palabra prohibida: {matched}.\n"
                f"Has llegado al límite de warns y quedas silenciado por "
                f"{settings['auto_mute_minutes']} minutos."
            )
            return

        await message.answer(
            f"🧹 {message.from_user.full_name}, mensaje eliminado por palabra prohibida: {matched}.\n"
            f"Warns actuales: {warns}"
        )
        return

    if settings["antiflood"]:
        key = f"{message.chat.id}:{message.from_user.id}"
        now = time()

        FLOOD_CACHE[key].append(now)
        window = settings["flood_window_seconds"]
        FLOOD_CACHE[key] = [t for t in FLOOD_CACHE[key] if now - t <= window]

        if len(FLOOD_CACHE[key]) > settings["flood_max_messages"]:
            try:
                await message.delete()
            except Exception:
                pass

            warns = await add_warn(message.chat.id, message.from_user.id)
            await add_log(
                message.chat.id,
                "FLOOD_DETECTED",
                user_id=message.from_user.id,
                reason=f"warns={warns}"
            )

            try:
                await message.bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=mute_until(1)
                )
            except Exception:
                pass

            if warns >= settings["warn_limit"]:
                try:
                    await message.bot.restrict_chat_member(
                        chat_id=message.chat.id,
                        user_id=message.from_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=mute_until(settings["auto_mute_minutes"])
                    )
                except Exception:
                    pass

                await add_log(
                    message.chat.id,
                    "AUTO_MUTE_BY_FLOOD_WARNS",
                    user_id=message.from_user.id,
                    reason=f"{settings['auto_mute_minutes']} min"
                )

                await message.answer(
                    f"⚡ {message.from_user.full_name}, flood detectado.\n"
                    f"Has llegado al límite de warns y quedas silenciado por "
                    f"{settings['auto_mute_minutes']} minutos."
                )
                return

            await message.answer(
                f"⚠️ {message.from_user.full_name}, baja la velocidad.\n"
                f"Flood detectado. Warns actuales: {warns}"
            )