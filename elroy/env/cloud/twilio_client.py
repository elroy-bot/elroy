import logging
import os

from toolz import pipe
from twilio.rest import Client
from twilio.rest.api.v2010.account.message import MessageInstance

from elroy.system.rate_limiter import rate_limit

account_sid = lambda: os.environ["TWILIO_ACCOUNT_SID"]
auth_token = lambda: os.environ["TWILIO_AUTH_TOKEN"]
sender_number = lambda: os.environ["TWILIO_SENDER_NUMBER"]
message_service_sid = lambda: os.environ["TWILIO_MESSAGE_SERVICE_SID"]


def deliver_whatsapp_message(recipient_phone, message):
    if not recipient_phone.startswith("whatsapp:"):
        deliver_twilio_message("whatsapp:" + recipient_phone, message)
    else:
        deliver_twilio_message("whatsapp:" + recipient_phone, message)


def deliver_twilio_message(recipient_phone: str, message: str):
    assert account_sid(), "TWILIO_ACCOUNT_SID not set"
    assert auth_token(), "TWILIO_AUTH_TOKEN not set"
    assert sender_number(), "TWILIO_SENDER_NUMBER not set"
    assert message_service_sid(), "TWILIO_MESSAGE_SERVICE_SID not set"

    client = Client(account_sid(), auth_token())

    if recipient_phone.startswith("whatsapp:"):
        full_sender_number = "whatsapp:" + sender_number()
    else:
        full_sender_number = sender_number()

    pipe(
        _create_message(client, recipient_phone, full_sender_number, message),
        _check_result,
    )


def _create_message(client, recipient_phone, full_sender_number, message):
    with rate_limit(f"twilio_{recipient_phone}", 1, 5):
        return client.messages.create(body=message, to=recipient_phone, from_=full_sender_number, message_service_sid=message_service_sid())


def _check_result(result: MessageInstance):
    if result.error_code:
        logging.error("Twilio error: %s", result.error_message)
