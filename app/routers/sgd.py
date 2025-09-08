# app/routers/individual.py
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from ..models import ProcessedDocument, IndividualDocumentRequest
from ..auth import verify_token
from ..services.document_processor import DocumentProcessor
from ..utils.pdf_utils import PDFProcessor
import uuid

router = APIRouter(prefix="/individual", tags=["Individual"])

@router.post("/extraer", response_model=ProcessedDocument)
async def extract_individual_document(
    file: UploadFile = File(...),
    current_user: str = Depends(verify_token)
):
    """Extrae datos de un documento individual cargado"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    try:
        # Leer archivo
        pdf_content = await file.read()
        
        # Procesar documento
        processor = DocumentProcessor()
        document_id = str(uuid.uuid4())
        
        result = processor.process_document(pdf_content, document_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")

@router.post("/extraer/base64", response_model=ProcessedDocument)
async def extract_document_base64(
    request: IndividualDocumentRequest,
    current_user: str = Depends(verify_token)
):
    """Extrae datos de un documento enviado en base64"""
    try:
        # Decodificar base64
        pdf_processor = PDFProcessor()
        pdf_bytes = pdf_processor.base64_to_pdf(request.document_base64)
        
        # Procesar documento
        processor = DocumentProcessor()
        document_id = str(uuid.uuid4())
        
        result = processor.process_document(pdf_bytes, document_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")

