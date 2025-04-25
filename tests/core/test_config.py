from elroy.core.config import ElroyConfig


def test_elroy_config_init():
    """Test that ElroyConfig initializes correctly with parameters."""
    config = ElroyConfig(test_param="test_value", another_param=123, bool_param=True)

    assert config.test_param == "test_value"
    assert config.another_param == 123
    assert config.bool_param is True


def test_elroy_config_missing_attribute():
    """Test that ElroyConfig handles missing attributes gracefully."""
    config = ElroyConfig(test_param="test_value")

    assert config.test_param == "test_value"
    assert config.non_existent_param is None


def test_elroy_config_nested_attributes():
    """Test that ElroyConfig can handle nested attributes."""
    config = ElroyConfig(nested={"key": "value", "number": 42})

    assert config.nested == {"key": "value", "number": 42}
