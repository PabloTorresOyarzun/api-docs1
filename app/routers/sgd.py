# app/routers/sgd.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from ..models import SGDDocumentResponse, ProcessedDocument
from ..auth import verify_token
from ..services.sgd_service import SGDService
from ..services.document_processor import DocumentProcessor
from ..tasks.celery_tasks import process_sgd_documents
import uuid
from typing import List

router = APIRouter(prefix="/sgd", tags=["SGD"])

@router.get("/documentos/clasificar/{despacho_id}", response_model=List[ProcessedDocument])
async def get_classified_documents(
    despacho_id: str,
    current_user: str = Depends(verify_token)
):
    """Obtiene lista de documentos clasificados por IA según despacho consultado"""
    try:
        sgd_service = SGDService()
        processor = DocumentProcessor()
        
        # Obtener documentos de SGD
        documents = sgd_service.get_despacho_documents(despacho_id)
        
        if not documents:
            raise HTTPException(status_code=404, detail="No se encontraron documentos para este despacho")
        
        processed_documents = []
        for doc in documents:
            if 'content' in doc and 'id' in doc:
                try:
                    pdf_bytes = sgd_service.decode_document(doc['content'])
                    if pdf_bytes:
                        document_id = str(doc['id'])
                        result = processor.process_document(pdf_bytes, document_id)
                        processed_documents.append(result)
                except Exception as e:
                    print(f"Error procesando documento {doc.get('id')}: {e}")
                    continue
        
        return processed_documents
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo documentos: {str(e)}")

@router.get("/documentos/extraer/{despacho_id}/{document_id}", response_model=ProcessedDocument)
async def extract_specific_document(
    despacho_id: str,
    document_id: str,
    current_user: str = Depends(verify_token)
):
    """Extrae datos de un documento específico de un despacho"""
    try:
        sgd_service = SGDService()
        processor = DocumentProcessor()
        
        # Obtener documentos de SGD
        documents = sgd_service.get_despacho_documents(despacho_id)
        
        # Buscar documento específico
        target_doc = None
        for doc in documents:
            if str(doc.get('id')) == document_id:
                target_doc = doc
                break
        
        if not target_doc:
            raise HTTPException(status_code=404, detail="Documento no encontrado")
        
        # Procesar documento específico
        pdf_bytes = sgd_service.decode_document(target_doc['documento'])
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Error decodificando documento")
        
        result = processor.process_document(pdf_bytes, document_id)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extrayendo documento: {str(e)}")

@router.post("/documentos/procesar-asincrono/{despacho_id}")
async def process_documents_async(
    despacho_id: str,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(verify_token)
):
    """Procesa documentos de forma asíncrona usando Celery"""
    try:
        # Enviar tarea a Celery
        task = process_sgd_documents.delay(despacho_id)
        
        return {
            "message": "Procesamiento iniciado",
            "task_id": task.id,
            "despacho_id": despacho_id,
            "status": "processing"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error iniciando procesamiento: {str(e)}")

@router.get("/documentos/estado-tarea/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: str = Depends(verify_token)
):
    """Obtiene el estado de una tarea de procesamiento"""
    try:
        from ..tasks.celery_tasks import celery_app
        
        task_result = celery_app.AsyncResult(task_id)
        
        return {
            "task_id": task_id,
            "status": task_result.status,
            "result": task_result.result if task_result.ready() else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando tarea: {str(e)}")