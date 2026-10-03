from typing import BinaryIO
import re
from io import BytesIO
from zipfile import BadZipFile, ZipFile

MAX_PDF_PAGES = 200
MAX_DOCX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024


def extract_text_from_pdf_file(file: BinaryIO) -> str:
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(file)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF has too many pages (max {MAX_PDF_PAGES})")
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            pages.append(page_text)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Could not parse PDF: {exc}") from exc
    text = " ".join(pages)

    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def extract_text_from_txt_file(file: BinaryIO) -> str:
    return file.read().decode("utf-8", errors="strict")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    if not file_bytes.startswith(b"%PDF"):
        raise ValueError("File is not a valid PDF")
    return extract_text_from_pdf_file(BytesIO(file_bytes))


def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Text file must be valid UTF-8") from exc


def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        import defusedxml.ElementTree as ElementTree

        if not file_bytes.startswith(b"PK"):
            raise ValueError("File is not a valid DOCX")
        with ZipFile(BytesIO(file_bytes)) as docx:
            try:
                info = docx.getinfo("word/document.xml")
            except KeyError as exc:
                raise ValueError("DOCX is missing its document content") from exc
            if info.file_size > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ValueError("DOCX is too large when decompressed")
            xml = docx.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        parts = [node.text for node in root.findall(".//w:t", namespace) if node.text]
        return re.sub(r"\s+", " ", " ".join(parts)).strip()
    except ValueError:
        raise
    except BadZipFile as exc:
        raise ValueError(f"File is not a valid DOCX: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Could not parse DOCX: {exc}") from exc


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    return extract_text_from_txt(file_bytes)
