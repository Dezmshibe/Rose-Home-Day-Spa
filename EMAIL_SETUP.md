# Appoint Email Setup — Resend

Appoint now sends booking and payment emails through the Resend API instead of SMTP.

## 1. Install dependency

```bash
pip install -r requirements.txt
```

## 2. Environment variables

Set these environment variables on your local machine or hosting provider:

```text
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxx
MAIL_FROM=Appoint <your-verified-sender@yourdomain.com>
```

`RESEND_API_KEY` is your private Resend API key. Never commit it to GitHub or put it directly in `app.py`.

`MAIL_FROM` must be an address/sender that Resend permits you to send from. For a quick Resend test, Resend documents `onboarding@resend.dev` as a test sender. For production, use a verified domain/sender in Resend.

## 3. Render

In Render, open the Appoint service and add the same variables under Environment:

```text
RESEND_API_KEY=re_...
MAIL_FROM=Appoint <your-verified-sender@yourdomain.com>
```

Then redeploy.

## 4. Test

After logging in as a business owner, open:

```text
/test-email?to=your@email.com
```

The page reports whether Resend is configured. If the message fails, check the Render logs for the Resend error.

## 5. What emails are sent

- Customer booking confirmation for cash bookings.
- Customer booking confirmation after a YOCO payment is marked paid.
- Customer payment update when a payment is recorded.

The existing appointment and payment database logic is unchanged.
