from __future__ import annotations

import shutil
from pathlib import Path

from contract_bot.config import AppConfig


def _resolve_paths() -> tuple[Path, Path, Path]:
    try:
        config = AppConfig.load()
        return config.paths.files_dir, config.paths.generated_dir, config.paths.state_file
    except RuntimeError:
        base = Path.cwd()
        files_dir = base / "storage" / "contracts"
        generated_dir = base / "generated"
        state_file = base / "storage" / "meta" / "state.json"
        files_dir.mkdir(parents=True, exist_ok=True)
        generated_dir.mkdir(parents=True, exist_ok=True)
        state_file.parent.mkdir(parents=True, exist_ok=True)
        return files_dir, generated_dir, state_file


def _clear_directory(path: Path) -> int:
    removed = 0
    if not path.exists():
        return removed
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
        removed += 1
    path.mkdir(parents=True, exist_ok=True)
    return removed


def delete_cache() -> None:
    files_dir, generated_dir, state_file = _resolve_paths()

    removed_contracts = _clear_directory(files_dir)
    removed_generated = _clear_directory(generated_dir)

    if state_file.exists():
        state_file.unlink()
        removed_state = 1
    else:
        removed_state = 0

    print(
        "Кеш очищен:\n"
        f"- файлов в storage/contracts: {removed_contracts}\n"
        f"- файлов в generated: {removed_generated}\n"
        f"- state.json удалён: {'да' if removed_state else 'нет'}"
    )


def main() -> None:
    delete_cache()
