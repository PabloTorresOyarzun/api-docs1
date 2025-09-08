# app/services/document_processor.py
from typing import List, Dict, Any, Tuple
from ..models import DocumentType, ClassificationResult, ExtractionResult, ProcessedDocument
from ..utils.pdf_utils import PDFProcessor
from .azure_service import AzureDocumentService
import time

class DocumentProcessor:
    def __init__(self):
        self.pdf_processor = PDFProcessor()
        self.azure_service = AzureDocumentService()
    
    def process_document(self, pdf_bytes: bytes, document_id: str) -> ProcessedDocument:
        """Procesa un documento completo: separación, clasificación, agrupación y extracción"""
        start_time = time.time()
        
        # 1. Separar páginas
        pages = self.pdf_processor.separate_pages(pdf_bytes)
        
        # 2. Clasificar cada página
        classifications = []
        for i, page_bytes in enumerate(pages):
            doc_type = self.azure_service.classify_document(page_bytes)
            classifications.append(ClassificationResult(
                page_number=i + 1,
                document_type=doc_type,
                confidence=0.95  # Azure no siempre devuelve confianza
            ))
        
        # 3. Agrupar páginas consecutivas del mismo tipo
        grouped_documents = self._group_consecutive_pages(pages, classifications)
        
        # 4. Extraer datos de cada grupo
        extractions = []
        for doc_type, grouped_pages in grouped_documents:
            if grouped_pages:
                # Unir páginas del grupo
                merged_pdf = self.pdf_processor.merge_pages(grouped_pages)
                
                # Extraer datos
                extracted_data = self.azure_service.extract_data(merged_pdf, doc_type)
                
                extractions.append(ExtractionResult(
                    document_type=doc_type,
                    extracted_data=extracted_data,
                    confidence=0.95
                ))
        
        processing_time = time.time() - start_time
        
        return ProcessedDocument(
            document_id=document_id,
            classification=classifications,
            extraction=extractions,
            processing_time=processing_time
        )
    
    def _group_consecutive_pages(self, pages: List[bytes], classifications: List[ClassificationResult]) -> List[Tuple[DocumentType, List[bytes]]]:
        """Agrupa páginas consecutivas del mismo tipo"""
        if not classifications:
            return []
        
        grouped = []
        current_type = classifications[0].document_type
        current_pages = [pages[0]]
        
        for i in range(1, len(classifications)):
            if classifications[i].document_type == current_type:
                current_pages.append(pages[i])
            else:
                # Cambio de tipo, guardar grupo actual y comenzar nuevo
                grouped.append((current_type, current_pages))
                current_type = classifications[i].document_type
                current_pages = [pages[i]]
        
        # Agregar último grupo
        grouped.append((current_type, current_pages))
        
        return grouped
