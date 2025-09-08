# app/services/sgd_service.py
import requests
from typing import List, Dict, Any
import base64
from ..config import settings

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
            url = f"{self.base_url}/documentos64/despacho/{despacho_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            return data if isinstance(data, list) else []
            
        except Exception as e:
            print(f"Error obteniendo documentos SGD: {e}")
            return []
    
    def decode_document(self, base64_content: str) -> bytes:
        """Decodifica documento base64 a PDF"""
        try:
            return base64.b64decode(base64_content)
        except Exception as e:
            print(f"Error decodificando documento: {e}")
            return b""