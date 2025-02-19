"""SSL context configuration for MongoDB connections."""
from typing import List, Optional
import os
import ssl
import base64
from app.common.logging import get_logger

logger = get_logger(__name__)

def get_truststore_certs() -> List[str]:
    """Get certificates from environment variables starting with TRUSTSTORE_.
    
    Returns:
        List[str]: List of decoded certificate strings.
    """
    certs: List[str] = []
    
    for key, value in os.environ.items():
        if not key.startswith('TRUSTSTORE_') or not value:
            continue
            
        try:
            cert_data = base64.b64decode(value).decode('utf-8').strip()
            certs.append(cert_data)
        except Exception as e:
            logger.error(
                "Failed to decode certificate",
                extra={
                    "env_var": key,
                    "error": str(e)
                }
            )
    
    return certs

def create_ssl_context() -> Optional[ssl.SSLContext]:
    """Create SSL context with custom CA certificates if enabled.
    
    Returns:
        Optional[ssl.SSLContext]: Configured SSL context or None if disabled/no certs.
    """
    enable_secure_context = os.getenv('ENABLE_SECURE_CONTEXT', '').lower() == 'true'
    
    if not enable_secure_context:
        logger.info("Custom secure context is disabled")
        return None
        
    ssl_context = ssl.create_default_context()
    certs = get_truststore_certs()
    
    if not certs:
        logger.info('Could not find any TRUSTSTORE_ certificates')
        return None
        
    for cert in certs:
        try:
            ssl_context.load_verify_locations(cadata=cert)
        except Exception as e:
            logger.error(
                "Failed to load certificate",
                extra={"error": str(e)}
            )
            
    return ssl_context 