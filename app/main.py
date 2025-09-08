# app/main.py
import logging
import time
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi.errors import RateLimitExceeded
from .routers import sgd, individual
from .utils.rate_limiter import limiter, _rate_limit_exceeded_handler
from .auth import create_access_token
from datetime import timedelta

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("api.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Crear app FastAPI
app = FastAPI(
    title="API de Clasificación y Extracción de Documentos",
    description="API integrada con SGD para clasificar y extraer datos de documentos usando Azure Document Intelligence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    
    response = await call_next(request)
    
    # Log response
    process_time = time.time() - start_time
    logger.info(f"Response: {response.status_code} - {process_time:.4f}s")
    
    return response

# Incluir routers
app.include_router(sgd.router)
app.include_router(individual.router)

@app.get("/")
async def root():
    """Redirige a la documentación"""
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "document-processing-api"}

@app.post("/auth/token")
async def login():
    """Genera token JWT para autenticación (simplificado)"""
    # En producción, implementar autenticación real
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": "api_user"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Inicialización
import time
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)