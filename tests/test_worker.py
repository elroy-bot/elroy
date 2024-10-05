import random
from datetime import timedelta
from unittest.mock import patch

import pytest

from elroy.env.cloud.worker import _check_for_limits
from elroy.system.clock import FakeClock
from elroy.system.rate_limiter import (DAILY_WARNING_LIMIT,
                                       NON_PREMIUM_DAILY_MESSAGE_LIMIT)

get_user_id = lambda: random.randint(2, 100000)


@pytest.fixture
def mock_is_user_premium():
    with patch("elroy.store.user.is_user_premium") as mock:
        yield mock


def test_check_for_limits_premium_user(session, mock_is_user_premium):
    user_id = get_user_id()

    mock_is_user_premium.return_value = True

    result, warning = _check_for_limits(session, user_id)

    assert result is True
    assert warning is None


def test_check_for_limits_non_premium_user_within_limits(
    session,
    mock_is_user_premium,
):
    user_id = get_user_id()

    mock_is_user_premium.return_value = False

    result, warning = _check_for_limits(session, user_id)

    assert result is True
    assert warning is None


def test_check_for_limits_non_premium_user_exceeded_limit(session, mock_is_user_premium):
    user_id = get_user_id()

    mock_is_user_premium.return_value = False

    for i in range(NON_PREMIUM_DAILY_MESSAGE_LIMIT + 10):
        _check_for_limits(session, user_id)

    result, warning = _check_for_limits(session, user_id)

    assert result is False
    assert warning == "You have exceeded the daily message limit. Please try again tomorrow."


def test_check_for_limits_non_premium_user_silent_drop(session, mock_is_user_premium):
    user_id = get_user_id()

    mock_is_user_premium.return_value = False

    for i in range(NON_PREMIUM_DAILY_MESSAGE_LIMIT + DAILY_WARNING_LIMIT + 10):
        _check_for_limits(session, user_id)

    result, warning = _check_for_limits(session, user_id)

    assert result is False
    assert warning is None


def test_exceeded_rate_limit_resets(session, mock_is_user_premium):
    user_id = get_user_id()

    mock_is_user_premium.return_value = False

    for i in range(NON_PREMIUM_DAILY_MESSAGE_LIMIT + DAILY_WARNING_LIMIT + 10):
        _check_for_limits(session, user_id)

    FakeClock.advance(timedelta(days=1))

    result, warning = _check_for_limits(session, user_id)

    assert result is True
    assert warning is None
