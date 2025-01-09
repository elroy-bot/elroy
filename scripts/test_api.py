from elroy.api import Elroy

if __name__ == "__main__":
    elroy = Elroy()
    response = elroy.message("This is a test, repeat: Hello world!")
    assert "hello world" in response.lower()
