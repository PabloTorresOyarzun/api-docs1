# app/utils/pdf_utils.py
import fitz  # PyMuPDF
import base64
from typing import List
from io import BytesIO

class PDFProcessor:
    @staticmethod
    def separate_pages(pdf_bytes: bytes) -> List[bytes]:
        """Separa un PDF en páginas individuales"""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        
        for page_num in range(doc.page_count):
            # Crear un nuevo documento con una sola página
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Convertir a bytes
            page_bytes = new_doc.write()
            pages.append(page_bytes)
            new_doc.close()
        
        doc.close()
        return pages
    
    @staticmethod
    def merge_pages(pages: List[bytes]) -> bytes:
        """Une múltiples páginas en un solo PDF"""
        merged_doc = fitz.open()
        
        for page_bytes in pages:
            page_doc = fitz.open(stream=page_bytes, filetype="pdf")
            merged_doc.insert_pdf(page_doc)
            page_doc.close()
        
        result_bytes = merged_doc.write()
        merged_doc.close()
        return result_bytes
    
    @staticmethod
    def base64_to_pdf(base64_string: str) -> bytes:
        """Convierte base64 a bytes de PDF"""
        return base64.b64decode(base64_string)
    
    @staticmethod
    def pdf_to_base64(pdf_bytes: bytes) -> str:
        """Convierte bytes de PDF a base64"""
        return base64.b64encode(pdf_bytes).decode('utf-8')