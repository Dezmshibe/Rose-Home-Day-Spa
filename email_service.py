import os
import resend


def _cfg(name, default=""):
    return os.environ.get(name, default).strip()


def email_enabled():
    """Return True when Resend is configured."""
    return bool(_cfg("RESEND_API_KEY") and _cfg("MAIL_FROM"))


def send_email(to, subject, html, text=None, reply_to=None):
    """Send an email through the Resend API.

    RESEND_API_KEY and MAIL_FROM must be configured in the environment.
    The API key is never stored in source code.
    """
    api_key = _cfg("RESEND_API_KEY")
    sender = _cfg("MAIL_FROM")

    if not api_key or not sender:
        print("Email not sent: Resend is not configured (RESEND_API_KEY/MAIL_FROM missing).")
        return False

    resend.api_key = api_key

    params = {
        "from": sender,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text
    if reply_to:
        params["reply_to"] = [reply_to]

    try:
        result = resend.Emails.send(params)
        print(f"Email sent successfully to {to}: {result}")
        return True
    except Exception as exc:
        print(f"Email send failed: {exc}")
        return False


def send_booking_confirmation(appointment):
    business = appointment.business

    if appointment.payment_method == "yoco" and appointment.payment_status == "paid":
        payment_html = f"""
          <p><strong>Payment method:</strong> YOCO · Paid online</p>
          <p><strong>Amount paid:</strong> R{appointment.amount_paid:,.2f}</p>
          <p><strong>Amount remaining:</strong> R{max(0, appointment.amount_due - appointment.amount_paid):,.2f}</p>
          <p><strong>Payment status:</strong> PAID</p>
        """
        payment_text = (
            f"Payment method: YOCO (paid online)\n"
            f"Amount paid: R{appointment.amount_paid:,.2f}\n"
            f"Amount remaining: R{max(0, appointment.amount_due - appointment.amount_paid):,.2f}\n"
            "Payment status: PAID"
        )
    else:
        payment_html = f"""
          <p><strong>Payment method:</strong> Cash / Pay in person</p>
          <p><strong>Amount to pay:</strong> R{appointment.amount_due:,.2f}</p>
          <p><strong>Amount paid:</strong> R{appointment.amount_paid:,.2f}</p>
          <p><strong>Payment status:</strong> PAYMENT DUE AT APPOINTMENT</p>
        """
        payment_text = (
            "Payment method: Cash / Pay in person\n"
            f"Amount to pay: R{appointment.amount_due:,.2f}\n"
            f"Amount paid: R{appointment.amount_paid:,.2f}\n"
            "Payment status: PAYMENT DUE AT APPOINTMENT"
        )

    subject = f"Appointment confirmed — {business.name}"
    html = f"""
    <!doctype html>
    <html>
      <body style="margin:0;background:#f5f7fb;font-family:Arial,sans-serif;color:#172033;">
        <div style="max-width:620px;margin:30px auto;background:#fff;border-radius:20px;padding:32px;box-shadow:0 8px 30px rgba(0,0,0,.08);">
          <div style="font-size:24px;font-weight:800;margin-bottom:24px;">Appoint<span style="color:#635bff;">.</span></div>
          <div style="display:inline-block;padding:7px 12px;border-radius:999px;background:#eaf8ef;color:#16733a;font-size:12px;font-weight:700;letter-spacing:.08em;">CONFIRMED</div>
          <h1 style="font-size:30px;margin:16px 0 8px;">You're booked.</h1>
          <p style="color:#667085;font-size:16px;">Hi {appointment.customer_name}, your appointment with <strong>{business.name}</strong> is confirmed.</p>
          <div style="background:#f7f7fb;border-radius:16px;padding:20px;margin:24px 0;">
            <p><strong>Service:</strong> {appointment.service.name}</p>
            <p><strong>Date:</strong> {appointment.date.strftime('%d %B %Y')}</p>
            <p><strong>Time:</strong> {appointment.time}</p>
            <p><strong>Reference:</strong> {appointment.reference}</p>
            <p><strong>Location:</strong> {business.address or 'See business profile'}{', ' + business.city if business.city else ''}</p>
          </div>
          <div style="background:#f7f7fb;border-radius:16px;padding:20px;margin:24px 0;">
            <h3 style="margin-top:0;">Payment</h3>
            {payment_html}
          </div>
          <p style="color:#667085;">Please keep your reference <strong>{appointment.reference}</strong> for your records.</p>
          <p style="margin-top:28px;">We look forward to seeing you!</p>
        </div>
      </body>
    </html>
    """
    text = (
        f"Hi {appointment.customer_name},\n\n"
        f"Your appointment with {business.name} is confirmed.\n\n"
        f"Service: {appointment.service.name}\n"
        f"Date: {appointment.date.strftime('%d %B %Y')}\n"
        f"Time: {appointment.time}\n"
        f"Reference: {appointment.reference}\n"
        f"Location: {business.address or 'See business profile'}"
        f"{', ' + business.city if business.city else ''}\n\n"
        f"PAYMENT\n{payment_text}\n\n"
        "We look forward to seeing you!"
    )
    return send_email(appointment.customer_email, subject, html, text)


def send_payment_update(appointment):
    business = appointment.business
    subject = f"Payment received — {business.name}"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:30px;">
      <h2>Payment received</h2>
      <p>Hi {appointment.customer_name}, we have recorded your payment for your appointment.</p>
      <p><strong>Reference:</strong> {appointment.reference}</p>
      <p><strong>Payment method:</strong> {appointment.payment_method.upper()}</p>
      <p><strong>Amount paid:</strong> R{appointment.amount_paid:,.2f}</p>
      <p><strong>Amount remaining:</strong> R{max(0, appointment.amount_due - appointment.amount_paid):,.2f}</p>
    </div>
    """
    text = (
        f"Payment received for {business.name}\n\n"
        f"Reference: {appointment.reference}\n"
        f"Payment method: {appointment.payment_method.upper()}\n"
        f"Amount paid: R{appointment.amount_paid:,.2f}\n"
        f"Amount remaining: R{max(0, appointment.amount_due - appointment.amount_paid):,.2f}"
    )
    return send_email(appointment.customer_email, subject, html, text)
