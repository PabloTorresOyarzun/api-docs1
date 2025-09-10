# Dockerfile.prod - Optimizado para producción
FROM python:3.11-slim as builder

# Instalar dependencias de compilación
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar requirements y instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip install --no-cache-dir -r requirements.txt

# Etapa final
FROM python:3.11-slim

# Instalar solo dependencias runtime necesarias
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copiar virtual environment desde builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Crear usuario no-root
RUN groupadd -r -g 1000 appuser && \
    useradd -r -g appuser -u 1000 appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/logs

WORKDIR /app

# Copiar código fuente
COPY --chown=appuser:appuser . .

# Cambiar a usuario no-root
USER appuser

# Variables de entorno para Python
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ready || exit 1

# Exponer puerto
EXPOSE 8000

# Comando por defecto
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]