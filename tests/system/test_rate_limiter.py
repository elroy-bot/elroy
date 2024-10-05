from elroy.system.rate_limiter import RateLimitExceeded, rate_limit


class Foo:
    def __init__(self):
        self.count = 0

    def increment(self):
        with rate_limit("increment", 1):
            self.count += 1
            return self.count

    def increment_retry(self):
        with rate_limit("increment_retry", 1, 3):
            self.count += 1
            return self.count


def test_fail():
    foo = Foo()
    assert foo.increment() == 1
    try:
        foo.increment()
    except RateLimitExceeded as e:
        assert str(e) == "Rate limit exceeded for increment after 0 retries"


def test_hapy():
    foo = Foo()
    assert foo.increment_retry() == 1
    assert foo.increment_retry() == 2
    assert foo.increment_retry() == 3
