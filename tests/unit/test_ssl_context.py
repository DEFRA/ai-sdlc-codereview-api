"""Unit tests for SSL context configuration."""
import os
import base64
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from app.common.ssl_context import get_truststore_certs, get_mongodb_ssl_options


@pytest.fixture
def mock_cert():
    """Sample certificate fixture."""
    return """
    -----BEGIN CERTIFICATE-----
    MIICMTCCAZoCCQD01SSXK+AoETANBgkqhkiG9w0BAQsFADBdMQswCQYDVQQGEwJV
    UzELMAkGA1UECAwCQ0ExEDAOBgNVBAoMB0NvbXBhbnkxDDAKBgNVBAsMA09yZzEh
    MB8GA1UEAwwYdGVzdC5jZXJ0aWZpY2F0ZS5leGFtcGxlMB4XDTIwMDEwMTAwMDAw
    MFoXDTIxMDEwMTAwMDAwMFowXTELMAkGA1UEBhMCVVMxCzAJBgNVBAgMAkNBMRAw
    DgYDVQQKDAdDb21wYW55MQwwCgYDVQQLDANPcmcxITAfBgNVBAMMGHRlc3QuY2Vy
    dGlmaWNhdGUuZXhhbXBsZTCBnzANBgkqhkiG9w0BAQEFAAOBjQAwgYkCgYEA1K4c
    6oVhU0yF8P1jJAg6VE2RhRxM2B+QhA9Z4ADM9wQUqY0xQ7v0YuKQXYQqXC8qvovh
    P9bwfVQ5rZtFYZk1RhFz0JK2Kg5JKmEE3BQqFvxVvuPfR8P5MhZJc7UKkEVBZ7Dk
    XZ5R8jLNfCYNqX5+TGLNQVoG8Q5QQZrKq8LGwS0CAwEAATANBgkqhkiG9w0BAQsF
    AAOBgQCsqY0L4E8Tt9l0zr3whJjxHm1qNKHPqP0G1T8NHUHEgmKk8GwFYxEEDRxG
    XOKXkVvYXP6gYGxG0YUYvh5y9Q5Yw+QwK1E0hqwkL3+5GcPXwE0GhL9xA4pA3A5A
    w5QqH1wG3RYhzIWuvJxk9ZOHwf7cHxRGtBf5F7HEwGwW4Tg9Yg==
    -----END CERTIFICATE-----
    """


@pytest.fixture
def mock_env_vars(mock_cert):
    """Setup environment variables for testing."""
    cert_b64 = base64.b64encode(mock_cert.encode()).decode()
    env_vars = {
        "TRUSTSTORE_1": cert_b64,
        "ENABLE_SECURE_CONTEXT": "true"
    }
    with patch.dict(os.environ, env_vars, clear=True):
        yield env_vars


async def test_get_truststore_certs_scenarios():
    """Test various certificate retrieval scenarios."""
    # Given: Different certificate scenarios
    valid_cert = base64.b64encode(b"valid-cert").decode()
    scenarios = [
        ({}, 0),  # Empty environment
        ({"TRUSTSTORE_1": "invalid-base64"}, 0),  # Invalid base64
        ({"TRUSTSTORE_1": "invalid-base64", "TRUSTSTORE_2": valid_cert}, 1)  # Mixed valid/invalid
    ]
    
    for env_vars, expected_count in scenarios:
        # When: Get certificates
        with patch.dict(os.environ, env_vars, clear=True):
            certs = get_truststore_certs()
        
        # Then: Verify expected behavior
        assert len(certs) == expected_count


async def test_get_mongodb_ssl_options_scenarios(mock_env_vars):
    """Test SSL options in different scenarios."""
    scenarios = [
        ({"ENABLE_SECURE_CONTEXT": "false"}, False),
        ({"ENABLE_SECURE_CONTEXT": "true"}, False),
        (mock_env_vars, True)
    ]
    
    for env_vars, should_have_config in scenarios:
        # When: Get SSL options
        with patch.dict(os.environ, env_vars, clear=True):
            options, ca_file = get_mongodb_ssl_options()
            
        # Then: Verify configuration
        if should_have_config:
            assert options == {
                "tls": True,
                "tlsCAFile": ca_file,
                "tlsAllowInvalidCertificates": False
            }
            assert ca_file.endswith('.pem')
            # Cleanup
            if ca_file:
                os.unlink(ca_file)
        else:
            assert options == {}
            assert ca_file == ""


async def test_get_mongodb_ssl_options_error_handling(mock_env_vars):
    """Test error handling in SSL options."""
    # Given: Different error scenarios
    mock_file = MagicMock()
    mock_file.name = "/tmp/test.pem"
    mock_file.write.side_effect = Exception("Write failed")

    error_scenarios = [
        # Temp file creation fails
        patch("tempfile.NamedTemporaryFile", side_effect=Exception("Failed to create file")),
        # Write fails
        patch("tempfile.NamedTemporaryFile", return_value=mock_file)
    ]
    
    for scenario in error_scenarios:
        with scenario:
            # When: Get SSL options
            options, ca_file = get_mongodb_ssl_options()
            
            # Then: Should handle errors gracefully
            assert options == {}
            assert ca_file == "" 