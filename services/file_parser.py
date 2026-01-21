from PyPDF2 import PdfReader
from typing import BinaryIO
import re
from io import BytesIO

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

