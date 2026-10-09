import os
import requests

from payment_crypto import decrypt_secret


YOCO_API_BASE = os.environ.get("YOCO_API_BASE", "https://payments.yoco.com/api").rstrip("/")


def _settings(business):
    settings = getattr(business, "settings", None)
    if settings is None:
        raise RuntimeError("Business payment settings are not configured.")
    return settings


def yoco_secret(business):
    return decrypt_secret(_settings(business).yoco_secret_key_encrypted)


def yoco_webhook_secret(business):
    return decrypt_secret(_settings(business).yoco_webhook_secret_encrypted)


def yoco_configured(business):
    settings = _settings(business)
    return bool(settings.yoco_enabled and yoco_secret(business))


def yoco_public_key(business):
    return (getattr(_settings(business), "yoco_public_key", "") or "").strip()


def create_checkout(appointment, business, base_url):
    """Create a hosted Yoco Checkout API session using this business's credentials."""
    secret = yoco_secret(business)
    if not secret or not _settings(business).yoco_enabled:
        raise RuntimeError("YOCO is not configured for this business.")

    amount_cents = int(round(float(appointment.amount_due) * 100))
    if amount_cents < 200:
        raise ValueError("Yoco card payments must be at least R2.00.")

    payload = {
        "amount": amount_cents,
        "currency": "ZAR",
        "successUrl": f"{base_url}/payment/yoco/success/{appointment.reference}",
        "cancelUrl": f"{base_url}/payment/yoco/cancel/{appointment.reference}",
        "failureUrl": f"{base_url}/payment/yoco/cancel/{appointment.reference}",
        "metadata": {
            "appointment_reference": appointment.reference,
            "business_id": str(business.id),
        },
    }

    headers = {
        "Authorization": f"Bearer {secret}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"appointment-{appointment.reference}",
    }

    response = requests.post(
        f"{YOCO_API_BASE}/checkouts",
        json=payload,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()

    redirect_url = data.get("redirectUrl") or data.get("redirect_url")
    checkout_id = data.get("id") or data.get("checkoutId")
    if not redirect_url or not checkout_id:
        raise RuntimeError(f"Yoco returned an unexpected checkout response: {data}")

    return checkout_id, redirect_url, data


def verify_checkout(appointment, business):
    """Verify the hosted checkout directly with YOCO after customer return."""
    secret = yoco_secret(business)
    if not secret or not _settings(business).yoco_enabled:
        raise RuntimeError("YOCO is not configured for this business.")

    checkout_id = (appointment.yoco_checkout_id or appointment.payment_reference or "").strip()
    if not checkout_id:
        raise RuntimeError("No YOCO checkout is attached to this appointment.")

    response = requests.get(
        f"{YOCO_API_BASE}/checkouts/{checkout_id}",
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    response.raise_for_status()
    return response.json()
