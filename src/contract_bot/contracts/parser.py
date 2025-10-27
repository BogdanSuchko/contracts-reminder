from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Iterable, List

import pandas as pd

DEFAULT_SHEET_NAMES = ("Контроль", "��������", "Sheet2", "Лист1")
HEADER_ROW_INDEX = 6


class DocumentType(str, Enum):
    EXTENSION = "extension"
    TERMINATION = "termination"


@dataclass
class ContractRecord:
    organization: str
    employee: str
    position: str | None
    contract_number: str | None
    contract_date: date | None
    start_date: date | None
    end_date: date | None
    reminder_date: date | None
    notification_label: str | None
    readiness_mark: str | None
    extension_term: str | None
    extension_start_date: date | None
    extension_end_date: date | None
    document_hint: str | None

    def decide_document(self) -> DocumentType | None:
        mark = _normalize_mark(self.readiness_mark)
        if mark in {"П", "Н"}:
            return DocumentType.EXTENSION
        if mark in {"И", "У"}:
            return DocumentType.TERMINATION
        hint = self.document_hint or self.notification_label
        if hint:
            lower = hint.lower()
            if "увольн" in lower:
                return DocumentType.TERMINATION
            if "продл" in lower:
                return DocumentType.EXTENSION
        return None


COLUMN_ALIASES: dict[str, Iterable[str]] = {
    "organization": ("Наименование организации", "������������ �����������"),
    "employee": ("Фамилия, имя, отчество", "�������, ���, ��������", "ФИО"),
    "position": (
        "Должность служащего, профессия рабочего",
        "��������� ���������, ��������� ��������",
        "Должность",
    ),
    "contract_date": ("Дата контракта", "���� ���������"),
    "contract_number": ("Номер контракта", "����� ���������"),
    "start_date": ("Дата начала контракта", "���� ������ ���������"),
    "contract_term": ("Срок действия контракта", "���� �������� ���������"),
    "end_date": ("Дата окончания контракта", "���� ��������� ���������"),
    "reminder_date": (
        "Срок для предупреж-дения за 1 месяц до окончания контракта",
        "���� ��� ���������-����� �� 1 ����� �� ��������� ���������",
    ),
    "notification": ("Уведомление", "�����������"),
    "readiness": ("Отметка о готовности", "������� � ����������"),
    "extension_term": (
        "Срок, на который продлен контракт или заключен новый контракт",
        "����, �� ������� ������� �������� ��� �������� ����� ��������",
    ),
    "extension_start": (
        "Дата начала продленного контракта",
        "Дата начала нового контракта",
    ),
    "extension_end": (
        "Дата окончания продленного контракта",
        "Дата окончания нового контракта",
    ),
}

COLUMN_INDEX_FALLBACK = {
    "organization": 0,
    "employee": 1,
    "position": 2,
    "contract_date": 3,
    "contract_number": 4,
    "start_date": 5,
    "contract_term": 6,
    "end_date": 9,
    "reminder_date": 10,
    "notification": 11,
    "readiness": 12,
    "extension_term": 13,
    "extension_start": 17,
    "extension_end": 18,
}


def parse_contracts(path: Path) -> List[ContractRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    sheet_name = _detect_sheet(path)
    df = pd.read_excel(path, sheet_name=sheet_name, header=HEADER_ROW_INDEX)
    df = df.dropna(subset=[_resolve_column(df, "employee")], how="all")

    records: List[ContractRecord] = []
    for _, row in df.iterrows():
        organization = _get_str(row, df, "organization")
        employee = _get_str(row, df, "employee")
        if not employee:
            continue

        record = ContractRecord(
            organization=organization or "",
            employee=employee,
            position=_get_str(row, df, "position"),
            contract_number=_get_str(row, df, "contract_number"),
            contract_date=_get_date(row, df, "contract_date"),
            start_date=_get_date(row, df, "start_date"),
            end_date=_get_date(row, df, "end_date"),
            reminder_date=_get_date(row, df, "reminder_date"),
            notification_label=_get_str(row, df, "notification"),
            readiness_mark=_get_str(row, df, "readiness"),
            extension_term=_get_str(row, df, "extension_term"),
            extension_start_date=_get_date(row, df, "extension_start"),
            extension_end_date=_get_date(row, df, "extension_end"),
            document_hint=_find_document_hint(row, df),
        )
        if record.end_date is None:
            continue
        records.append(record)

    return records


def _detect_sheet(path: Path) -> int | str:
    try:
        xls = pd.ExcelFile(path)
    except ValueError:
        return 0

    for preferred in DEFAULT_SHEET_NAMES:
        for name in xls.sheet_names:
            if name == preferred:
                return name
    return 0


def _resolve_column(df: pd.DataFrame, key: str) -> str:
    aliases = COLUMN_ALIASES.get(key, ())
    for alias in aliases:
        if alias in df.columns:
            return alias
    index = COLUMN_INDEX_FALLBACK.get(key)
    if index is None or index >= len(df.columns):
        raise KeyError(f"Cannot resolve column for {key}")
    return df.columns[index]


def _get_str(row: pd.Series, df: pd.DataFrame, key: str) -> str | None:
    column = _resolve_column(df, key)
    value = row.get(column)
    if pd.isna(value):
        return None
    if isinstance(value, (float, int)):
        if float(value).is_integer():
            return str(int(value))
    text = str(value).strip()
    return text or None


def _get_date(row: pd.Series, df: pd.DataFrame, key: str) -> date | None:
    column = _resolve_column(df, key)
    value = row.get(column)
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _find_document_hint(row: pd.Series, df: pd.DataFrame) -> str | None:
    for column in df.columns:
        name = str(column).lower()
        if "документ" in name or "тип" in name:
            value = row.get(column)
            text = _coerce_to_str(value)
            if text:
                return text
    return None


def _coerce_to_str(value: object) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _normalize_mark(mark: str | None) -> str:
    if not mark:
        return ""
    normalized = mark.strip().upper()
    replacements = {
        "\u040f": "\u041f",  # Џ -> П
        "\u040a": "\u041d",  # Њ -> Н
        "\u0403": "\u0413",  # Ѓ -> Г
    }
    return replacements.get(normalized, normalized)
