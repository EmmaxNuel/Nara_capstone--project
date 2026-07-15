import random
import logging
from django.core.cache import cache
from django.conf import settings
import requests

logger = logging.getLogger("nara")

OTP_TTL_SECONDS = 600  # 10 minutes
OTP_CACHE_PREFIX = "otp:"


def _otp_cache_key(phone):
    return f"{OTP_CACHE_PREFIX}{phone}"


def send_sms(phone, message):
    payload = {
        "to": phone,
        "from": settings.TERMII_SENDER_ID,
        "sms": message,
        "type": "plain",
        "channel": "dnd",
        "api_key": settings.TERMII_API_KEY,
    }
    try:
        response = requests.post(
            f"{settings.TERMII_BASE_URL}/sms/send",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("Termii SMS failed for %s: %s", phone, str(exc))
        return None


def send_whatsapp(phone, message):
    payload = {
        "to": phone,
        "from": settings.TERMII_SENDER_ID,
        "sms": message,
        "type": "plain",
        "channel": "whatsapp",
        "api_key": settings.TERMII_API_KEY,
    }
    try:
        response = requests.post(
            f"{settings.TERMII_BASE_URL}/sms/send",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        logger.error("Termii WhatsApp failed for %s: %s", phone, str(exc))
        return None


def send_otp(phone):
    otp = str(random.randint(100000, 999999))
    cache.set(_otp_cache_key(phone), otp, timeout=OTP_TTL_SECONDS)
    message = f"Your NARA verification code is {otp}. It expires in 10 minutes. Do not share it."
    logger.info("OTP for %s: %s", phone, otp)
    if settings.TERMII_API_KEY:
        send_sms(phone, message)
    return otp


def verify_otp(phone, submitted_otp):
    stored_otp = cache.get(_otp_cache_key(phone))
    if not stored_otp:
        return False
    if stored_otp != submitted_otp:
        return False
    # Delete immediately after successful verification — an OTP is single-use
    cache.delete(_otp_cache_key(phone))
    return True
