import os

import pytest
from flask.testing import FlaskClient

from elroy.env.cloud.api import app


@pytest.fixture
def client():
    with app.test_client() as client:
        yield client


def test_routes(client: FlaskClient):
    assert "health" in app.url_map._rules_by_endpoint.keys()


def test_health_route(client: FlaskClient):
    response = client.get("/health")
    assert response.status_code == 200


def test_new_user(phone_number, client: FlaskClient):
    whatsapp_number = "whatsapp:" + phone_number

    response = client.post(
        "/receive_sms", data={"Body": "Test message", "From": whatsapp_number, "AccountSid": os.environ["TWILIO_ACCOUNT_SID"]}
    )
    assert response.status_code == 200
