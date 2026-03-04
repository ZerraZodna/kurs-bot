"""
Unit test for boolean parameter coercion.

Tests that string "true"/"false" are properly converted to boolean True/False.
"""

import pytest
from src.functions.parameters import ParameterValidator


def test_coerce_string_true_to_boolean():
    """Test that string 'true' is coerced to boolean True."""
    success, coerced, error = ParameterValidator.coerce_value("true", "boolean")
    
    assert success is True, f"Expected success=True but got error: {error}"
    assert coerced is True, f"Expected coerced=True but got: {coerced}"
    assert error is None


def test_coerce_string_false_to_boolean():
    """Test that string 'false' is coerced to boolean False."""
    success, coerced, error = ParameterValidator.coerce_value("false", "boolean")
    
    assert success is True, f"Expected success=True but got error: {error}"
    assert coerced is False, f"Expected coerced=False but got: {coerced}"
    assert error is None


def test_coerce_actual_boolean_true():
    """Test that actual boolean True passes through."""
    success, coerced, error = ParameterValidator.coerce_value(True, "boolean")
    
    assert success is True
    assert coerced is True
    assert error is None


def test_coerce_actual_boolean_false():
    """Test that actual boolean False passes through."""
    success, coerced, error = ParameterValidator.coerce_value(False, "boolean")
    
    assert success is True
    assert coerced is False
    assert error is None


def test_coerce_string_TRUE_uppercase():
    """Test that uppercase 'TRUE' is coerced to boolean True."""
    success, coerced, error = ParameterValidator.coerce_value("TRUE", "boolean")
    
    assert success is True, f"Expected success=True but got error: {error}"
    assert coerced is True, f"Expected coerced=True but got: {coerced}"


def test_coerce_string_FALSE_uppercase():
    """Test that uppercase 'FALSE' is coerced to boolean False."""
    success, coerced, error = ParameterValidator.coerce_value("FALSE", "boolean")
    
    assert success is True, f"Expected success=True but got error: {error}"
    assert coerced is False, f"Expected coerced=False but got: {coerced}"


def test_coerce_string_yes_to_boolean():
    """Test that string 'yes' is coerced to boolean True."""
    success, coerced, error = ParameterValidator.coerce_value("yes", "boolean")
    
    assert success is True, f"Expected success=True but got error: {error}"
    assert coerced is True, f"Expected coerced=True but got: {coerced}"


def test_coerce_string_no_to_boolean():
    """Test that string 'no' is coerced to boolean False."""
    success, coerced, error = ParameterValidator.coerce_value("no", "boolean")
    
    assert success is True, f"Expected success=True but got error: {error}"
    assert coerced is False, f"Expected coerced=False but got: {coerced}"


def test_coerce_integer_1_to_boolean():
    """Test that integer 1 is coerced to boolean True."""
    success, coerced, error = ParameterValidator.coerce_value(1, "boolean")
    
    assert success is True
    assert coerced is True


def test_coerce_integer_0_to_boolean():
    """Test that integer 0 is coerced to boolean False."""
    success, coerced, error = ParameterValidator.coerce_value(0, "boolean")
    
    assert success is True
    assert coerced is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
