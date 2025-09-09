# app/services/sgd_service.py
import requests
from typing import List, Dict, Any
import base64
from ..config import settings
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
    
    def get_despacho_documents(self, despacho_id: str) -> List[Dict[str, Any]]:
        """Obtiene documentos de un despacho desde SGD"""
        try:
            url = f"{self.base_url}/{despacho_id}"
            logger.info(f"Llamando SGD: {url}")
            logger.info(f"Headers: {self.headers}")
            
            response = requests.get(url, headers=self.headers, timeout=30)
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            # Log respuesta raw
            response_text = response.text
            logger.info(f"Response raw (primeros 500 chars): {response_text[:500]}")
            
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Tipo de respuesta: {type(data)}")
            logger.info(f"SGD devolvió {len(data) if isinstance(data, list) else 0} documentos")
            
            # Log estructura completa para debug
            if isinstance(data, list) and len(data) > 0:
                first_doc_keys = list(data[0].keys())
                logger.info(f"Estructura primer documento: {first_doc_keys}")
            elif isinstance(data, dict):
                logger.info(f"Respuesta es dict con claves: {list(data.keys())}")
            else:
                logger.info(f"Respuesta es: {data}")
            
            # SGD devuelve {"data": [...]} no lista directa
            if isinstance(data, dict) and 'data' in data:
                documents = data['data']
                logger.info(f"Extrayendo {len(documents) if isinstance(documents, list) else 0} documentos del campo 'data'")
                return documents if isinstance(documents, list) else []
            
            return data if isinstance(data, list) else []
            
        except requests.RequestException as e:
            logger.error(f"Error HTTP obteniendo documentos SGD: {e}")
            logger.error(f"Response text: {response.text if 'response' in locals() else 'No response'}")
            return []
        except Exception as e:
            logger.error(f"Error general obteniendo documentos SGD: {e}")
            return []
    
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