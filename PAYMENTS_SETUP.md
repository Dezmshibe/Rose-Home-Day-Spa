# YOCO + Cash Payments

## What is included

- Cash / Pay in person
- YOCO hosted online checkout
- Payment status on every appointment
- Amount due / amount paid / amount remaining
- Business dashboard payment visibility
- Business can mark cash payments as paid
- Customer payment information in confirmation emails
- Per-business YOCO credentials
- Encrypted storage for YOCO secret credentials
- Server-side YOCO checkout verification
- SQLite migration for existing databases

## Configure YOCO for a business

1. Log in as the business owner.
2. Open **Dashboard -> Settings**.
3. Under **Payment methods**, enable **YOCO online payments**.
4. Paste the YOCO **Test Public Key** into **YOCO Public Key**.
5. Paste the YOCO **Test Secret Key** into **YOCO Secret Key**.
6. Save the settings.

The secret key is encrypted before storage and is never sent to the customer's browser.

## No webhook setup for the business owner

Appoint uses the same simple flow as the proven payment reference: it creates a hosted YOCO checkout on the server, sends the customer to YOCO, then verifies the checkout directly with YOCO when the customer returns. This keeps webhook configuration out of the business settings screen.

## Important

- Keep YOCO secret keys server-side only.
- Use YOCO test credentials while testing.
- Do not mark an online appointment paid merely because the customer returned to the success URL. Appoint asks YOCO directly for the checkout status and checks the ZAR amount before marking it paid.
- Yoco expects amounts in cents internally, so R300.00 becomes 30000.
- Set a strong `SECRET_KEY` in production. It is also used to derive the encryption key for stored payment credentials. Changing it later makes previously stored encrypted credentials unreadable.

## Payment flow

Cash:

Customer books -> appointment confirmed -> email shows amount due -> business marks cash paid -> customer receives payment-received email.

YOCO:

Customer books -> appointment pending payment -> hosted YOCO checkout -> Appoint verifies checkout directly with YOCO -> appointment marked paid -> confirmation email shows amount paid and R0 remaining.
