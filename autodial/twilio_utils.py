from twilio.rest import Client
from autodial.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
from autodial.logger import get_logger

logger = get_logger("Autodial.Twilio")

def get_twilio_client() -> Client:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        logger.warning("Twilio credentials missing. Outbound dialing will fail.")
        return None
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

twilio_client = get_twilio_client()

def execute_dtmf(call_sid: str, digits: str):
    if not twilio_client or not call_sid:
        return
    try:
        formatted_digits = f"w{digits}w" 
        twilio_client.calls(call_sid).update(send_digits=formatted_digits)
        logger.info(f"[Twilio] Injected DTMF: {digits} into Call: {call_sid}")
    except Exception as e:
        logger.error(f"[Twilio] DTMF Failed: {e}")

import urllib.parse

def dial_out(target_number: str, host: str, context: str = None, goals: str = None, keywords: str = None, 
             broadcast_message: str = None, callback_url: str = None, system_instructions: str = None):
    if not twilio_client:
        logger.error("Cannot dial out, Twilio client is not initialized.")
        return None
        
    params = {}
    if context: params['context'] = context
    if goals: params['goals'] = goals
    if keywords: params['keywords'] = keywords
    if broadcast_message: params['broadcast_message'] = broadcast_message
    if callback_url: params['callback_url'] = callback_url
    if system_instructions: params['system_instructions'] = system_instructions
    
    query_string = f"?{urllib.parse.urlencode(params)}" if params else ""
    websocket_url = f"wss://{host}/media-stream{query_string}"
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""
    try:
        call = twilio_client.calls.create(
            twiml=twiml, to=target_number, from_=TWILIO_PHONE_NUMBER
        )
        logger.info(f"Dialing {target_number} | SID: {call.sid}")
        return call.sid
    except Exception as e:
        logger.error(f"Dialing failed: {e}")
        return None

def hangup_call(call_sid: str):
    if not twilio_client or not call_sid:
        return
    try:
        twilio_client.calls(call_sid).update(status="completed")
        logger.info(f"[Twilio] Hung up Call: {call_sid}")
    except Exception as e:
        logger.error(f"[Twilio] Hangup Failed: {e}")
