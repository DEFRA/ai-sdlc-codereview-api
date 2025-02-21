"""Unit tests for ID validation utilities."""
import pytest
from bson import ObjectId
from app.utils.id_validation import ensure_object_id


async def test_ensure_object_id_with_valid_string():
    """Test conversion of valid string to ObjectId."""
    # Given: A valid ObjectId string
    valid_id = str(ObjectId())
    
    # When: Converting to ObjectId
    result = ensure_object_id(valid_id)
    
    # Then: Should return ObjectId
    assert isinstance(result, ObjectId)
    assert str(result) == valid_id


async def test_ensure_object_id_with_object_id():
    """Test handling of existing ObjectId."""
    # Given: An existing ObjectId
    object_id = ObjectId()
    
    # When: Passing ObjectId
    result = ensure_object_id(object_id)
    
    # Then: Should return same ObjectId
    assert result == object_id


async def test_ensure_object_id_with_none():
    """Test handling of None value."""
    # Given/When: Passing None
    result = ensure_object_id(None)
    
    # Then: Should return None
    assert result is None


async def test_ensure_object_id_with_invalid_string():
    """Test handling of invalid ObjectId string."""
    # Given: An invalid ObjectId string
    invalid_id = "not-an-object-id"
    
    # When/Then: Should raise ValueError
    with pytest.raises(ValueError, match="Invalid ObjectId format"):
        ensure_object_id(invalid_id)


async def test_ensure_object_id_with_invalid_type():
    """Test handling of invalid type."""
    # Given: A value of invalid type
    invalid_value = 12345
    
    # When/Then: Should raise ValueError
    with pytest.raises(ValueError, match="Cannot convert type"):
        ensure_object_id(invalid_value) 