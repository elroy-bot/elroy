# Elroy does not set expectation for features that it does not actually have

import pytest


@pytest.mark.skip(reason="TODO")
def test_feature_description():
    pass
