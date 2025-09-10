# app/routers/sgd.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from ..models import (
    ProcessedDocument, ClassificationResult, DocumentType,
    DespachoInfo, DocumentInfo, ProcessingResult, ProcessingStatus,
    DocumentError, ProcessingMetadata, ClasificacionDocumento,
    DespachoClasificado, AsyncTaskResponse, TaskStatusResponse
)
from ..auth import verify_token
from ..services.sgd_service import SGDService
from ..services.document_processor import DocumentProcessor
from ..services.cache_service import CacheService
from ..tasks.celery_tasks import process_sgd_documents
import logging
from typing import List, Optional
from datetime import datetime
import time
import traceback

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sgd", tags=["SGD"])

@router.get("/despacho/{despacho_id}/info", response_model=DespachoInfo)
async def obtener_info_despacho(
    despacho_id: str,
    use_cache: bool = Query(True, description="Usar cache si está disponible"),
    current_user: str = Depends(verify_token)
):
    """Obtiene información del despacho y lista sus documentos sin procesarlos"""
    try:
        logger.info(f"Obteniendo información del despacho: {despacho_id}")
        sgd_service = SGDService()
        
        documents, from_cache = sgd_service.get_despacho_documents(despacho_id, use_cache)
        
        if not documents:
            raise HTTPException(status_code=404, detail="No se encontraron documentos")
        
        document_info_list = []
        for i, doc in enumerate(documents):
            # Obtener nombre del documento
            doc_name = doc.get('nombre', doc.get('name', doc.get('filename', f"doc_{i}")))
            
            # Obtener contenido para calcular tamaño y páginas
            content_field = None
            for field in ['documento', 'content', 'base64', 'data']:
                if field in doc:
                    content_field = field
                    break
            
            size_bytes = None
            pages = None
            
            if content_field:
                size_bytes = sgd_service.estimate_document_size(doc[content_field])
                # Opcionalmente, contar páginas (puede ser costoso)
                pdf_bytes = sgd_service.decode_document(doc[content_field])
                if pdf_bytes:
                    pages = sgd_service.count_pdf_pages(pdf_bytes)
            
            document_info_list.append(DocumentInfo(
                document_id=doc_name,
                filename=doc_name,
                size_bytes=size_bytes,
                pages=pages
            ))
        
        return DespachoInfo(
            despacho_id=despacho_id,
            total_documents=len(documents),
            documents=document_info_list,
            retrieved_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo info del despacho: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/despacho/{despacho_id}/clasificar", response_model=DespachoClasificado)
async def clasificar_despacho(
    despacho_id: str,
    use_cache: bool = Query(True, description="Usar cache si está disponible"),
    current_user: str = Depends(verify_token)
):
    """Solo clasifica todos los documentos de un despacho con manejo de errores"""
    try:
        start_time = time.time()
        logger.info(f"Clasificando despacho: {despacho_id}")
        
        sgd_service = SGDService()
        processor = DocumentProcessor()
        cache_service = CacheService()
        
        # Verificar si hay resultado en cache
        if use_cache:
            cached_result = cache_service.get_processing_result(f"{despacho_id}_clasificacion")
            if cached_result:
                logger.info(f"Retornando clasificación desde cache para {despacho_id}")
                return DespachoClasificado(**cached_result)
        
        documents, from_cache = sgd_service.get_despacho_documents(despacho_id, use_cache)
        
        if not documents:
            raise HTTPException(status_code=404, detail="No se encontraron documentos")
        
        documentos_clasificados = []
        documentos_fallidos = []
        modelos_usados = set()
        
        for i, doc in enumerate(documents):
            doc_name = doc.get('nombre', doc.get('name', doc.get('filename', f"doc_{i}")))
            
            try:
                content_field = None
                for field in ['documento', 'content', 'base64', 'data']:
                    if field in doc:
                        content_field = field
                        break
                
                if not content_field:
                    documentos_fallidos.append(DocumentError(
                        document_id=doc_name,
                        error_message="Documento sin contenido",
                        error_type="MISSING_CONTENT"
                    ))
                    continue
                
                pdf_bytes = sgd_service.decode_document(doc[content_field])
                if not pdf_bytes:
                    documentos_fallidos.append(DocumentError(
                        document_id=doc_name,
                        error_message="Error decodificando documento",
                        error_type="DECODE_ERROR"
                    ))
                    continue
                
                classifications = processor.clasificar(pdf_bytes, doc_name)
                
                # Registrar modelos usados
                for cls in classifications:
                    modelos_usados.add(f"classification_{cls.document_type.value}")
                
                documentos_clasificados.append(ClasificacionDocumento(
                    document_id=doc_name,
                    document_real_id=doc_name,
                    classifications=classifications
                ))
                
            except Exception as e:
                logger.error(f"Error clasificando documento {doc_name}: {str(e)}")
                documentos_fallidos.append(DocumentError(
                    document_id=doc_name,
                    error_message=str(e),
                    error_type="CLASSIFICATION_ERROR"
                ))
        
        processing_time = time.time() - start_time
        
        metadata = ProcessingMetadata(
            total_documentos=len(documents),
            procesados=len(documentos_clasificados),
            fallidos=len(documentos_fallidos),
            tiempo_total=processing_time,
            modelos_usados=list(modelos_usados),
            cached=from_cache
        )
        
        result = DespachoClasificado(
            despacho_id=despacho_id,
            documentos=documentos_clasificados,
            metadata=metadata
        )
        
        # Guardar en cache
        cache_service.set_processing_result(f"{despacho_id}_clasificacion", result.dict())
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clasificando despacho: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/despacho/{despacho_id}/procesar", response_model=ProcessingResult)
async def procesar_despacho(
    despacho_id: str,
    use_cache: bool = Query(True, description="Usar cache si está disponible"),
    force_reprocess: bool = Query(False, description="Forzar reprocesamiento"),
    current_user: str = Depends(verify_token)
):
    """Clasifica y extrae datos de todos los documentos con manejo robusto de errores"""
    try:
        start_time = time.time()
        logger.info(f"Procesando despacho completo: {despacho_id}")
        
        sgd_service = SGDService()
        processor = DocumentProcessor()
        cache_service = CacheService()
        
        # Verificar cache si no se fuerza reprocesamiento
        if use_cache and not force_reprocess:
            cached_result = cache_service.get_processing_result(despacho_id)
            if cached_result:
                logger.info(f"Retornando resultado desde cache para {despacho_id}")
                return ProcessingResult(**cached_result)
        
        documents, from_cache = sgd_service.get_despacho_documents(despacho_id, use_cache)
        
        if not documents:
            raise HTTPException(status_code=404, detail="No se encontraron documentos")
        
        processed_documents = []
        failed_documents = []
        modelos_usados = set()
        
        for i, doc in enumerate(documents):
            doc_name = doc.get('nombre', doc.get('name', doc.get('filename', f"doc_{i}")))
            logger.info(f"Procesando documento {i+1}/{len(documents)}: {doc_name}")
            
            try:
                content_field = None
                for field in ['documento', 'content', 'base64', 'data']:
                    if field in doc:
                        content_field = field
                        break
                
                if not content_field:
                    failed_documents.append(DocumentError(
                        document_id=doc_name,
                        error_message="Documento sin contenido",
                        error_type="MISSING_CONTENT"
                    ))
                    continue
                
                pdf_bytes = sgd_service.decode_document(doc[content_field])
                if not pdf_bytes:
                    failed_documents.append(DocumentError(
                        document_id=doc_name,
                        error_message="Error decodificando documento",
                        error_type="DECODE_ERROR"
                    ))
                    continue
                
                result = processor.clasificar_y_procesar(pdf_bytes, doc_name)
                processed_documents.append(result)
                
                # Registrar modelos usados
                for ext in result.extraction:
                    modelos_usados.add(f"extraction_{ext.document_type.value}")
                
            except Exception as e:
                logger.error(f"Error procesando documento {doc_name}: {str(e)}")
                logger.error(traceback.format_exc())
                failed_documents.append(DocumentError(
                    document_id=doc_name,
                    error_message=str(e),
                    error_type="PROCESSING_ERROR"
                ))
        
        processing_time = time.time() - start_time
        
        # Determinar estado general
        if len(failed_documents) == 0:
            status = ProcessingStatus.SUCCESS
        elif len(processed_documents) == 0:
            status = ProcessingStatus.FAILED
        else:
            status = ProcessingStatus.PARTIAL
        
        metadata = ProcessingMetadata(
            total_documentos=len(documents),
            procesados=len(processed_documents),
            fallidos=len(failed_documents),
            tiempo_total=processing_time,
            modelos_usados=list(modelos_usados),
            cached=from_cache
        )
        
        result = ProcessingResult(
            exitosos=processed_documents,
            fallidos=failed_documents,
            metadata=metadata,
            status=status
        )
        
        # Guardar en cache solo si fue exitoso o parcial
        if status != ProcessingStatus.FAILED:
            cache_service.set_processing_result(despacho_id, result.dict())
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando despacho: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/despacho/{despacho_id}/procesar-asincrono", response_model=AsyncTaskResponse)
async def procesar_despacho_asincrono(
    despacho_id: str,
    webhook_url: Optional[str] = None,
    current_user: str = Depends(verify_token)
):
    """Procesa documentos de forma asíncrona con opción de webhook"""
    try:
        # Enviar tarea a Celery con webhook si se proporciona
        task = process_sgd_documents.delay(despacho_id, webhook_url)
        
        return AsyncTaskResponse(
            task_id=task.id,
            despacho_id=despacho_id,
            status="processing",
            message="Procesamiento iniciado",
            webhook_url=webhook_url
        )
        
    except Exception as e:
        logger.error(f"Error iniciando procesamiento asíncrono: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tarea/{task_id}/estado", response_model=TaskStatusResponse)
async def obtener_estado_tarea(
    task_id: str,
    current_user: str = Depends(verify_token)
):
    """Obtiene el estado detallado de una tarea asíncrona"""
    try:
        from ..tasks.celery_tasks import celery_app
        
        task_result = celery_app.AsyncResult(task_id)
        
        # Obtener información detallada según el estado
        if task_result.ready():
            if task_result.successful():
                return TaskStatusResponse(
                    task_id=task_id,
                    status="completed",
                    result=task_result.result,
                    progress=100.0
                )
            else:
                return TaskStatusResponse(
                    task_id=task_id,
                    status="failed",
                    error=str(task_result.info),
                    progress=0.0
                )
        else:
            # Si la tarea está en progreso, intentar obtener metadata
            meta = task_result.info or {}
            progress = meta.get('progress', 0.0) if isinstance(meta, dict) else 0.0
            
            return TaskStatusResponse(
                task_id=task_id,
                status="processing",
                progress=progress
            )
        
    except Exception as e:
        logger.error(f"Error consultando tarea: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/despacho/{despacho_id}/cache")
async def invalidar_cache_despacho(
    despacho_id: str,
    current_user: str = Depends(verify_token)
):
    """Invalida el cache de un despacho específico"""
    try:
        cache_service = CacheService()
        cache_service.invalidate_despacho(despacho_id)
        
        return {
            "message": f"Cache invalidado para despacho {despacho_id}",
            "despacho_id": despacho_id
        }
        
    except Exception as e:
        logger.error(f"Error invalidando cache: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/despacho/{despacho_id}/cache/ttl")
async def obtener_ttl_cache(
    despacho_id: str,
    current_user: str = Depends(verify_token)
):
    """Obtiene el tiempo restante del cache para un despacho"""
    try:
        cache_service = CacheService()
        ttl = cache_service.get_ttl(despacho_id)
        
        return {
            "despacho_id": despacho_id,
            "ttl_seconds": ttl,
            "cached": ttl > 0
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo TTL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))