"""
Centralized service endpoint configuration.

All service URLs (AI Review API, Chatbot API, etc.) are managed here.
This eliminates hardcoded URLs and enables deployment-time configuration.
"""

import os
from typing import Dict

# Service endpoint URLs - all configurable via environment variables
SERVICE_ENDPOINTS: Dict[str, str] = {
    # AI Code Review API
    'ai_review_api': os.getenv('AI_REVIEW_API_URL', 'http://localhost:8000'),
    
    # Chatbot API
    'chatbot_api': os.getenv('CHATBOT_API_URL', 'http://localhost:10000'),
    
    # Bitbucket API (Cloud)
    'bitbucket_api': os.getenv('BITBUCKET_API_URL', 'https://api.bitbucket.org/2.0'),
    
    # Bitbucket Server/Data Center (if using on-premise)
    'bitbucket_server': os.getenv('BITBUCKET_SERVER_URL', ''),
}

# CORS allowed origins - configure via environment
def get_allowed_origins() -> list:
    """
    Get list of allowed CORS origins from environment.
    
    Environment variable: ALLOWED_CORS_ORIGINS
    Format: comma-separated list
    Default: localhost development origins
    
    Example:
        ALLOWED_CORS_ORIGINS=https://app.example.com,https://dashboard.example.com
    
    Returns:
        List of allowed origins
    """
    default_origins = ['http://localhost:3000', 'http://localhost:8000', 'http://127.0.0.1:3000']
    
    env_origins = os.getenv('ALLOWED_CORS_ORIGINS', '')
    if env_origins:
        return [origin.strip() for origin in env_origins.split(',') if origin.strip()]
    
    return default_origins


def get_cors_config() -> dict:
    """
    Get CORS middleware configuration.
    
    Environment variables:
    - ALLOWED_CORS_ORIGINS: Comma-separated list of allowed origins
    - ENVIRONMENT: 'production' or 'development' (default: 'development')
    
    Returns:
        Dictionary with CORS configuration
    """
    environment = os.getenv('ENVIRONMENT', 'development').lower()
    allowed_origins = get_allowed_origins()
    
    if environment == 'production':
        # Strict production configuration
        allow_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
        allow_headers = [
            'Content-Type',
            'Authorization',
            'X-Requested-With',
        ]
    else:
        # Permissive development configuration
        allow_methods = ['*']
        allow_headers = ['*']
    
    return {
        'allow_origins': allowed_origins,
        'allow_credentials': True,
        'allow_methods': allow_methods,
        'allow_headers': allow_headers,
        'max_age': 3600,  # 1 hour CORS cache
    }


def get_service_url(service_name: str) -> str:
    """
    Get a service endpoint URL by name.
    
    Args:
        service_name: Name of service ('ai_review_api', 'chatbot_api', etc.)
    
    Returns:
        Service URL
    
    Raises:
        ValueError: If service_name not found
    """
    if service_name not in SERVICE_ENDPOINTS:
        raise ValueError(
            f"Unknown service: {service_name}. "
            f"Available services: {', '.join(SERVICE_ENDPOINTS.keys())}"
        )
    
    return SERVICE_ENDPOINTS[service_name]
