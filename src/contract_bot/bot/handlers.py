from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Optional

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from zoneinfo import ZoneInfo

from contract_bot.config import AppConfig
from contract_bot.service.reminder import ReminderService
from contract_bot.service.sheet_sync import SheetSyncService
from contract_bot.storage.file_repository import FileRepository
from contract_bot.storage.state_store import StateStore
from contract_bot.utils.text import humanize_filename


@dataclass
class BotDependencies:
    config: AppConfig
    state_store: StateStore
    file_repository: FileRepository
    reminder_service: Optional[ReminderService] = None
    sheet_sync: Optional[SheetSyncService] = None


class UploadState:
    waiting_for_file = "waiting_for_file"


MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/status"), KeyboardButton(text="/sync")],
        [KeyboardButton(text="/run"), KeyboardButton(text="/run_force")],
        [KeyboardButton(text="/help")],
    ],
    resize_keyboard=True,
)


def create_dispatcher(deps: BotDependencies) -> Dispatcher:
    router = Router(name="main")
    storage = MemoryStorage()
    dispatcher = Dispatcher(storage=storage)

    @router.message(CommandStart())
    async def handle_start(message: Message, bot: Bot) -> None:
        if not _is_authorized(message.chat.id, deps):
            await message.answer(
                "Извините, доступ к боту ограничен. Свяжитесь с администратором, чтобы получить разрешение."
            )
            return

        deps.state_store.register_chat(message.chat.id)
        await message.answer(
            "Здравствуйте! Я помогу контролировать сроки контрактов. Используйте меню или команды `/status`, `/sync`, `/run`, `/run_force`, `/help`.",
            reply_markup=MAIN_MENU,
        )

    @router.message(Command("status"))
    async def handle_status(message: Message) -> None:
        if not _is_authorized(message.chat.id, deps):
            await message.answer(
                "Ваш аккаунт пока не авторизован. Для доступа свяжитесь с администратором."
            )
            return

        chat_state = deps.state_store.get_chat(message.chat.id)
        if chat_state is None or chat_state.last_upload_at is None:
            await message.answer(
                "В системе ещё нет актуального файла. Синхронизация с Google Sheets пока не выполнялась."
            )
            return

        tz = ZoneInfo(deps.config.scheduler.timezone)
        last_upload = chat_state.last_upload_at
        if last_upload.tzinfo is None:
            last_upload = last_upload.replace(tzinfo=timezone.utc)
        local_time = last_upload.astimezone(tz)
        display_name = humanize_filename(chat_state.last_file_name)
        tz_label = local_time.tzname()
        if not tz_label or tz_label.startswith('+'):
            offset_hours = int(local_time.utcoffset().total_seconds() // 3600)
            tz_label = f"UTC{offset_hours:+d}"

        lines = [
            "Последняя загрузка: {time}".format(
                time=local_time.strftime("%d.%m.%Y %H:%M") + f" ({tz_label})",
            ),
            "Имя файла: {name}".format(name=display_name),
        ]
        if deps.reminder_service:
            lines.append(
                "Горизонт напоминаний: {days} дн.".format(
                    days=deps.reminder_service.reminder_days,
                )
            )
        await message.answer("\n".join(lines))

    @router.message(Command("help"))
    async def handle_help(message: Message) -> None:
        if not _is_authorized(message.chat.id, deps):
            await message.answer(
                "Ваш аккаунт пока не авторизован. Для доступа свяжитесь с администратором."
            )
            return

        await message.answer(
            "Доступные команды:\n"
            "• `/status` — посмотреть дату и имя последней загрузки.\n"
            "• `/sync` — принудительно синхронизировать Google Sheet.\n"
            "• `/run` — запустить проверку и рассылку по расписанию (без повторов).\n"
            "• `/run_force` — запустить проверку и отправить документы повторно.\n"
            "• `/help` — показать справку по командам.",
            reply_markup=MAIN_MENU,
        )

    @router.message(Command("sync"))
    async def handle_sync(message: Message) -> None:
        if not _is_authorized(message.chat.id, deps):
            await message.answer(
                "Ваш аккаунт пока не авторизован. Для доступа свяжитесь с администратором."
            )
            return

        if not deps.sheet_sync or not deps.sheet_sync.enabled:
            await message.answer("Автосинхронизация с Google Sheets не настроена.")
            return

        await message.answer("Запускаю синхронизацию с Google Sheets. Пожалуйста, подождите...")
        synced = await deps.sheet_sync.sync(force=True)
        if synced:
            await message.answer("Синхронизация завершена успешно."
                                 " Проверьте `/status`, чтобы убедиться в обновлении файла.")
        else:
            await message.answer("Не удалось обновить данные из Google Sheets. Проверьте доступ и попробуйте позже.")

    @router.message(Command("run"))
    async def handle_run(message: Message) -> None:
        await _run_reminder(message, deps, force=False)

    @router.message(Command("run_force"))
    async def handle_run_force(message: Message) -> None:
        await _run_reminder(message, deps, force=True)

    dispatcher.include_router(router)
    return dispatcher


def _is_authorized(chat_id: int, deps: BotDependencies) -> bool:
    whitelist = deps.config.bot.chat_whitelist
    return not whitelist or chat_id in whitelist


async def _run_reminder(message: Message, deps: BotDependencies, force: bool) -> None:
    if not _is_authorized(message.chat.id, deps):
        await message.answer(
            "Ваш аккаунт пока не авторизован. Для доступа свяжитесь с администратором."
        )
        return

    if deps.reminder_service is None:
        await message.answer("Сервис напоминаний временно недоступен. Попробуйте позже.")
        return

    await message.answer("Запускаю проверку контрактов. Пожалуйста, подождите...")
    try:
        result = await deps.reminder_service.run(force=force)
    except Exception as exc:  # noqa: BLE001
        await message.answer(f"Во время проверки произошла ошибка: {exc}")
        return

    await message.answer(
        "Проверка завершена.\n"
        f"Обработано записей: {result.processed}.\n"
        f"Отправлено уведомлений: {result.notified}.\n"
        f"Пропущено: {result.skipped}."
    )
