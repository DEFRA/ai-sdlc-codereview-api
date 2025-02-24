"""Unit tests for Anthropic client utility."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from anthropic import AsyncAnthropic, AsyncAnthropicBedrock
from app.utils.anthropic_client import (
    AnthropicClient, 
    DirectAnthropicClient,
    BedrockAnthropicClient,
    USE_BEDROCK,
    AnthropicClientProtocol,
    BaseAnthropicClient
)

from app.config.config import settings

@pytest.fixture
def mock_anthropic_response():
    """Create mock Anthropic response."""
    mock = MagicMock()
    mock.content = [MagicMock(text="Test response")]
    return mock

class TestAnthropicClient:
    """Test cases for AnthropicClient."""

    def setup_method(self):
        """Reset client instance before each test."""
        AnthropicClient._instance = None
        DirectAnthropicClient._instance = None
        BedrockAnthropicClient._instance = None

    async def test_get_client_creates_direct_instance(self):
        """Test direct client instance creation with valid API key."""
        # Given: No existing client instance and Bedrock disabled
        with patch('app.utils.anthropic_client.USE_BEDROCK', False), \
             patch('app.utils.anthropic_client.settings.ANTHROPIC_API_KEY', 'fake-api-key'):
            # When: Getting client instance
            client = AnthropicClient.get_client()
            
            # Then: Should return AsyncAnthropic instance
            assert isinstance(client, AsyncAnthropic)

    async def test_get_client_creates_bedrock_instance(self):
        """Test bedrock client instance creation with valid credentials."""
        # Given: No existing client instance and Bedrock enabled
        with patch('app.utils.anthropic_client.USE_BEDROCK', True):
            with patch('app.utils.anthropic_client.settings') as mock_settings:
                mock_settings.AWS_ACCESS_KEY = "test-key"
                mock_settings.AWS_SECRET_KEY = "test-secret"
                mock_settings.AWS_REGION = "test-region"

                # When: Getting client instance
                client = AnthropicClient.get_client()

                # Then: New Bedrock instance is created
                assert isinstance(client, AsyncAnthropicBedrock)
                assert isinstance(AnthropicClient._instance, BedrockAnthropicClient)

    async def test_get_client_raises_error_without_credentials(self):
        """Test error handling when credentials are missing."""
        # Given: No credentials in settings
        with patch('app.utils.anthropic_client.USE_BEDROCK', True):
            with patch('app.utils.anthropic_client.settings') as mock_settings:
                mock_settings.AWS_ACCESS_KEY = None
                mock_settings.AWS_SECRET_KEY = None
                mock_settings.AWS_REGION = None

                # When/Then: Getting client raises error
                with pytest.raises(ValueError, match="AWS credentials .* must be set for Bedrock"):
                    AnthropicClient.get_client()

    async def test_direct_client_raises_error_without_api_key(self):
        """Test error handling when API key is missing for direct client."""
        # Given: No API key in settings
        with patch('app.utils.anthropic_client.settings') as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None

            # When/Then: Getting client raises error
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY environment variable not set"):
                DirectAnthropicClient.get_client()

    async def test_create_message_with_direct_client(self, mock_anthropic_response):
        """Test message creation with direct client."""
        # Given: Mocked direct client instance
        with patch('app.utils.anthropic_client.USE_BEDROCK', False):
            mock_messages = AsyncMock()
            mock_messages.create = AsyncMock(return_value=mock_anthropic_response)

            mock_client = AsyncMock()
            mock_client.messages = mock_messages

            with patch.object(DirectAnthropicClient, 'get_client', return_value=mock_client):
                # When: Creating message
                response = await AnthropicClient.create_message(
                    prompt="Test prompt",
                    system_prompt="Test system prompt",
                    max_tokens=100,
                    temperature=0.8
                )

                # Then: Message is created with correct parameters
                assert response == "Test response"
                mock_messages.create.assert_called_once_with(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=100,
                    system="Test system prompt",
                    temperature=0.8,
                    messages=[{"role": "user", "content": "Test prompt"}]
                )

    async def test_create_message_with_bedrock_client(self, mock_anthropic_response):
        """Test message creation with bedrock client."""
        # Given: Mocked bedrock client instance
        with patch('app.utils.anthropic_client.USE_BEDROCK', True):
            mock_messages = AsyncMock()
            mock_messages.create = AsyncMock(return_value=mock_anthropic_response)

            mock_client = AsyncMock()
            mock_client.messages = mock_messages

            with patch.object(BedrockAnthropicClient, 'get_client', return_value=mock_client):
                with patch('app.utils.anthropic_client.settings') as mock_settings:
                    mock_settings.AWS_BEDROCK_MODEL = "test-bedrock-model"

                    # When: Creating message
                    response = await AnthropicClient.create_message(
                        prompt="Test prompt",
                        system_prompt="Test system prompt",
                        max_tokens=100,
                        temperature=0.8
                    )

                    # Then: Message is created with correct parameters
                    assert response == "Test response"
                    mock_messages.create.assert_called_once_with(
                        model="test-bedrock-model",
                        max_tokens=100,
                        system="Test system prompt",
                        temperature=0.8,
                        messages=[{"role": "user", "content": "Test prompt"}]
                    )

    async def test_create_message_handles_api_error(self, mock_anthropic_response):
        """Test error handling in message creation."""
        # Given: Mocked client that raises an error
        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(side_effect=Exception("API Error"))

        mock_client = AsyncMock()
        mock_client.messages = mock_messages

        with patch.object(DirectAnthropicClient, 'get_client', return_value=mock_client):
            # When/Then: Creating message raises error
            with pytest.raises(Exception, match="API Error"):
                await AnthropicClient.create_message(
                    prompt="Test prompt",
                    system_prompt="Test system prompt"
                )

# Test Protocol Implementation
class MockAnthropicClient(AnthropicClientProtocol):
    """Mock implementation of AnthropicClientProtocol."""
    async def messages(self):
        """Test implementation of messages method."""
        return AsyncMock()

async def test_anthropic_client_protocol():
    """Test AnthropicClientProtocol implementation."""
    # Given: A class implementing the protocol
    client = MockAnthropicClient()
    
    # When/Then: Messages method exists and returns
    messages = await client.messages()
    assert messages is not None


# Test Base Client Instance
async def test_base_anthropic_client_instance():
    """Test BaseAnthropicClient instance initialization."""
    # Given: A fresh BaseAnthropicClient subclass
    class TestClient(BaseAnthropicClient):
        @classmethod
        def get_client(cls):
            if cls._instance is None:  # Add instance initialization
                cls._instance = AsyncMock()
            return cls._instance
    
    # When: Accessing instance before initialization
    assert TestClient._instance is None
    
    # When: Getting client
    client = TestClient.get_client()
    
    # Then: Instance is set
    assert TestClient._instance is not None
    assert isinstance(client, AsyncMock)


async def test_create_message_response_error():
    """Test error handling when response structure is invalid."""
    # Given: A mocked client with invalid response structure
    mock_response = MagicMock()
    mock_response.content = []  # Empty content to trigger IndexError
    
    mock_messages = AsyncMock()
    mock_messages.create = AsyncMock(return_value=mock_response)
    
    mock_client = AsyncMock()
    mock_client.messages = mock_messages
    
    with patch.object(DirectAnthropicClient, 'get_client', return_value=mock_client):
        # When: Creating message
        result = await AnthropicClient.create_message(
            prompt="Test prompt",
            system_prompt="Test system prompt"
        )
        
        # Then: Should handle error and return empty string
        assert result == ""


async def test_create_message_attribute_error():
    """Test error handling when response lacks required attributes."""
    # Given: A mocked client with response missing attributes
    mock_response = MagicMock()
    delattr(mock_response, 'content')  # Remove content attribute to trigger AttributeError
    
    mock_messages = AsyncMock()
    mock_messages.create = AsyncMock(return_value=mock_response)
    
    mock_client = AsyncMock()
    mock_client.messages = mock_messages
    
    with patch.object(DirectAnthropicClient, 'get_client', return_value=mock_client):
        # When: Creating message
        result = await AnthropicClient.create_message(
            prompt="Test prompt",
            system_prompt="Test system prompt"
        )
        
        # Then: Should handle error and return empty string
        assert result == "" 