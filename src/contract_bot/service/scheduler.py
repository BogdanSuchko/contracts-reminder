from __future__ import annotations

from datetime import datetime, timedelta
from logging import Logger

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from zoneinfo import ZoneInfo

from contract_bot.config import AppConfig
from contract_bot.service.reminder import ReminderService
from contract_bot.service.sheet_sync import SheetSyncService


class Scheduler:
    def __init__(self, config: AppConfig, reminder_service: ReminderService, sheet_sync: SheetSyncService, logger: Logger) -> None:
        self._config = config
        self._reminder_service = reminder_service
        self._sheet_sync = sheet_sync
        self._logger = logger
        self._timezone = ZoneInfo(config.scheduler.timezone)
        self._scheduler = AsyncIOScheduler(
            timezone=self._timezone,
            job_defaults={"misfire_grace_time": 86400, "coalesce": True},
        )

    def start(self) -> None:
        if self._sheet_sync.enabled:
            self._scheduler.add_job(
                self._sync_sheet_job,
                trigger=IntervalTrigger(minutes=self._config.integrations.sheet_sync_interval_minutes, timezone=self._timezone),
                id="sheet-sync",
                replace_existing=True,
                next_run_time=datetime.now(self._timezone),
            )

        daily_trigger = CronTrigger(hour=9, minute=0)
        self._scheduler.add_job(
            self._reminder_job,
            trigger=daily_trigger,
            id="contract-reminder-daily",
            replace_existing=True,
            next_run_time=datetime.now(self._timezone),
            misfire_grace_time=86400,
        )

        hourly_trigger = IntervalTrigger(hours=1, timezone=self._timezone)
        self._scheduler.add_job(
            self._reminder_job,
            trigger=hourly_trigger,
            id="contract-reminder-hourly",
            replace_existing=True,
            next_run_time=datetime.now(self._timezone) + timedelta(hours=1),
        )

        self._scheduler.start()
        self._logger.info(
            "Планировщик запущен: ежедневная проверка в 09:00 + резервный запуск раз в час"
        )

    async def _sync_sheet_job(self) -> None:
        await self._sheet_sync.sync()

    async def run_once(self) -> None:
        await self._reminder_job()

    async def _reminder_job(self) -> None:
        try:
            if self._sheet_sync.enabled:
                await self._sheet_sync.sync()
            result = await self._reminder_service.run()
            self._logger.info(
                "Напоминания обработаны: всего=%s, отправлено=%s, пропущено=%s",
                result.processed,
                result.notified,
                result.skipped,
            )
        except Exception as exc:  # noqa: BLE001
            self._logger.exception("Ошибка при выполнении напоминаний: %s", exc)

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown()
            self._logger.info("Планировщик остановлен")
