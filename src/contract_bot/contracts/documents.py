from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from docxtpl import DocxTemplate

from contract_bot.contracts.parser import ContractRecord, DocumentType
from contract_bot.utils.text import sanitize_filename

DATE_FORMAT = "%d.%m.%Y"

TEMPLATE_NAMES = {
    DocumentType.EXTENSION: "notify_extension.docx",
    DocumentType.TERMINATION: "notify_termination.docx",
}


@dataclass
class DocumentContext:
    record: ContractRecord
    document_number: str = ""
    director_name: str = ""
    director_signature: str = ""

    def for_extension(self) -> dict[str, str]:
        return {
            "organization": self.record.organization,
            "document_number": self.document_number,
            "position": self.record.position or "",
            "employee_full_name": self.record.employee,
            "contract_date": format_date(self.record.contract_date),
            "contract_number": self.record.contract_number or "",
            "contract_end_date": format_date(self.record.end_date),
            "extension_term": self.record.extension_term or "",
            "extension_start": format_date(self.record.extension_start_date),
            "extension_end": format_date(self.record.extension_end_date),
            "director_name": self.director_name,
            "director_signature": self.director_signature,
            "response_deadline": format_date(self.record.reminder_date),
        }

    def for_termination(self) -> dict[str, str]:
        return {
            "organization": self.record.organization,
            "document_number": self.document_number,
            "contract_date": format_date(self.record.contract_date),
            "contract_number": self.record.contract_number or "",
            "employee_full_name": self.record.employee,
            "contract_end_date": format_date(self.record.end_date),
            "director_name": self.director_name,
            "director_signature": self.director_signature,
        }


class DocumentGenerator:
    def __init__(self, templates_dir: Path, output_dir: Path):
        self._templates_dir = templates_dir
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        record: ContractRecord,
        context: DocumentContext | None = None,
        doc_type: Optional[DocumentType] = None,
    ) -> Path:
        doc_type = doc_type or record.decide_document()
        if doc_type is None:
            raise ValueError("Cannot determine document type for record")

        template_name = TEMPLATE_NAMES.get(doc_type)
        if not template_name:
            raise FileNotFoundError(f"Template not configured for {doc_type}")

        template_path = self._templates_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        tpl = DocxTemplate(template_path)
        context = context or DocumentContext(record=record)
        if doc_type is DocumentType.EXTENSION:
            payload = context.for_extension()
        else:
            payload = context.for_termination()

        tpl.render(payload)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{sanitize_filename(record.employee)}_{doc_type.value}.docx"
        target_dir = self._output_dir / datetime.utcnow().strftime("%Y-%m-%d")
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / filename
        tpl.save(output_path)
        return output_path


def format_date(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime(DATE_FORMAT)
