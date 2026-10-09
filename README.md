# Appoint Multi-Business Appointment Platform

Run:
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py

Open http://127.0.0.1:5000

Demo platform admin:
admin@platform.local / admin123

Demo business owner:
owner@brightstudio.local / owner123

This version introduces User -> Business -> Services / Staff / Appointments / Settings relationships and a business marketplace.


## Payments
See `PAYMENTS_SETUP.md` for YOCO test/live setup and the cash payment flow.


Payment UI fix: the booking form now visibly includes YOCO and Pay in person choices, the amount due, and a dynamic payment button.
