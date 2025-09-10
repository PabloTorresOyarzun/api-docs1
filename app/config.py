# app/config.py - Versión corregida sin errores
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Settings(BaseSettings):
    # Entorno
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Azure
    azure_endpoint: str = os.getenv("AZURE_ENDPOINT", "")
    azure_key: str = os.getenv("AZURE_KEY", "")
    azure_classification_model: str = os.getenv("AZURE_CLASSIFICATION_MODEL", "doctype_01")
    azure_invoice_model: str = os.getenv("AZURE_INVOICE_MODEL", "inovice_01")
    azure_transport_model: str = os.getenv("AZURE_TRANSPORT_MODEL", "transport_01")
    
    # SGD
    sgd_base_url: str = os.getenv("SGD_BASE_URL", "")
    sgd_bearer_token: str = os.getenv("SGD_BEARER_TOKEN", "")
    sgd_timeout: int = int(os.getenv("SGD_TIMEOUT", "30"))
    sgd_max_retries: int = int(os.getenv("SGD_MAX_RETRIES", "3"))
    
    # JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    redis_max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
    
    # Rate Limiting
    rate_limit_calls: int = int(os.getenv("RATE_LIMIT_CALLS", "100"))
    rate_limit_period: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))
    
    # Archivos
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    
    # Logs
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = os.getenv("LOG_FORMAT", "json")
    
    # Health checks
    health_check_timeout: int = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))
    
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024
    
    @property
    def allowed_origins(self) -> List[str]:
        """CORS origins - manejo seguro"""
        origins_str = os.getenv("ALLOWED_ORIGINS", "")
        
        if not origins_str.strip():
            # En desarrollo permitir todo, en producción denegar
            return ["*"] if self.is_development else []
        
        # Limpiar y separar por comas
        origins = [origin.strip() for origin in origins_str.split(",")]
        return [origin for origin in origins if origin]  # Filtrar vacíos
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"
    
    model_config = {
        "env_file": ".env",
        "extra": "allow"
    }

# Crear instancia
settings = Settings()

# Validaciones críticas solo para campos requeridos
def validate_required_settings():
    """Valida configuraciones críticas al inicio"""
    errors = []
    
    if not settings.azure_key:
        errors.append("AZURE_KEY es requerido")
    
    if not settings.azure_endpoint:
        errors.append("AZURE_ENDPOINT es requerido")
    
    if not settings.sgd_bearer_token:
        errors.append("SGD_BEARER_TOKEN es requerido")
    
    if not settings.sgd_base_url:
        errors.append("SGD_BASE_URL es requerido")
    
    if settings.is_production and settings.jwt_secret_key == "dev-secret-key":
        errors.append("JWT_SECRET_KEY debe cambiarse en producción")
    
    if errors:
        raise ValueError(f"Configuración inválida: {'; '.join(errors)}")

# Validar solo si no estamos en modo desarrollo sin credenciales
if settings.environment != "test":
    validate_required_settings()