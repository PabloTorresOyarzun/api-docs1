# app/routers/sgd.py (Debug version)
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from ..models import SGDDocumentResponse, ProcessedDocument
from ..auth import verify_token
from ..services.sgd_service import SGDService
from ..services.document_processor import DocumentProcessor
from ..tasks.celery_tasks import process_sgd_documents
import uuid
import logging
from typing import List

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sgd", tags=["SGD"])

@router.get("/documentos/clasificar/{despacho_id}", response_model=List[ProcessedDocument])
async def get_classified_documents(
    despacho_id: str,
    current_user: str = Depends(verify_token)
):
    """Obtiene lista de documentos clasificados por IA según despacho consultado"""
    try:
        logger.info(f"Iniciando clasificación para despacho: {despacho_id}")
        sgd_service = SGDService()
        processor = DocumentProcessor()
        
        # Obtener documentos de SGD
        logger.info("Obteniendo documentos de SGD...")
        documents = sgd_service.get_despacho_documents(despacho_id)
        
        if not documents:
            logger.warning(f"No se encontraron documentos para despacho {despacho_id}")
            raise HTTPException(status_code=404, detail="No se encontraron documentos para este despacho")
        
        logger.info(f"Procesando {len(documents)} documentos...")
        processed_documents = []
        
        for i, doc in enumerate(documents):
            logger.info(f"Procesando documento {i+1}/{len(documents)}")
            logger.info(f"Claves del documento: {list(doc.keys())}")
            
            # Buscar campo que contenga el base64 - SGD usa 'documento'
            content_field = None
            for field in ['documento', 'content', 'base64', 'data']:
                if field in doc:
                    content_field = field
                    break
            
            if not content_field:
                logger.error(f"No se encontró campo de contenido en documento {i+1}")
                continue
                
            document_id = str(doc.get('id', f"doc_{i}"))
            
            try:
                logger.info(f"Decodificando documento {document_id}...")
                pdf_bytes = sgd_service.decode_document(doc[content_field])
                
                if not pdf_bytes:
                    logger.error(f"Error decodificando documento {document_id}")
                    continue
                
                logger.info(f"Clasificando y extrayendo datos de documento {document_id}...")
                result = processor.process_document(pdf_bytes, document_id)
                processed_documents.append(result)
                logger.info(f"Documento {document_id} procesado exitosamente")
                
            except Exception as e:
                logger.error(f"Error procesando documento {document_id}: {str(e)}")
                logger.exception("Stack trace:")
                continue
        
        logger.info(f"Procesamiento completado. {len(processed_documents)} documentos exitosos")
        return processed_documents
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error general obteniendo documentos: {str(e)}")
        logger.exception("Stack trace:")
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