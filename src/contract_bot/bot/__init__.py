from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from contract_bot.bot.handlers import BotDependencies, create_dispatcher
from contract_bot.config import AppConfig
from contract_bot.storage.file_repository import FileRepository
from contract_bot.storage.state_store import StateStore


def build_bot(
    config: AppConfig,
    state_store: StateStore,
    file_repository: FileRepository,
) -> tuple[Bot, Dispatcher, BotDependencies]:
    bot = Bot(
        token=config.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    deps = BotDependencies(
        config=config,
        state_store=state_store,
        file_repository=file_repository,
    )
    dispatcher = create_dispatcher(deps)
    return bot, dispatcher, deps
