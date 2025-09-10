# app/services/cache_service.py
import redis
import json
import hashlib
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url)
        self.default_ttl = 300  # 5 minutos por defecto
        
    def _generate_key(self, prefix: str, identifier: str) -> str:
        """Genera una clave única para cache"""
        return f"cache:{prefix}:{identifier}"
    
    def get_despacho_documents(self, despacho_id: str) -> Optional[List[Dict[str, Any]]]:
        """Obtiene documentos de despacho desde cache"""
        try:
            key = self._generate_key("despacho", despacho_id)
            cached_data = self.redis_client.get(key)
            
            if cached_data:
                logger.info(f"Cache hit para despacho {despacho_id}")
                data = json.loads(cached_data)
                return data.get('documents', [])
            
            logger.info(f"Cache miss para despacho {despacho_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo cache: {e}")
            return None
    
    def set_despacho_documents(self, despacho_id: str, documents: List[Dict[str, Any]], ttl: int = None):
        """Guarda documentos de despacho en cache"""
        try:
            key = self._generate_key("despacho", despacho_id)
            ttl = ttl or self.default_ttl
            
            data = {
                'documents': documents,
                'cached_at': datetime.utcnow().isoformat(),
                'ttl': ttl
            }
            
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(data, default=str)
            )
            logger.info(f"Despacho {despacho_id} guardado en cache por {ttl} segundos")
            
        except Exception as e:
            logger.error(f"Error guardando en cache: {e}")
    
    def get_processing_result(self, despacho_id: str, document_id: str = None) -> Optional[Dict[str, Any]]:
        """Obtiene resultado de procesamiento desde cache"""
        try:
            if document_id:
                key = self._generate_key("result", f"{despacho_id}:{document_id}")
            else:
                key = self._generate_key("result", despacho_id)
                
            cached_data = self.redis_client.get(key)
            
            if cached_data:
                logger.info(f"Resultado encontrado en cache para {key}")
                return json.loads(cached_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo resultado de cache: {e}")
            return None
    
    def set_processing_result(self, despacho_id: str, result: Dict[str, Any], document_id: str = None, ttl: int = 3600):
        """Guarda resultado de procesamiento en cache (1 hora por defecto)"""
        try:
            if document_id:
                key = self._generate_key("result", f"{despacho_id}:{document_id}")
            else:
                key = self._generate_key("result", despacho_id)
            
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(result, default=str)
            )
            logger.info(f"Resultado guardado en cache: {key}")
            
        except Exception as e:
            logger.error(f"Error guardando resultado en cache: {e}")
    
    def invalidate_despacho(self, despacho_id: str):
        """Invalida cache de un despacho"""
        try:
            # Invalidar documentos del despacho
            key = self._generate_key("despacho", despacho_id)
            self.redis_client.delete(key)
            
            # Invalidar resultados del despacho
            pattern = self._generate_key("result", f"{despacho_id}*")
            for key in self.redis_client.scan_iter(match=pattern):
                self.redis_client.delete(key)
                
            logger.info(f"Cache invalidado para despacho {despacho_id}")
            
        except Exception as e:
            logger.error(f"Error invalidando cache: {e}")
    
    def get_ttl(self, despacho_id: str) -> int:
        """Obtiene el TTL restante de un despacho en cache"""
        try:
            key = self._generate_key("despacho", despacho_id)
            ttl = self.redis_client.ttl(key)
            return ttl if ttl > 0 else 0
        except Exception as e:
            logger.error(f"Error obteniendo TTL: {e}")
            return 0