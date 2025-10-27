from __future__ import annotations

from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError

load_dotenv()


class BotConfig(BaseModel):
    token: str = Field(alias="BOT_TOKEN")
    chat_whitelist: set[int] = Field(default_factory=set, alias="CHAT_WHITELIST")

    @staticmethod
    def _parse_chat_ids(raw: str | None) -> set[int]:
        if not raw:
            return set()
        items: Iterable[str] = (item.strip() for item in raw.split(","))
        return {int(item) for item in items if item}

    @classmethod
    def model_validate_env(cls) -> "BotConfig":
        from os import getenv

        raw_ids = getenv("CHAT_WHITELIST", "")
        return cls(
            BOT_TOKEN=getenv("BOT_TOKEN", ""),
            CHAT_WHITELIST=cls._parse_chat_ids(raw_ids),
        )


class PathsConfig(BaseModel):
    files_dir: Path = Field(default=Path("storage/contracts"), alias="FILES_DIR")
    generated_dir: Path = Field(default=Path("generated"), alias="GENERATED_DIR")
    templates_dir: Path = Field(default=Path("templates"), alias="TEMPLATES_DIR")
    meta_dir: Path = Field(default=Path("storage/meta"), alias="META_DIR")

    def ensure(self) -> None:
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.generated_dir.mkdir(parents=True, exist_ok=True)
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

    @property
    def state_file(self) -> Path:
        return self.meta_dir / "state.json"


class SchedulerConfig(BaseModel):
    reminder_days: int = Field(default=30, alias="REMINDER_DAYS")
    timezone: str = Field(default="Europe/Minsk", alias="TIMEZONE")


class LoggingConfig(BaseModel):
    level: str = Field(default="INFO", alias="LOG_LEVEL")


class IntegrationsConfig(BaseModel):
    yadisk_token: str | None = Field(default=None, alias="YADISK_TOKEN")
    google_sheet_id: str | None = Field(default=None, alias="GOOGLE_SHEET_ID")
    google_sheet_gid: str = Field(default="0", alias="GOOGLE_SHEET_GID")
    google_sheet_name: str = Field(default="Контроль", alias="GOOGLE_SHEET_NAME")
    google_sheet_filename: str = Field(
        default="Контроль окончания сроков действия контрактов.xlsx",
        alias="GOOGLE_SHEET_FILENAME",
    )
    sheet_sync_interval_minutes: int = Field(default=5, alias="SHEET_SYNC_INTERVAL_MINUTES")


class AppConfig(BaseModel):
    bot: BotConfig
    paths: PathsConfig
    scheduler: SchedulerConfig
    logging: LoggingConfig
    integrations: IntegrationsConfig

    @classmethod
    def load(cls) -> "AppConfig":
        from os import getenv

        try:
            bot = BotConfig.model_validate_env()
            if not bot.token:
                raise RuntimeError("BOT_TOKEN is required")

            paths = PathsConfig(
                FILES_DIR=Path(getenv("FILES_DIR", "storage/contracts")),
                GENERATED_DIR=Path(getenv("GENERATED_DIR", "generated")),
                TEMPLATES_DIR=Path(getenv("TEMPLATES_DIR", "templates")),
                META_DIR=Path(getenv("META_DIR", "storage/meta")),
            )

            scheduler = SchedulerConfig(
                REMINDER_DAYS=int(getenv("REMINDER_DAYS", "30")),
                TIMEZONE=getenv("TIMEZONE", "Europe/Minsk"),
            )

            logging = LoggingConfig(
                LOG_LEVEL=getenv("LOG_LEVEL", "INFO"),
            )

            integrations = IntegrationsConfig(
                YADISK_TOKEN=getenv("YADISK_TOKEN"),
                GOOGLE_SHEET_ID=getenv("GOOGLE_SHEET_ID"),
                GOOGLE_SHEET_GID=getenv("GOOGLE_SHEET_GID", "0"),
                GOOGLE_SHEET_NAME=getenv("GOOGLE_SHEET_NAME", "Контроль"),
                GOOGLE_SHEET_FILENAME=getenv(
                    "GOOGLE_SHEET_FILENAME",
                    "Контроль окончания сроков действия контрактов.xlsx",
                ),
                SHEET_SYNC_INTERVAL_MINUTES=int(getenv("SHEET_SYNC_INTERVAL_MINUTES", "5")),
            )
        except (ValidationError, ValueError) as exc:
            raise RuntimeError("Failed to load configuration") from exc

        paths.ensure()
        return cls(bot=bot, paths=paths, scheduler=scheduler, logging=logging, integrations=integrations)
