# app/services/azure_service.py
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from typing import List, Dict, Any
import base64
from ..config import settings
from ..models import DocumentType, ClassificationResult, ExtractionResult

class AzureDocumentService:
    def __init__(self):
        self.client = DocumentAnalysisClient(
            endpoint=settings.azure_endpoint,
            credential=AzureKeyCredential(settings.azure_key)
        )
    
    def classify_document(self, pdf_bytes: bytes) -> DocumentType:
        """Clasifica un documento usando el modelo doctype_01"""
        try:
            poller = self.client.begin_classify_document(
                settings.azure_classification_model, 
                document=pdf_bytes
            )
            result = poller.result()
            
            # Obtener la clasificación con mayor confianza
            if result.documents:
                doc_type = result.documents[0].doc_type
                confidence = result.documents[0].confidence
                
                # Mapear tipos de documento
                type_mapping = {
                    "invoice": DocumentType.INVOICE,
                    "transport": DocumentType.TRANSPORT,
                    "packlist": DocumentType.PACKLIST
                }
                
                return type_mapping.get(doc_type, DocumentType.INVOICE)
            
            return DocumentType.INVOICE  # Default
            
        except Exception as e:
            print(f"Error en clasificación: {e}")
            return DocumentType.INVOICE  # Default en caso de error
    
    def extract_data(self, pdf_bytes: bytes, document_type: DocumentType) -> Dict[str, Any]:
        """Extrae datos del documento según su tipo"""
        try:
            # Seleccionar modelo según tipo de documento
            if document_type == DocumentType.TRANSPORT:
                model_name = "transport_01"
            elif document_type in [DocumentType.INVOICE, DocumentType.PACKLIST]:
                model_name = "inovice_01"  # Manteniendo el nombre con typo como está en specs
            else:
                model_name = "inovice_01"  # Default
            
            poller = self.client.begin_analyze_document(
                model_name,
                document=pdf_bytes
            )
            result = poller.result()
            
            extracted_data = {}
            
            # Extraer campos según el tipo de documento
            if result.documents:
                document = result.documents[0]
                for field_name, field in document.fields.items():
                    if field.value is not None:
                        extracted_data[field_name] = field.value
                        
            return extracted_data
            
        except Exception as e:
            print(f"Error en extracción: {e}")
            return {}