import logging
import os

from flask import Flask, Response, request, send_from_directory
from twilio.twiml.messaging_response import MessagingResponse

from elroy.config import ROOT_DIR, session_manager
from elroy.env.cloud.twilio_client import account_sid
from elroy.env.cloud.worker import response_to_twilio_message
from elroy.onboard_user import onboard_user
from elroy.store.store import create_signup
from elroy.store.user import get_user_id_by_phone

app = Flask(__name__, static_folder=os.path.join(ROOT_DIR, "web"))
app.secret_key = os.environ.get("FLASK_SECRET_KEY")


@app.route("/receive_signup", methods=["POST"])
def receive_signup() -> Response:
    data = request.get_json()
    name = data.get("name")
    phone = data.get("phone")
    email = data.get("email")
    honeypot = data.get("url")

    if honeypot:
        logging.warning("Honeypot triggered")
        return Response(
            {
                "name": name,
                "phone": phone,
            },
            status=200,
            mimetype="application/json",
        )
    else:
        with session_manager() as session:
            logging.info(f"received form submission: {name}")
            create_signup(session, name=name, phone=phone, email=email)

        return Response(
            {
                "msg": "Form submitted",
                "name": name,
                "phone": phone,
            },
            status=200,
            mimetype="application/json",
        )


@app.route("/health", methods=["GET"])
def health():
    return {
        "body": {
            "message": "healthy",
        },
        "statusCode": 200,
    }


# sms and whatsapp
@app.route("/receive_sms", methods=["POST"])
def sms_receive() -> Response:

    if validate_request(request):
        received_msg = request.form.get("Body")
        assert received_msg
        sender_number = request.form.get("From")
        assert sender_number

        if sender_number.startswith("whatsapp:"):
            user_lookup_number = sender_number.replace("whatsapp:", "")
        else:
            user_lookup_number = sender_number

        with session_manager() as session:
            try:
                user_id = get_user_id_by_phone(session, user_lookup_number)
            except KeyError:
                user_id = onboard_user(session, sender_number)
        assert isinstance(user_id, int)

        logging.info("Received message from userid %s of length %s", user_id, len(received_msg))

        logging.info("Received message from userid %s of length %s", user_id, len(received_msg))

        response = response_to_twilio_message(session, user_id, received_msg)

        resp = MessagingResponse()

        if response:
            resp.message(response)
            return Response(str(resp), status=200, mimetype="text/xml")
        else:
            logging.error("dropping message")
            error_resp = """<?xml version="1.0" encoding="UTF-8"?>
                            <Response>
                                <Message>Invalid signature</Message>
                            </Response>"""
            return Response(error_resp, status=403, mimetype="text/xml")

    else:
        logging.error("failed validation")
        error_resp = """<?xml version="1.0" encoding="UTF-8"?>
                        <Response>
                            <Message>Invalid signature</Message>
                        </Response>"""
        return Response(error_resp, status=403, mimetype="text/xml")


@app.route("/receive_sms_fallback", methods=["POST"])
def sms_fallback() -> Response:
    if validate_request(request):
        logging.info("fallback triggered")
        return Response({"message": "received"}, status=200, mimetype="application/json")

    else:
        logging.error("rejecting fallback")
        return Response({"message": "invalid signature"}, status=403, mimetype="application/json")


@app.route("/twilio_status_callback", methods=["POST"])
def twilio_status_callback() -> Response:
    # Extract relevant information from the request
    message_sid = request.form.get("MessageSid")
    message_status = request.form.get("MessageStatus")
    error_code = request.form.get("ErrorCode")
    error_message = request.form.get("ErrorMessage")

    # Log the status callback information
    logging.info(f"Received status callback for MessageSid: {message_sid}")
    logging.info(f"Message Status: {message_status}")

    if error_code:
        logging.error(f"Error Code: {error_code}, Error Message: {error_message}")

    # Respond to Twilio (must respond with a 200 OK)
    return Response(status=204)


def validate_request(request) -> bool:
    # twilio validation library not working for some reason, instead match SID
    msg_sid = request.form.get("AccountSid")
    if not account_sid():
        logging.warning("No account_sid set")
        return False
    elif msg_sid != account_sid():
        # TODO: also match phone number against known numbers
        return False
    else:
        return True


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    if path != "" and os.path.exists(app.static_folder + "/" + path):  # type: ignore
        return send_from_directory(app.static_folder, path)  # type: ignore
    else:
        return send_from_directory(app.static_folder, "index.html")  # type: ignore


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
