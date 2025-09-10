# app/services/sgd_service.py
import requests
from typing import List, Dict, Any, Optional, Tuple
import base64
from ..config import settings
from .cache_service import CacheService
import logging

logger = logging.getLogger(__name__)

class SGDService:
    def __init__(self):
        self.base_url = settings.sgd_base_url
        self.bearer_token = settings.sgd_bearer_token
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        self.cache = CacheService()
    
    def get_despacho_documents(self, despacho_id: str, use_cache: bool = True) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Obtiene documentos de un despacho desde SGD o cache
        Retorna: (documentos, from_cache)
        """
        # Intentar obtener desde cache si está habilitado
        if use_cache:
            cached_documents = self.cache.get_despacho_documents(despacho_id)
            if cached_documents is not None:
                return cached_documents, True
        
        # Si no hay cache o no se usa, obtener desde SGD
        try:
            url = f"{self.base_url}/{despacho_id}"
            logger.info(f"Obteniendo documentos desde SGD: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Extraer documentos según estructura de respuesta
            if isinstance(data, dict) and 'data' in data:
                documents = data['data']
            else:
                documents = data if isinstance(data, list) else []
            
            # Guardar en cache para futuras llamadas
            if use_cache and documents:
                self.cache.set_despacho_documents(despacho_id, documents)
            
            logger.info(f"SGD devolvió {len(documents)} documentos")
            return documents, False
            
        except requests.RequestException as e:
            logger.error(f"Error HTTP obteniendo documentos SGD: {e}")
            return [], False
        except Exception as e:
            logger.error(f"Error general obteniendo documentos SGD: {e}")
            return [], False
    
    def get_document_info(self, despacho_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de un documento específico"""
        documents, _ = self.get_despacho_documents(despacho_id)
        
        for doc in documents:
            doc_name = doc.get('nombre', doc.get('name', doc.get('filename', '')))
            if doc_name == document_id or doc_name == f"{document_id}.pdf" or doc_name.replace('.pdf', '') == document_id:
                return doc
        
        return None
    
    def decode_document(self, base64_content: str) -> bytes:
        """Decodifica documento base64 a PDF"""
        try:
            if not base64_content:
                logger.warning("Base64 content está vacío")
                return b""
                
            # Remover prefijo si existe
            if base64_content.startswith("data:application/pdf;base64,"):
                base64_content = base64_content.replace("data:application/pdf;base64,", "")
            
            decoded = base64.b64decode(base64_content)
            logger.info(f"Documento decodificado: {len(decoded)} bytes")
            return decoded
            
        except Exception as e:
            logger.error(f"Error decodificando documento: {e}")
            return b""
    
    def estimate_document_size(self, base64_content: str) -> int:
        """Estima el tamaño del documento en bytes"""
        try:
            # El tamaño aproximado es longitud de base64 * 3/4
            return len(base64_content) * 3 // 4
        except:
            return 0
    
    def count_pdf_pages(self, pdf_bytes: bytes) -> int:
        """Cuenta las páginas de un PDF"""
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = doc.page_count
            doc.close()
            return pages
        except Exception as e:
            logger.error(f"Error contando páginas: {e}")
            return 0