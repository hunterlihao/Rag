from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from docx import Document
from pypdf import PdfReader


def extract_text_from_file(file_source: bytes | BinaryIO, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        return _decode_text_bytes(_read_file_bytes(file_source))
    if suffix == ".pdf":
        return _extract_pdf_text(file_source)
    if suffix == ".docx":
        return _extract_docx_text(file_source)
    if suffix in {".xlsx", ".xls"}:
        return _extract_excel_text(file_source)
    if suffix == ".doc":
        raise ValueError("当前仅支持 .docx，老式 .doc 请先另存为 .docx 后再上传。")
    raise ValueError(f"暂不支持 {suffix or '无扩展名'} 格式。")


def _read_file_bytes(file_source: bytes | BinaryIO) -> bytes:
    if isinstance(file_source, bytes):
        return file_source

    current_position = file_source.tell() if file_source.seekable() else None
    if file_source.seekable():
        file_source.seek(0)
    file_bytes = file_source.read()
    if isinstance(file_bytes, str):
        file_bytes = file_bytes.encode("utf-8")
    if current_position is not None:
        file_source.seek(current_position)
    return bytes(file_bytes)


def _decode_text_bytes(file_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


def _extract_pdf_text(file_source: bytes | BinaryIO) -> str:
    reader = PdfReader(BytesIO(_read_file_bytes(file_source)))
    parts = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            parts.append(f"第{index}页\n{page_text}")
    return "\n\n".join(parts)


def _extract_docx_text(file_source: bytes | BinaryIO) -> str:
    document = Document(BytesIO(_read_file_bytes(file_source)))
    parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]

    for table_index, table in enumerate(document.tables, start=1):
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                rows.append(" | ".join(cells))
        if rows:
            parts.append(f"表格{table_index}\n" + "\n".join(rows))

    return "\n\n".join(parts)


def _extract_excel_text(file_source: bytes | BinaryIO) -> str:
    sheets = pd.read_excel(BytesIO(_read_file_bytes(file_source)), sheet_name=None, dtype=str)
    parts = []

    for sheet_name, dataframe in sheets.items():
        dataframe = dataframe.fillna("")
        if dataframe.empty and not list(dataframe.columns):
            continue
        sheet_text = dataframe.to_csv(index=False).replace("\r\n", "\n").replace("\r", "\n").strip()
        if sheet_text:
            parts.append(f"工作表: {sheet_name}\n{sheet_text}")

    return "\n\n".join(parts)
