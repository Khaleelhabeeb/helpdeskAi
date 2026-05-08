from PyPDF2 import PdfReader
from typing import BinaryIO
import re
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree

def extract_text_from_pdf_file(file: BinaryIO) -> str:
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text += page_text + " "
    
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)   
    text = text.strip()                
    
    return text


def extract_text_from_txt_file(file: BinaryIO) -> str:
    return file.read().decode("utf-8")


def extract_text_from_pdf(file_bytes: bytes) -> str:
    # Extract text from PDF bytes
    return extract_text_from_pdf_file(BytesIO(file_bytes))


def extract_text_from_txt(file_bytes: bytes) -> str:
    # Extract text from TXT bytes
    return file_bytes.decode("utf-8")


def extract_text_from_docx(file_bytes: bytes) -> str:
    with ZipFile(BytesIO(file_bytes)) as docx:
        xml = docx.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts = [node.text for node in root.findall(".//w:t", namespace) if node.text]
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    if lower.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    return extract_text_from_txt(file_bytes)
