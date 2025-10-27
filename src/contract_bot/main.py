from __future__ import annotations

import asyncio
from logging import Logger

from aiogram.types import BotCommand

from contract_bot.bot import build_bot
from contract_bot.config import AppConfig
from contract_bot.contracts.documents import DocumentGenerator
from contract_bot.integrations.yadisk import YandexDiskClient
from contract_bot.logging_setup import setup_logging
from contract_bot.service.reminder import ReminderService
from contract_bot.service.scheduler import Scheduler
from contract_bot.service.sheet_sync import SheetSyncService
from contract_bot.storage import create_file_repository, create_state_store


async def _run_async() -> None:
    config = AppConfig.load()
    logger = setup_logging(config.logging.level)

    state_store = create_state_store(config.paths.state_file)
    file_repo = create_file_repository(config.paths.files_dir)
    document_generator = DocumentGenerator(config.paths.templates_dir, config.paths.generated_dir)
    yadisk_client = YandexDiskClient(config.integrations.yadisk_token)

    sheet_sync = SheetSyncService(
        config=config,
        file_repository=file_repo,
        state_store=state_store,
        logger=logger,
    )

    bot, dispatcher, deps = build_bot(config, state_store, file_repo)

    reminder_service = ReminderService(
        config=config,
        bot=bot,
        file_repository=file_repo,
        document_generator=document_generator,
        state_store=state_store,
        logger=logger,
        yadisk_client=yadisk_client,
    )
    sheet_sync.set_reminder_service(reminder_service)
    deps.reminder_service = reminder_service
    deps.sheet_sync = sheet_sync

    await sheet_sync.sync(force=True)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить бота"),
            BotCommand(command="status", description="Проверить последнюю загрузку"),
            BotCommand(command="help", description="Справка по командам"),
            BotCommand(command="run", description="Запустить проверку вручную"),
            BotCommand(command="run_force", description="Принудительно отправить уведомления"),
        ]
    )

    scheduler = Scheduler(
        config=config,
        reminder_service=reminder_service,
        sheet_sync=sheet_sync,
        logger=logger,
    )
    scheduler.start()

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown()


def main() -> None:
    asyncio.run(_run_async())


if __name__ == "__main__":
    main()
