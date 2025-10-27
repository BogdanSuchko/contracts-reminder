from __future__ import annotations

from pathlib import Path


class YandexDiskClient:
    def __init__(self, token: str | None = None) -> None:
        self._token = token

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    async def upload(self, path: Path) -> str:
        raise NotImplementedError("Yandex.Disk integration is not implemented yet")
