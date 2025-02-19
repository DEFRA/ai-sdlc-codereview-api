"""SSL context configuration for MongoDB connections."""
import os
import base64
import tempfile
from typing import Dict, Tuple
from app.common.logging import get_logger

logger = get_logger(__name__)

def get_truststore_certs() -> list[str]:
    """Get certificates from environment variables starting with TRUSTSTORE_.
    
    Reads base64 encoded certificates from environment variables and decodes them.
    
    Returns:
        list[str]: List of decoded certificate strings.
    """
    certs: list[str] = []
    
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

def get_mongodb_ssl_options() -> Tuple[Dict, str]:
    """Get MongoDB SSL options based on environment configuration.
    
    Creates a temporary file with CA certificates from environment variables
    when secure context is enabled.
    
    Returns:
        Tuple[Dict, str]: (MongoDB connection options, temp file path)
        - First element is dict with MongoDB TLS options
        - Second element is path to temp CA file (empty string if no file created)
    """
    if not os.getenv('ENABLE_SECURE_CONTEXT', '').lower() == 'true':
        logger.info("Custom secure context is disabled")
        return {}, ""
        
    certs = get_truststore_certs()
    if not certs:
        logger.info('Could not find any TRUSTSTORE_ certificates')
        return {}, ""
        
    try:
        # Create and populate temporary CA file
        temp_ca_file = tempfile.NamedTemporaryFile(
            mode='w',
            delete=False,
            suffix='.pem'
        )
        for cert in certs:
            temp_ca_file.write(f"{cert}\n")
        temp_ca_file.flush()
        
        # MongoDB TLS configuration
        return {
            "tls": True,
            "tlsCAFile": temp_ca_file.name,
            "tlsAllowInvalidCertificates": False
        }, temp_ca_file.name
        
    except Exception as e:
        logger.error("Failed to create SSL configuration", extra={"error": str(e)})
        if 'temp_ca_file' in locals():
            try:
                os.unlink(temp_ca_file.name)
            except Exception:
                pass
        return {}, ""