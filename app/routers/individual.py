# app/routers/individual.py
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from ..models import ProcessedDocument, IndividualDocumentRequest
from ..auth import verify_token
from ..services.document_processor import DocumentProcessor
from ..utils.pdf_utils import PDFProcessor
import uuid

router = APIRouter(prefix="/individual", tags=["Individual"])

@router.post("/clasificar-procesar", response_model=ProcessedDocument)
async def clasificar_procesar_documento(
    file: UploadFile = File(...),
    current_user: str = Depends(verify_token)
):
    """Clasifica y extrae datos de un documento individual cargado"""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")
    
    try:
        pdf_content = await file.read()
        processor = DocumentProcessor()
        document_id = str(uuid.uuid4())
        
        result = processor.clasificar_y_procesar(pdf_content, document_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")

@router.post("/clasificar-procesar/base64", response_model=ProcessedDocument)
async def clasificar_procesar_documento_base64(
    request: IndividualDocumentRequest,
    current_user: str = Depends(verify_token)
):
    """Clasifica y extrae datos de un documento enviado en base64"""
    try:
        pdf_processor = PDFProcessor()
        pdf_bytes = pdf_processor.base64_to_pdf(request.document_base64)
        
        processor = DocumentProcessor()
        document_id = str(uuid.uuid4())
        
        result = processor.clasificar_y_procesar(pdf_bytes, document_id)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")