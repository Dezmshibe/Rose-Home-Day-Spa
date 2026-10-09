"""
Seed a rich demo database for the Appoint platform.

Usage:
    python seed_demo.py

Drops and recreates all tables, then populates a demo business with
services, staff, and ~55 appointments spread across the current month.
"""

import os
import random
import secrets
from datetime import date, datetime, timedelta

from werkzeug.security import generate_password_hash
from flask import Flask

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Build a minimal Flask app for seeding (avoids importing app.py side effects)
from models import db, User, Business, BusinessSetting, Service, Staff, Appointment

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "booking.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


CUSTOMERS = [
    ("Thabo Mokoena",      "thabo@example.com",      "+27 82 111 0001"),
    ("Lerato Dlamini",     "lerato@example.com",     "+27 82 111 0002"),
    ("Sipho Ndlovu",       "sipho@example.com",      "+27 82 111 0003"),
    ("Naledi Khumalo",     "naledi@example.com",     "+27 82 111 0004"),
    ("Kabelo Mahlangu",    "kabelo@example.com",     "+27 82 111 0005"),
    ("Zanele Mthembu",     "zanele@example.com",     "+27 82 111 0006"),
    ("Mandla Zulu",        "mandla@example.com",     "+27 82 111 0007"),
    ("Precious Nkosi",     "precious@example.com",   "+27 82 111 0008"),
    ("Bongani Sithole",    "bongani@example.com",    "+27 82 111 0009"),
    ("Ayanda Mabaso",      "ayanda@example.com",     "+27 82 111 0010"),
    ("Katlego Modise",     "katlego@example.com",    "+27 82 111 0011"),
    ("Refilwe Tshabalala", "refilwe@example.com",    "+27 82 111 0012"),
    ("Themba Radebe",      "themba@example.com",     "+27 82 111 0013"),
    ("Lindiwe Mnguni",     "lindiwe@example.com",    "+27 82 111 0014"),
    ("Sibusiso Cele",      "sibusiso@example.com",   "+27 82 111 0015"),
]

NOTES = [
    "", "", "",
    "First-time client.",
    "Prefers morning slots.",
    "Repeat customer — knows the team.",
    "Requested extra time.",
    "Referred by a friend.",
    "",
    "Please confirm 30 min before.",
]


def ref():
    return "APT-" + secrets.token_hex(4).upper()


def make_appointment(business, service, staff, customer, when, payment_method,
                     payment_status, status):
    amount_due = float(service.price or 0)
    amount_paid = amount_due if payment_status == "paid" else 0

    return Appointment(
        reference=ref(),
        business_id=business.id,
        service_id=service.id,
        staff_id=staff.id if staff else None,
        customer_id=None,
        customer_name=customer[0],
        customer_email=customer[1],
        customer_phone=customer[2],
        date=when.date(),
        time=when.strftime("%H:%M"),
        notes=random.choice(NOTES),
        status=status,
        payment_method=payment_method,
        payment_status=payment_status,
        amount_due=amount_due,
        amount_paid=amount_paid,
        payment_reference=("CASH-" + ref()) if payment_method == "cash" and payment_status == "paid" else "",
        paid_at=datetime.utcnow() if payment_status == "paid" else None,
        payment_email_sent=payment_status == "paid",
    )


def seed_demo():
    with app.app_context():
        print("Dropping existing tables...")
        db.drop_all()

        print("Creating fresh schema...")
        db.create_all()

        # ---------------- Users ----------------
        admin = User(
            name="Platform Admin",
            email="admin@platform.local",
            password_hash=generate_password_hash("admin123"),
            role="platform_admin",
        )
        owner = User(
            name="Nomsa Mabaso",
            email="owner@brightstudio.local",
            password_hash=generate_password_hash("owner123"),
            role="business_owner",
        )
        db.session.add_all([admin, owner])
        db.session.flush()
        print(f"  Created users: admin id={admin.id}, owner id={owner.id}")

        # ---------------- Business ----------------
        business = Business(
            owner_id=owner.id,
            name="Bright Studio",
            slug="bright-studio",
            category="Beauty",
            description=(
                "A modern Johannesburg beauty studio offering hair, nails, "
                "and skin treatments in a calm, welcoming space."
            ),
            email="hello@brightstudio.com",
            phone="+27 11 000 0000",
            address="123 Main Street, Maboneng",
            city="Johannesburg",
            country="South Africa",
            status="active",
        )
        db.session.add(business)
        db.session.flush()
        print(f"  Created business: {business.name} id={business.id}")

        settings = BusinessSetting(
            business_id=business.id,
            slot_duration=30,
            open_time="09:00",
            close_time="18:00",
            working_days="0,1,2,3,4,5",
            cancellation_hours=24,
            cash_enabled=True,
            yoco_enabled=True,
            yoco_public_key="pk_test_demo_public_key_not_real",
            yoco_secret_key_encrypted="",
        )
        db.session.add(settings)

        # ---------------- Services ----------------
        services = [
            Service(business_id=business.id, name="Consultation",
                    description="Quick 30-minute consultation.",
                    duration=30, price=300, popular=True),
            Service(business_id=business.id, name="Haircut & Style",
                    description="Cut, wash, and blow-dry.",
                    duration=60, price=550, popular=True),
            Service(business_id=business.id, name="Gel Manicure",
                    description="Long-lasting gel nails.",
                    duration=45, price=420),
            Service(business_id=business.id, name="Deep Tissue Massage",
                    description="60-minute full-body massage.",
                    duration=60, price=850, popular=True),
            Service(business_id=business.id, name="Facial Treatment",
                    description="Cleansing, exfoliation, and hydration.",
                    duration=60, price=700),
            Service(business_id=business.id, name="Full Day Spa Package",
                    description="Massage, facial, and manicure.",
                    duration=180, price=2200),
        ]
        db.session.add_all(services)
        db.session.flush()
        print(f"  Created {len(services)} services")

        # ---------------- Staff ----------------
        staff_members = [
            Staff(business_id=business.id, name="Alex Mokoena",   role="Lead Stylist",      email="alex@brightstudio.com"),
            Staff(business_id=business.id, name="Taylor Nkosi",   role="Beauty Therapist",  email="taylor@brightstudio.com"),
            Staff(business_id=business.id, name="Jordan Dlamini", role="Nail Technician",   email="jordan@brightstudio.com"),
            Staff(business_id=business.id, name="Casey Mthembu",  role="Massage Therapist", email="casey@brightstudio.com"),
        ]
        db.session.add_all(staff_members)
        db.session.flush()
        print(f"  Created {len(staff_members)} staff members")

        # ---------------- Appointments ----------------
        today = date.today()
        first_of_month = today.replace(day=1)
        last_of_month = (first_of_month.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        # Collect working days: last 5 days of previous month + full current + first 7 of next
        candidate_days = []
        cursor = first_of_month - timedelta(days=5)
        while cursor < first_of_month:
            candidate_days.append(cursor)
            cursor += timedelta(days=1)
        cursor = first_of_month
        while cursor <= last_of_month:
            candidate_days.append(cursor)
            cursor += timedelta(days=1)
        cursor = last_of_month + timedelta(days=1)
        for _ in range(7):
            candidate_days.append(cursor)
            cursor += timedelta(days=1)

        working_days = [d for d in candidate_days if d.weekday() < 6]  # Mon–Sat

        slots = [
            "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
            "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "16:00", "16:30", "17:00",
        ]

        appointments = []
        used = set()
        target = 55
        attempts = 0
        max_attempts = 800

        while len(appointments) < target and attempts < max_attempts:
            attempts += 1
            day = random.choice(working_days)
            slot = random.choice(slots)

            if (day, slot) in used:
                continue
            used.add((day, slot))

            service = random.choice(services)
            staff = random.choice(staff_members)
            customer = random.choice(CUSTOMERS)

            if day < today:
                roll = random.random()
                if roll < 0.75:
                    method, pay_status, status = "cash", "paid", "completed"
                elif roll < 0.9:
                    method, pay_status, status = "yoco", "paid", "completed"
                else:
                    method, pay_status, status = "cash", "unpaid", "cancelled"
            elif day == today:
                roll = random.random()
                if roll < 0.4:
                    method, pay_status, status = "cash", "paid", "confirmed"
                elif roll < 0.7:
                    method, pay_status, status = "cash", "unpaid", "confirmed"
                else:
                    method, pay_status, status = "yoco", "paid", "confirmed"
            else:
                roll = random.random()
                if roll < 0.5:
                    method, pay_status, status = "cash", "unpaid", "confirmed"
                elif roll < 0.8:
                    method, pay_status, status = "yoco", "pending", "pending_payment"
                else:
                    method, pay_status, status = "cash", "paid", "confirmed"

            when = datetime.combine(day, datetime.strptime(slot, "%H:%M").time())
            appointments.append(make_appointment(
                business, service, staff, customer, when,
                method, pay_status, status
            ))

        db.session.add_all(appointments)
        db.session.commit()

        # ---------------- Summary ----------------
        total = Appointment.query.filter_by(business_id=business.id).count()
        by_status = {}
        for a in Appointment.query.filter_by(business_id=business.id).all():
            by_status[a.status] = by_status.get(a.status, 0) + 1

        print()
        print("=" * 60)
        print("  DEMO DATABASE READY")
        print("=" * 60)
        print(f"  Database:     {os.path.join(BASE_DIR, 'booking.db')}")
        print(f"  Business ID:  {business.id}")
        print(f"  Business:     {business.name}  (/business/{business.slug})")
        print(f"  Services:     {len(services)}")
        print(f"  Staff:        {len(staff_members)}")
        print(f"  Appointments: {total}")
        print(f"  By status:    {by_status}")
        print()
        print("  Login:")
        print("    Owner:  owner@brightstudio.local / owner123")
        print("    Admin:  admin@platform.local / admin123")
        print()
        print("  Open in browser:")
        print("    http://127.0.0.1:5000/business/calendar")
        print("=" * 60)


if __name__ == "__main__":
    seed_demo()