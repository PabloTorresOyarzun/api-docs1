# app/models.py
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

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

# Nuevos modelos para mejoras

class DocumentInfo(BaseModel):
    """Información básica de un documento sin procesar"""
    document_id: str
    filename: str
    size_bytes: Optional[int] = None
    pages: Optional[int] = None

class DespachoInfo(BaseModel):
    """Información del despacho y sus documentos"""
    despacho_id: str
    total_documents: int
    documents: List[DocumentInfo]
    retrieved_at: datetime

class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"

class DocumentError(BaseModel):
    """Error al procesar un documento"""
    document_id: str
    error_message: str
    error_type: str

class ProcessingMetadata(BaseModel):
    """Metadata del procesamiento"""
    total_documentos: int
    procesados: int
    fallidos: int
    tiempo_total: float
    modelos_usados: List[str]
    cached: bool = False

class ProcessingResult(BaseModel):
    """Resultado de procesamiento con manejo de errores"""
    exitosos: List[ProcessedDocument]
    fallidos: List[DocumentError]
    metadata: ProcessingMetadata
    status: ProcessingStatus

class ClasificacionDocumento(BaseModel):
    document_id: str
    document_real_id: str
    classifications: List[ClassificationResult]

class DespachoClasificado(BaseModel):
    despacho_id: str
    documentos: List[ClasificacionDocumento]
    metadata: ProcessingMetadata

class AsyncTaskResponse(BaseModel):
    """Respuesta para tareas asíncronas"""
    task_id: str
    despacho_id: str
    status: str
    message: str
    webhook_url: Optional[str] = None

class TaskStatusResponse(BaseModel):
    """Estado de una tarea asíncrona"""
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: Optional[float] = None