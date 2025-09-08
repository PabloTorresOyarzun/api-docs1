# app/models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

class DocumentType(str, Enum):
    INVOICE = "invoice"
    TRANSPORT = "transport" 
    PACKLIST = "packlist"

class ClassificationResult(BaseModel):
    page_number: int
    document_type: DocumentType
    confidence: float

class ExtractionResult(BaseModel):
    document_type: DocumentType
    extracted_data: Dict[str, Any]
    confidence: float

class ProcessedDocument(BaseModel):
    document_id: str
    classification: List[ClassificationResult]
    extraction: List[ExtractionResult]
    processing_time: float

class SGDDocumentResponse(BaseModel):
    documents: List[ProcessedDocument]
    despacho_id: str

class IndividualDocumentRequest(BaseModel):
    document_base64: str
    filename: Optional[str] = None