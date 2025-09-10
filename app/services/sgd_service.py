# app/services/sgd_service.py - Mejorado con timeouts y validaciones
import requests
from typing import List, Dict, Any, Optional, Tuple
import base64
from ..config import settings
from .cache_service import CacheService
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

logger = logging.getLogger(__name__)

class SGDService:
    def __init__(self):
        self.base_url = settings.sgd_base_url
        self.bearer_token = settings.sgd_bearer_token
        self.timeout = settings.sgd_timeout
        self.max_retries = settings.sgd_max_retries
        
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "DocumentProcessor/1.0"
        }
        
        # Configurar session con retry y pool de conexiones
        self.session = requests.Session()
        
        # Estrategia de retry
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.cache = CacheService()
    
    def get_despacho_documents(self, despacho_id: str, use_cache: bool = True) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Obtiene documentos de un despacho desde SGD o cache
        Retorna: (documentos, from_cache)
        """
        # Validar entrada
        if not despacho_id or not despacho_id.strip():
            raise ValueError("despacho_id no puede estar vacío")
        
        # Intentar obtener desde cache si está habilitado
        if use_cache:
            cached_documents = self.cache.get_despacho_documents(despacho_id)
            if cached_documents is not None:
                logger.info(f"Cache hit para despacho {despacho_id}")
                return cached_documents, True
        
        # Si no hay cache o no se usa, obtener desde SGD
        try:
            url = f"{self.base_url}/{despacho_id}"
            logger.info(f"Obteniendo documentos desde SGD: {url}")
            
            start_time = time.time()
            
            response = self.session.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout
            )
            
            request_time = time.time() - start_time
            logger.info(f"SGD respondió en {request_time:.2f}s")
            
            response.raise_for_status()
            
            data = response.json()
            
            # Extraer documentos según estructura de respuesta
            if isinstance(data, dict) and 'data' in data:
                documents = data['data']
            else:
                documents = data if isinstance(data, list) else []
            
            # Validar que tengamos documentos
            if not documents:
                logger.warning(f"SGD no devolvió documentos para despacho {despacho_id}")
                return [], False
            
            # Guardar en cache para futuras llamadas
            if use_cache and documents:
                self.cache.set_despacho_documents(despacho_id, documents)
            
            logger.info(f"SGD devolvió {len(documents)} documentos")
            return documents, False
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout obteniendo documentos SGD después de {self.timeout}s")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Error de conexión con SGD: {url}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP obteniendo documentos SGD: {e}")
            if e.response.status_code == 404:
                raise ValueError(f"Despacho {despacho_id} no encontrado")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de request obteniendo documentos SGD: {e}")
            raise
        except Exception as e:
            logger.error(f"Error general obteniendo documentos SGD: {e}")
            raise
    
    def get_document_info(self, despacho_id: str, document_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de un documento específico"""
        if not document_id or not document_id.strip():
            raise ValueError("document_id no puede estar vacío")
            
        documents, _ = self.get_despacho_documents(despacho_id)
        
        for doc in documents:
            doc_name = doc.get('nombre', doc.get('name', doc.get('filename', '')))
            if doc_name == document_id or doc_name == f"{document_id}.pdf" or doc_name.replace('.pdf', '') == document_id:
                return doc
        
        return None
    
    def decode_document(self, base64_content: str) -> bytes:
        """Decodifica documento base64 a PDF con validaciones"""
        try:
            if not base64_content:
                logger.warning("Base64 content está vacío")
                return b""
            
            # Validar tamaño estimado antes de decodificar
            estimated_size = self.estimate_document_size(base64_content)
            if estimated_size > settings.max_file_size_bytes:
                raise ValueError(f"Documento demasiado grande: {estimated_size / 1024 / 1024:.1f}MB (máximo: {settings.max_file_size_mb}MB)")
            
            # Remover prefijo si existe
            if base64_content.startswith("data:application/pdf;base64,"):
                base64_content = base64_content.replace("data:application/pdf;base64,", "")
            
            # Validar que es base64 válido
            try:
                decoded = base64.b64decode(base64_content, validate=True)
            except Exception as e:
                logger.error(f"Base64 inválido: {e}")
                raise ValueError("Contenido base64 inválido")
            
            # Validar que empiece como PDF
            if not decoded.startswith(b'%PDF'):
                logger.warning("El contenido decodificado no parece ser un PDF válido")
            
            logger.info(f"Documento decodificado: {len(decoded)} bytes")
            return decoded
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error decodificando documento: {e}")
            raise ValueError(f"Error decodificando documento: {e}")
    
    def estimate_document_size(self, base64_content: str) -> int:
        """Estima el tamaño del documento en bytes"""
        try:
            # El tamaño aproximado es longitud de base64 * 3/4
            return len(base64_content) * 3 // 4
        except Exception:
            return 0
    
    def count_pdf_pages(self, pdf_bytes: bytes) -> int:
        """Cuenta las páginas de un PDF"""
        try:
            if not pdf_bytes:
                return 0
                
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = doc.page_count
            doc.close()
            return pages
        except Exception as e:
            logger.error(f"Error contando páginas: {e}")
            return 0
    
    def validate_document(self, pdf_bytes: bytes) -> bool:
        """Valida que el documento sea un PDF válido"""
        try:
            if not pdf_bytes:
                return False
                
            # Verificar header PDF
            if not pdf_bytes.startswith(b'%PDF'):
                return False
                
            # Intentar abrir con PyMuPDF
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            is_valid = doc.page_count > 0
            doc.close()
            return is_valid
            
        except Exception:
            return False
    
    def __del__(self):
        """Cerrar session al destruir objeto"""
        if hasattr(self, 'session'):
            self.session.close()