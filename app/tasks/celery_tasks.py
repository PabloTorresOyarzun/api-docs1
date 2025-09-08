# app/tasks/celery_tasks.py
from celery import Celery
from ..services.document_processor import DocumentProcessor
from ..services.sgd_service import SGDService
from ..config import settings
import base64

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
)

@celery_app.task
def process_individual_document(base64_content: str, document_id: str):
    """Tarea para procesar documento individual"""
    try:
        processor = DocumentProcessor()
        pdf_bytes = base64.b64decode(base64_content)
        result = processor.process_document(pdf_bytes, document_id)
        return result.dict()
    except Exception as e:
        return {"error": str(e)}

@celery_app.task
def process_sgd_documents(despacho_id: str):
    """Tarea para procesar documentos de SGD"""
    try:
        sgd_service = SGDService()
        processor = DocumentProcessor()
        
        # Obtener documentos de SGD
        documents = sgd_service.get_despacho_documents(despacho_id)
        
        processed_documents = []
        for doc in documents:
            if 'content' in doc and 'id' in doc:
                pdf_bytes = sgd_service.decode_document(doc['content'])
                if pdf_bytes:
                    result = processor.process_document(pdf_bytes, str(doc['id']))
                    processed_documents.append(result.dict())
        
        return {
            "despacho_id": despacho_id,
            "documents": processed_documents
        }
    except Exception as e:
        return {"error": str(e)}