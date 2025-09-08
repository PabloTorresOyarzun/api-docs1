# app/config.py
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Azure
    azure_endpoint: str = os.getenv("AZURE_ENDPOINT")
    azure_key: str = os.getenv("AZURE_KEY")
    
    # SGD
    sgd_base_url: str = os.getenv("SGD_BASE_URL")
    sgd_bearer_token: str = os.getenv("SGD_BEARER_TOKEN")
    
    # JWT
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Rate Limiting
    rate_limit_calls: int = int(os.getenv("RATE_LIMIT_CALLS", "100"))
    rate_limit_period: int = int(os.getenv("RATE_LIMIT_PERIOD", "60"))
    
    class Config:
        env_file = ".env"

settings = Settings()