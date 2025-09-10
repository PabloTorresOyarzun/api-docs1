# app/main.py - Corregido
import logging
import logging.config  # FALTABA ESTE IMPORT
import time
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from slowapi.errors import RateLimitExceeded
from .routers import sgd, individual
from .utils.rate_limiter import limiter, _rate_limit_exceeded_handler
from .auth import create_access_token
from .config import settings
from datetime import timedelta
import redis
import psutil
import os

# Configurar logging con manejo de errores
def setup_logging():
    try:
        # Intentar crear directorio si no existe
        os.makedirs("/app/logs", exist_ok=True)
        
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                },
                "json": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                }
            },
            "handlers": {
                "file": {
                    "class": "logging.handlers.RotatingFileHandler", 
                    "filename": "/app/logs/api.log",
                    "maxBytes": 10485760,  # 10MB
                    "backupCount": 5,
                    "formatter": "json" if settings.log_format == "json" else "default",
                    "mode": "a"
                },
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default"
                }
            },
            "root": {
                "level": settings.log_level,
                "handlers": ["file", "console"]
            }
        }
        
        logging.config.dictConfig(log_config)
        
    except Exception as e:
        # Fallback a logging básico si falla
        logging.basicConfig(
            level=settings.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()]
        )
        print(f"Warning: Could not setup file logging, using console only: {e}")

setup_logging()
logger = logging.getLogger(__name__)

# Crear app FastAPI
app = FastAPI(
    title="API de Clasificación y Extracción de Documentos",
    description="API integrada con SGD para clasificar y extraer datos de documentos usando Azure Document Intelligence",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middleware GZip para compresión
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS configurado por entorno
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Variables globales para health checks
startup_time = time.time()
request_count = 0

# Middleware para logging y métricas
@app.middleware("http")
async def log_and_metrics_middleware(request: Request, call_next):
    global request_count
    start_time = time.time()
    request_count += 1
    
    # Log request (sin datos sensibles)
    logger.info(
        f"Request: {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent", "")[:100]
        }
    )
    
    try:
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} - {process_time:.4f}s",
            extra={
                "status_code": response.status_code,
                "process_time": process_time,
                "path": request.url.path
            }
        )
        
        # Agregar headers de timing
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = str(request_count)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {str(e)} - {process_time:.4f}s",
            extra={
                "error": str(e),
                "process_time": process_time,
                "path": request.url.path
            }
        )
        raise

# Middleware para validar tamaño de requests
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    if request.method in ["POST", "PUT", "PATCH"]:
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            if content_length > settings.max_file_size_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request too large. Max size: {settings.max_file_size_mb}MB"
                    }
                )
    
    return await call_next(request)

# Exception handlers personalizados
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    logger.warning(f"ValueError: {str(exc)}")
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc), "type": "validation_error"}
    )

@app.exception_handler(TimeoutError)
async def timeout_error_handler(request: Request, exc: TimeoutError):
    logger.error(f"TimeoutError: {str(exc)}")
    return JSONResponse(
        status_code=504,
        content={"detail": "Request timeout", "type": "timeout_error"}
    )

# Incluir routers
app.include_router(sgd.router)
app.include_router(individual.router)

@app.get("/")
async def root():
    """Redirige a la documentación en desarrollo"""
    if settings.is_development:
        return RedirectResponse(url="/docs")
    else:
        return {
            "service": "Document Processing API",
            "version": "1.0.0",
            "status": "healthy"
        }

@app.get("/health")
async def health_check():
    """Health check detallado"""
    try:
        # Verificar Redis
        redis_client = redis.from_url(settings.redis_url)
        redis_ping = redis_client.ping()
        redis_client.close()
        
        # Métricas del sistema
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        uptime = time.time() - startup_time
        
        health_data = {
            "status": "healthy",
            "service": "document-processing-api",
            "version": "1.0.0",
            "timestamp": time.time(),
            "uptime_seconds": uptime,
            "environment": settings.environment,
            "checks": {
                "redis": "ok" if redis_ping else "failed",
                "memory_usage_percent": memory.percent,
                "disk_usage_percent": disk.percent
            },
            "stats": {
                "requests_processed": request_count,
                "requests_per_second": request_count / uptime if uptime > 0 else 0
            }
        }
        
        # Determinar status general
        if memory.percent > 90 or disk.percent > 90 or not redis_ping:
            health_data["status"] = "degraded"
            
        return health_data
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": time.time()
            }
        )

@app.get("/health/ready")
async def readiness_check():
    """Readiness check para Kubernetes"""
    try:
        # Verificar dependencias críticas
        redis_client = redis.from_url(settings.redis_url)
        redis_client.ping()
        redis_client.close()
        
        return {"status": "ready"}
        
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )

@app.get("/metrics")
async def metrics():
    """Métricas básicas para monitoreo"""
    memory = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)
    uptime = time.time() - startup_time
    
    return {
        "requests_total": request_count,
        "uptime_seconds": uptime,
        "memory_usage_percent": memory.percent,
        "cpu_usage_percent": cpu,
        "requests_per_second": request_count / uptime if uptime > 0 else 0
    }

@app.post("/auth/token")
async def login():
    """Genera token JWT para autenticación"""
    # En producción, implementar autenticación real
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": "api_user"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Startup event
@app.on_event("startup")
async def startup_event():
    global startup_time
    startup_time = time.time()
    logger.info(f"API iniciada en modo {settings.environment}")
    logger.info(f"Allowed origins: {settings.allowed_origins}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("API cerrándose...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_config=None  # Usar nuestro logging config
    )