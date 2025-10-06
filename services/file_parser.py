from PyPDF2 import PdfReader
from typing import BinaryIO
import re

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

