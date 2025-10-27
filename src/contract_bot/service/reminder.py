from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from logging import Logger
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from zoneinfo import ZoneInfo

from contract_bot.config import AppConfig
from contract_bot.contracts.documents import DocumentContext, DocumentGenerator
from contract_bot.contracts.parser import ContractRecord, DocumentType, parse_contracts
from contract_bot.storage.file_repository import FileRepository
from contract_bot.storage.state_store import StateStore
from contract_bot.integrations.yadisk import YandexDiskClient


@dataclass
class ReminderResult:
    processed: int = 0
    notified: int = 0
    skipped: int = 0


class ReminderService:
    def __init__(
        self,
        config: AppConfig,
        bot: Bot,
        file_repository: FileRepository,
        document_generator: DocumentGenerator,
        state_store: StateStore,
        logger: Logger,
        yadisk_client: YandexDiskClient | None = None,
    ) -> None:
        self._config = config
        self._bot = bot
        self._file_repository = file_repository
        self._document_generator = document_generator
        self._state_store = state_store
        self._logger = logger
        self._timezone = ZoneInfo(config.scheduler.timezone)
        self._yadisk = yadisk_client
        self._reminder_days = config.scheduler.reminder_days

    @property
    def reminder_days(self) -> int:
        return self._reminder_days

    def update_reminder_days(self, days: int) -> None:
        if days <= 0:
            return
        if days != self._reminder_days:
            self._reminder_days = days
            self._logger.info("Горизонт напоминаний обновлён: %s дн.", days)

    async def run(self, *, force: bool = False) -> ReminderResult:
        latest = self._file_repository.get_latest()
        if not latest:
            self._logger.info("Нет загруженного Excel. Напоминания пропущены.")
            return ReminderResult()

        records = await asyncio.to_thread(parse_contracts, Path(latest))
        now = datetime.now(tz=self._timezone).date()
        reminder_days = self._reminder_days
        chats = self._state_store.get_chats()
        result = ReminderResult(processed=len(records))

        if not chats:
            self._logger.info("Нет зарегистрированных чатов для отправки уведомлений.")
            return result

        for record in records:
            if not record.end_date:
                result.skipped += 1
                continue

            mark = (record.readiness_mark or "").strip().upper()
            # временно игнорируем отметки, чтобы проверка всегда шла
            # if not force and mark in {"П", "Н", "Д", "И"}:
            #     self._logger.debug(
            #         "Запись %s помечена как обработанная (отметка %s), пропускаю",
            #         record.employee,
            #         mark,
            #     )
            #     result.skipped += 1
            #     continue

            days_left = (record.end_date - now).days
            if days_left < 0:
                result.skipped += 1
                continue
            if days_left > reminder_days:
                continue

            doc_type = record.decide_document()
            doc_types = [doc_type] if doc_type is not None else [DocumentType.EXTENSION, DocumentType.TERMINATION]

            for current_type in doc_types:
                notification_key = f"{record.employee}|{record.end_date.isoformat()}|{current_type.value}"

                for chat in chats:
                    if not force and self._state_store.has_notification(chat.chat_id, notification_key):
                        self._logger.debug("Уведомление уже отправлялось для %s", notification_key)
                        continue

                    await self._send_notification(chat.chat_id, record, current_type, notification_key, days_left)
                    result.notified += 1

        return result

    async def _send_notification(
        self,
        chat_id: int,
        record: ContractRecord,
        doc_type: DocumentType,
        notification_key: str,
        days_left: int,
    ) -> None:
        document_path = await asyncio.to_thread(
            self._document_generator.render,
            record,
            DocumentContext(record=record),
            doc_type,
        )

        link = None
        if self._yadisk and self._yadisk.enabled:
            try:
                link = await self._yadisk.upload(document_path)
            except NotImplementedError:
                self._logger.debug("Загрузка на Яндекс.Диск ещё не реализована")

        caption = self._build_caption(record, days_left, doc_type, link)
        file = FSInputFile(document_path)

        await self._bot.send_document(chat_id=chat_id, document=file, caption=caption)
        self._state_store.mark_notification(chat_id, notification_key)
        self._logger.info("Отправлено уведомление %s чату %s", notification_key, chat_id)

    def _build_caption(
        self,
        record: ContractRecord,
        days_left: int,
        doc_type: DocumentType,
        link: str | None = None,
    ) -> str:
        end_date = record.end_date.strftime("%d.%m.%Y") if record.end_date else "?"
        action = "продление" if doc_type is DocumentType.EXTENSION else "увольнение"
        mark = (record.readiness_mark or "").strip().upper()
        if mark == "И":
            action = "иное"
        parts = [
            f"*Организация:* {record.organization or '—'}",
            f"*Сотрудник:* {record.employee}",
            f"*Действие:* *{action.upper()}*",
            f"*Контракт до:* {end_date} (осталось {days_left} дн.)",
        ]
        if record.notification_label:
            label = record.notification_label
            if isinstance(label, str) and label.startswith("#"):
                label = "Ошибка в формуле"
            parts.append(f"Статус в таблице: {label}")
        if link:
            parts.append(f"Файл на диске: {link}")
        return "\n".join(parts)
