# app/utils/rate_limiter.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
import redis
from ..config import settings

# Configurar Redis para rate limiting
redis_client = redis.from_url(settings.redis_url)

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    default_limits=[f"{settings.rate_limit_calls}/{settings.rate_limit_period}seconds"]
)