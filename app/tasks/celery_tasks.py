# app/tasks/celery_tasks.py
from celery import Celery, Task
from ..services.document_processor import DocumentProcessor
from ..services.sgd_service import SGDService
from ..services.cache_service import CacheService
from ..config import settings
from ..models import ProcessingResult, ProcessingStatus, DocumentError, ProcessingMetadata
import base64
import requests
import logging
import time
import traceback

logger = logging.getLogger(__name__)

celery_app = Celery(
    "document_processor",
    broker=settings.redis_url,
    backend=settings.redis_url
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True
)

class CallbackTask(Task):
    """Task que reporta progreso"""
    def on_success(self, retval, task_id, args, kwargs):
        """Llamado cuando la tarea termina exitosamente"""
        webhook_url = kwargs.get('webhook_url')
        if webhook_url:
            try:
                self.send_webhook(webhook_url, task_id, 'completed', retval)
            except Exception as e:
                logger.error(f"Error enviando webhook: {e}")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Llamado cuando la tarea falla"""
        webhook_url = kwargs.get('webhook_url')
        if webhook_url:
            try:
                self.send_webhook(webhook_url, task_id, 'failed', {'error': str(exc)})
            except Exception as e:
                logger.error(f"Error enviando webhook: {e}")
    
    def send_webhook(self, url, task_id, status, data):
        """Envía notificación al webhook"""
        try:
            payload = {
                'task_id': task_id,
                'status': status,
                'timestamp': time.time(),
                'data': data
            }
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"Webhook enviado a {url}: {status}")
        except Exception as e:
            logger.error(f"Error enviando webhook a {url}: {e}")

@celery_app.task(bind=True, base=CallbackTask)
def process_individual_document(self, base64_content: str, document_id: str):
    """Tarea para procesar documento individual con progreso"""
    try:
        # Reportar inicio
        self.update_state(state='PROCESSING', meta={'progress': 0})
        
        processor = DocumentProcessor()
        pdf_bytes = base64.b64decode(base64_content)
        
        # Reportar progreso
        self.update_state(state='PROCESSING', meta={'progress': 50})
        
        result = processor.clasificar_y_procesar(pdf_bytes, document_id)
        
        # Reportar completado
        self.update_state(state='PROCESSING', meta={'progress': 100})
        
        return result.dict()
        
    except Exception as e:
        logger.error(f"Error procesando documento: {str(e)}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise

@celery_app.task(bind=True, base=CallbackTask)
def process_sgd_documents(self, despacho_id: str, webhook_url: str = None):
    """Tarea para procesar documentos de SGD con progreso y webhook"""
    try:
        start_time = time.time()
        
        # Reportar inicio
        self.update_state(state='PROCESSING', meta={'progress': 0, 'message': 'Obteniendo documentos'})
        
        sgd_service = SGDService()
        processor = DocumentProcessor()
        cache_service = CacheService()
        
        # Obtener documentos de SGD
        documents, from_cache = sgd_service.get_despacho_documents(despacho_id)
        
        if not documents:
            return {
                "status": "failed",
                "error": "No se encontraron documentos",
                "despacho_id": despacho_id
            }
        
        processed_documents = []
        failed_documents = []
        modelos_usados = set()
        total_docs = len(documents)
        
        for i, doc in enumerate(documents):
            # Calcular y reportar progreso
            progress = ((i + 1) / total_docs) * 100
            self.update_state(
                state='PROCESSING',
                meta={
                    'progress': progress,
                    'current': i + 1,
                    'total': total_docs,
                    'message': f'Procesando documento {i+1} de {total_docs}'
                }
            )
            
            doc_name = doc.get('nombre', doc.get('name', doc.get('filename', f"doc_{i}")))
            
            try:
                content_field = None
                for field in ['documento', 'content', 'base64', 'data']:
                    if field in doc:
                        content_field = field
                        break
                
                if not content_field:
                    failed_documents.append({
                        "document_id": doc_name,
                        "error_message": "Documento sin contenido",
                        "error_type": "MISSING_CONTENT"
                    })
                    continue
                
                pdf_bytes = sgd_service.decode_document(doc[content_field])
                if not pdf_bytes:
                    failed_documents.append({
                        "document_id": doc_name,
                        "error_message": "Error decodificando documento",
                        "error_type": "DECODE_ERROR"
                    })
                    continue
                
                result = processor.clasificar_y_procesar(pdf_bytes, doc_name)
                processed_documents.append(result.dict())
                
                # Registrar modelos usados
                for ext in result.extraction:
                    modelos_usados.add(f"extraction_{ext.document_type.value}")
                
            except Exception as e:
                logger.error(f"Error procesando documento {doc_name}: {str(e)}")
                failed_documents.append({
                    "document_id": doc_name,
                    "error_message": str(e),
                    "error_type": "PROCESSING_ERROR"
                })
        
        processing_time = time.time() - start_time
        
        # Determinar estado general
        if len(failed_documents) == 0:
            status = "success"
        elif len(processed_documents) == 0:
            status = "failed"
        else:
            status = "partial"
        
        result = {
            "despacho_id": despacho_id,
            "exitosos": processed_documents,
            "fallidos": failed_documents,
            "metadata": {
                "total_documentos": total_docs,
                "procesados": len(processed_documents),
                "fallidos": len(failed_documents),
                "tiempo_total": processing_time,
                "modelos_usados": list(modelos_usados),
                "cached": from_cache
            },
            "status": status
        }
        
        # Guardar en cache si fue exitoso
        if status != "failed":
            cache_service.set_processing_result(despacho_id, result)
        
        # Enviar webhook si se proporcionó
        if webhook_url:
            try:
                self.send_webhook(webhook_url, self.request.id, 'completed', result)
            except Exception as e:
                logger.error(f"Error enviando webhook: {e}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error en tarea de procesamiento: {str(e)}")
        logger.error(traceback.format_exc())
        
        error_result = {
            "status": "failed",
            "error": str(e),
            "despacho_id": despacho_id
        }
        
        # Enviar webhook de error si se proporcionó
        if webhook_url:
            try:
                self.send_webhook(webhook_url, self.request.id, 'failed', error_result)
            except:
                pass
        
        raise