import os, re, secrets
from datetime import datetime, date, timedelta
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Business, BusinessSetting, Service, Staff, Appointment
from email_service import send_booking_confirmation, send_payment_update, email_enabled
from yoco_service import create_checkout, verify_checkout, yoco_configured
from payment_crypto import encrypt_secret

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "booking.db"))
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


PAYMENT_COLUMNS = {
    "payment_method": "VARCHAR(30) DEFAULT 'cash'",
    "payment_status": "VARCHAR(30) DEFAULT 'unpaid'",
    "amount_due": "FLOAT DEFAULT 0",
    "amount_paid": "FLOAT DEFAULT 0",
    "payment_reference": "VARCHAR(120) DEFAULT ''",
    "yoco_checkout_id": "VARCHAR(120) DEFAULT ''",
    "payment_email_sent": "BOOLEAN DEFAULT 0",
    "paid_at": "DATETIME",
}

BUSINESS_PAYMENT_COLUMNS = {
    "cash_enabled": "BOOLEAN DEFAULT 1",
    "yoco_enabled": "BOOLEAN DEFAULT 0",
    "yoco_public_key": "VARCHAR(255) DEFAULT ''",
    "yoco_secret_key_encrypted": "TEXT DEFAULT ''",
    "yoco_webhook_secret_encrypted": "TEXT DEFAULT ''",
}


def ensure_business_payment_columns():
    """Add per-business payment configuration to an existing SQLite database."""
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return
    from sqlalchemy import text
    with db.engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(business_setting)"))}
        for name, definition in BUSINESS_PAYMENT_COLUMNS.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE business_setting ADD COLUMN {name} {definition}"))


def ensure_payment_columns():
    """Add payment columns to an existing SQLite database without deleting data."""
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        return
    from sqlalchemy import text
    with db.engine.begin() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(appointment)"))}
        for name, definition in PAYMENT_COLUMNS.items():
            if name not in cols:
                conn.execute(text(f"ALTER TABLE appointment ADD COLUMN {name} {definition}"))


CATEGORIES = ["Barber", "Beauty", "Hair Salon", "Nails", "Massage", "Fitness",
              "Tutoring", "Photography", "Healthcare", "Automotive", "Other"]


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def slugify(value):
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value) or "business"


def unique_slug(name):
    base, slug, n = slugify(name), slugify(name), 2
    while Business.query.filter_by(slug=slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


def owner_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_business_owner():
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def get_owned_business():
    business_id = request.args.get("business_id", type=int)
    business = Business.query.filter_by(
        owner_id=current_user.id,
        **({"id": business_id} if business_id else {})
    ).order_by(Business.id).first()
    if not business:
        abort(404)
    return business


def reference():
    return "APT-" + secrets.token_hex(4).upper()


def seed():
    if User.query.filter_by(email="admin@platform.local").first():
        return
    admin = User(name="Platform Admin", email="admin@platform.local",
                 password_hash=generate_password_hash("admin123"), role="platform_admin")
    owner = User(name="Demo Owner", email="owner@brightstudio.local",
                 password_hash=generate_password_hash("owner123"), role="business_owner")
    db.session.add_all([admin, owner])
    db.session.flush()
    business = Business(owner_id=owner.id, name="Bright Studio", slug="bright-studio", category="Beauty",
                        description="A modern appointment business ready for online bookings.",
                        email="hello@brightstudio.com", phone="+27 11 000 0000",
                        address="123 Main Street", city="Johannesburg")
    db.session.add(business)
    db.session.flush()
    db.session.add(BusinessSetting(business_id=business.id))
    db.session.add_all([
        Service(business_id=business.id, name="Consultation",
                description="A quick consultation.", duration=30, price=300, popular=True),
        Service(business_id=business.id, name="Standard Appointment",
                description="Our most popular appointment.", duration=45, price=750, popular=True),
        Service(business_id=business.id, name="Deep Session",
                description="A longer premium session.", duration=90, price=1500),
    ])
    db.session.add_all([
        Staff(business_id=business.id, name="Alex", role="Lead Specialist"),
        Staff(business_id=business.id, name="Taylor", role="Specialist"),
    ])
    db.session.commit()


@app.context_processor
def inject_globals():
    return {"categories": CATEGORIES}


# =========================================================
# HOMEPAGE — single-business landing page
# =========================================================
@app.route("/")
def home():
    """Single-business mode: homepage IS the business landing page."""
    business = Business.query.filter_by(status="active").order_by(Business.id).first()

    if not business:
        return render_template("index.html", business=None)

    services = (
        Service.query
        .filter_by(business_id=business.id, active=True)
        .order_by(Service.popular.desc(), Service.name)
        .all()
    )
    staff = Staff.query.filter_by(business_id=business.id, active=True).all()

    return render_template(
        "index.html",
        business=business,
        services=services,
        staff=staff,
    )


@app.route("/business/<slug>")
def business_profile(slug):
    business = Business.query.filter_by(slug=slug, status="active").first_or_404()
    services = Service.query.filter_by(business_id=business.id, active=True).order_by(Service.popular.desc(), Service.name).all()
    staff = Staff.query.filter_by(business_id=business.id, active=True).all()
    return render_template("business/profile.html", business=business, services=services, staff=staff)


@app.route("/book/<slug>", methods=["GET", "POST"])
def book(slug):
    business = Business.query.filter_by(slug=slug, status="active").first_or_404()
    services = Service.query.filter_by(business_id=business.id, active=True).order_by(Service.name).all()
    staff = Staff.query.filter_by(business_id=business.id, active=True).all()

    selected_service = None
    selected_service_id = request.args.get("service_id", type=int)
    if selected_service_id:
        selected_service = Service.query.filter_by(
            id=selected_service_id,
            business_id=business.id,
            active=True,
        ).first()
        if not selected_service:
            flash("That service is no longer available. Please choose another service.", "warning")
            return redirect(url_for("business_profile", slug=slug))

    if request.method == "POST":
        service = db.session.get(Service, request.form.get("service_id", type=int))
        if not service or service.business_id != business.id or not service.active:
            flash("Please choose a valid service.", "danger")
            return redirect(url_for("book", slug=slug))

        try:
            booking_date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            flash("Please choose a valid date.", "danger")
            return redirect(url_for("book", slug=slug))

        if booking_date < date.today():
            flash("Please choose a future date.", "danger")
            return redirect(url_for("book", slug=slug))

        appointment_time = request.form.get("time", "")
        existing = Appointment.query.filter_by(
            business_id=business.id, date=booking_date, time=appointment_time,
        ).filter(Appointment.status.in_(["confirmed", "pending", "pending_payment"])).first()
        if existing:
            flash("That time is no longer available. Please choose another slot.", "warning")
            return redirect(url_for("book", slug=slug))

        payment_method = request.form.get("payment_method", "cash").lower()
        payment_settings = business.settings or BusinessSetting(business_id=business.id)
        if payment_method == "cash" and not payment_settings.cash_enabled:
            flash("This business is not accepting pay-in-person bookings right now.", "danger")
            return redirect(url_for("book", slug=slug))
        if payment_method == "yoco" and not payment_settings.yoco_enabled:
            flash("Online YOCO payments are not enabled for this business.", "danger")
            return redirect(url_for("book", slug=slug))
        if payment_method == "yoco" and not yoco_configured(business):
            flash("Online payments are not fully configured for this business yet.", "danger")
            return redirect(url_for("book", slug=slug))
        if payment_method not in {"cash", "yoco"}:
            flash("Please choose a valid payment method.", "danger")
            return redirect(url_for("book", slug=slug))

        customer = current_user if current_user.is_authenticated else None
        amount_due = float(service.price or 0)

        if payment_method == "yoco" and amount_due < 2:
            flash("Online YOCO payments require the service price to be at least R2.00.", "danger")
            return redirect(url_for("book", slug=slug))

        appointment = Appointment(
            reference=reference(),
            business_id=business.id,
            service_id=service.id,
            staff_id=request.form.get("staff_id", type=int) or None,
            customer_id=customer.id if customer else None,
            customer_name=request.form["customer_name"].strip(),
            customer_email=request.form["customer_email"].strip(),
            customer_phone=request.form["customer_phone"].strip(),
            date=booking_date,
            time=appointment_time,
            notes=request.form.get("notes", "").strip(),
            status="confirmed" if payment_method == "cash" else "pending_payment",
            payment_method=payment_method,
            payment_status="unpaid" if payment_method == "cash" else "pending",
            amount_due=amount_due,
            amount_paid=0,
        )
        db.session.add(appointment)
        db.session.commit()

        if payment_method == "cash":
            email_sent = send_booking_confirmation(appointment)
            if email_sent:
                appointment.payment_email_sent = True
                db.session.commit()
            flash("Booking confirmed. The customer will pay in person.", "success")
            return redirect(url_for("confirmation", reference=appointment.reference))

        try:
            base_url = request.url_root.rstrip("/")
            checkout_id, redirect_url, _ = create_checkout(appointment, business, base_url)
            appointment.yoco_checkout_id = checkout_id
            appointment.payment_reference = checkout_id
            db.session.commit()
            return redirect(redirect_url)
        except Exception:
            app.logger.exception("YOCO checkout creation failed")
            db.session.delete(appointment)
            db.session.commit()
            flash("We could not start the YOCO payment. No appointment was created. Please try again.", "danger")
            return redirect(url_for("book", slug=slug))

    return render_template(
        "book.html",
        business=business,
        services=services,
        staff=staff,
        selected_service=selected_service,
    )


@app.route("/test-email")
@owner_required
def test_email():
    recipient = request.args.get("to", "").strip().lower()
    if not recipient:
        return (
            "<h2>Email test</h2>"
            "<p>Add <code>?to=your@email.com</code> to this URL.</p>"
            "<p>Example: <code>/test-email?to=you@example.com</code></p>"
            "<p>Email provider: <strong>Resend</strong></p>"
            f"<p>Resend configured: <strong>{'yes' if email_enabled() else 'no'}</strong></p>"
        )
    from email_service import send_email
    ok = send_email(
        recipient,
        "Appoint email test",
        "<h1>Appoint email test</h1><p>If you received this, email delivery is working.</p>",
        "Appoint email test\n\nIf you received this, email delivery is working.",
    )
    if ok:
        return "<h2>Email sent</h2><p>Check the recipient inbox.</p>"
    return "<h2>Email not sent</h2><p>Check the terminal for the Resend error and your environment variables.</p>", 500


@app.route("/payment/yoco/success/<reference>")
def yoco_success(reference):
    appointment = Appointment.query.filter_by(reference=reference).first_or_404()

    if appointment.payment_method != "yoco":
        flash("This appointment does not use YOCO.", "warning")
        return redirect(url_for("confirmation", reference=reference))

    if appointment.payment_status == "paid":
        return redirect(url_for("confirmation", reference=reference))

    try:
        result = verify_checkout(appointment, appointment.business)
    except Exception:
        app.logger.exception("YOCO payment verification failed for %s", reference)
        flash("We could not verify the YOCO payment yet. Please refresh in a moment.", "warning")
        return redirect(url_for("confirmation", reference=reference))

    status = str(result.get("status", "")).strip().lower()
    if status != "completed":
        flash("YOCO has not confirmed this payment yet. Please refresh in a moment.", "info")
        return redirect(url_for("confirmation", reference=reference))

    currency = str(result.get("currency", "ZAR")).upper()
    expected = round(float(appointment.amount_due), 2)
    candidates = [
        result.get("amount"),
        (result.get("amountDetails") or {}).get("amount") if isinstance(result.get("amountDetails"), dict) else None,
    ]
    supplied = None
    for value in candidates:
        try:
            if value is not None:
                number = float(value)
                supplied = round(number / 100 if number > expected * 10 else number, 2)
                break
        except (TypeError, ValueError):
            pass

    if currency != "ZAR" or (supplied is not None and supplied != expected):
        app.logger.warning("YOCO payment mismatch for %s", reference)
        flash("The YOCO payment details could not be matched to this appointment.", "danger")
        return redirect(url_for("confirmation", reference=reference))

    appointment.payment_status = "paid"
    appointment.amount_paid = expected
    appointment.payment_reference = result.get("id") or appointment.yoco_checkout_id or appointment.payment_reference
    appointment.paid_at = datetime.utcnow()
    appointment.status = "confirmed"

    if not appointment.payment_email_sent:
        if send_booking_confirmation(appointment):
            appointment.payment_email_sent = True

    db.session.commit()
    flash("YOCO payment confirmed. Your appointment is booked.", "success")
    return redirect(url_for("confirmation", reference=reference))


@app.route("/payment/yoco/cancel/<reference>")
def yoco_cancel(reference):
    appointment = Appointment.query.filter_by(reference=reference).first_or_404()
    if appointment.payment_status != "paid":
        appointment.payment_status = "failed"
        appointment.status = "cancelled"
        db.session.commit()
    flash("YOCO payment was cancelled or did not complete. The appointment was not confirmed.", "warning")
    return redirect(url_for("confirmation", reference=reference))


@app.route("/business/appointments/<int:appointment_id>/mark-paid", methods=["POST"])
@owner_required
def mark_cash_paid(appointment_id):
    business = get_owned_business()
    appointment = Appointment.query.filter_by(id=appointment_id, business_id=business.id).first_or_404()

    if appointment.payment_method != "cash":
        flash("Only pay-in-person appointments can be marked paid manually.", "warning")
        return redirect(url_for("dashboard", business_id=business.id))

    if appointment.payment_status == "paid":
        flash("This appointment is already marked paid.", "info")
        return redirect(url_for("dashboard", business_id=business.id))

    appointment.amount_paid = appointment.amount_due
    appointment.payment_status = "paid"
    appointment.payment_reference = "CASH-" + appointment.reference
    appointment.paid_at = datetime.utcnow()
    if appointment.status == "pending_payment":
        appointment.status = "confirmed"

    if not appointment.payment_email_sent:
        if send_payment_update(appointment):
            appointment.payment_email_sent = True

    db.session.commit()
    flash("Cash payment marked as paid.", "success")
    return redirect(url_for("dashboard", business_id=business.id))


@app.route("/confirmation/<reference>")
def confirmation(reference):
    return render_template("confirmation.html", appointment=Appointment.query.filter_by(reference=reference).first_or_404())


@app.route("/cancel/<reference>", methods=["POST"])
def cancel(reference):
    appointment = Appointment.query.filter_by(reference=reference).first_or_404()
    appointment.status = "cancelled"
    db.session.commit()
    flash("Your appointment has been cancelled.", "success")
    return redirect(url_for("confirmation", reference=reference))


@app.route("/api/slots")
def slots():
    business = db.session.get(Business, request.args.get("business_id", type=int))
    service = db.session.get(Service, request.args.get("service_id", type=int))
    try:
        chosen = datetime.strptime(request.args.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []}), 400
    if not business or not service or service.business_id != business.id:
        return jsonify({"slots": []}), 400
    settings = business.settings or BusinessSetting(business_id=business.id)
    if str(chosen.weekday()) not in settings.working_days.split(","):
        return jsonify({"slots": []})
    start = datetime.combine(chosen, datetime.strptime(settings.open_time, "%H:%M").time())
    end = datetime.combine(chosen, datetime.strptime(settings.close_time, "%H:%M").time())
    booked = {a.time for a in Appointment.query.filter_by(business_id=business.id, date=chosen)
              .filter(Appointment.status.in_(["confirmed", "pending", "pending_payment"])).all()}
    result = []
    cursor = start
    duration = timedelta(minutes=service.duration)
    while cursor + duration <= end:
        label = cursor.strftime("%H:%M")
        if label not in booked:
            result.append(label)
        cursor += timedelta(minutes=settings.slot_duration or 30)
    return jsonify({"slots": result})


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"].strip().lower()).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            login_user(user)
            return redirect(url_for("dashboard") if user.is_business_owner() else url_for("home"))
        flash("Incorrect email or password.", "danger")
    return render_template("auth/login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = request.form.get("role", "customer")
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "warning")
            return redirect(url_for("register"))
        user = User(name=name, email=email,
                    password_hash=generate_password_hash(password),
                    role="business_owner" if role == "business_owner" else "customer")
        db.session.add(user)
        db.session.commit()
        login_user(user)
        if user.role == "business_owner":
            return redirect(url_for("dashboard"))
        flash("Welcome! Your account is ready.", "success")
        return redirect(url_for("home"))
    return render_template("auth/register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


@app.route("/dashboard")
@owner_required
def dashboard():
    business = get_owned_business()
    appointments = Appointment.query.filter_by(business_id=business.id).order_by(
        Appointment.date.desc(), Appointment.time.desc()).limit(25).all()
    total = Appointment.query.filter_by(business_id=business.id).count()
    upcoming = (
        Appointment.query.filter_by(business_id=business.id, date=date.today(), status="confirmed").count()
        + Appointment.query.filter_by(business_id=business.id, status="confirmed").filter(Appointment.date > date.today()).count()
    )
    revenue = sum((a.amount_paid or 0) for a in Appointment.query.filter_by(business_id=business.id, payment_status="paid").all())
    return render_template("business/dashboard.html", business=business, appointments=appointments,
                           total=total, upcoming=upcoming, revenue=revenue)


@app.route("/business/calendar")
@owner_required
def calendar():
    business = get_owned_business()
    staff_members = Staff.query.filter_by(business_id=business.id, active=True).order_by(Staff.name).all()
    return render_template("business/calendar.html", business=business, staff=staff_members)


@app.route("/api/calendar/appointments")
@owner_required
def calendar_appointments():
    business = get_owned_business()
    month_param = request.args.get("month", "").strip()
    staff_id = request.args.get("staff_id", type=int)

    try:
        year, month = (int(x) for x in month_param.split("-"))
        first_day = date(year, month, 1)
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid month. Use YYYY-MM."}), 400

    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)

    query = Appointment.query.filter(
        Appointment.business_id == business.id,
        Appointment.date >= first_day,
        Appointment.date <= last_day,
        Appointment.status.in_(["confirmed", "pending", "pending_payment", "completed"]),
    )
    if staff_id:
        query = query.filter(Appointment.staff_id == staff_id)

    appointments = query.order_by(Appointment.date, Appointment.time).all()

    days = {}
    for appt in appointments:
        key = appt.date.isoformat()
        days.setdefault(key, []).append({
            "id": appt.id,
            "time": appt.time,
            "reference": appt.reference,
            "customer_name": appt.customer_name,
            "customer_phone": appt.customer_phone,
            "service": appt.service.name if appt.service else "—",
            "staff_id": appt.staff_id,
            "staff_name": appt.staff.name if appt.staff else None,
            "status": appt.status,
            "payment_method": appt.payment_method,
            "payment_status": appt.payment_status,
            "amount_due": float(appt.amount_due or 0),
            "amount_paid": float(appt.amount_paid or 0),
        })

    return jsonify({
        "month": month_param,
        "first_day": first_day.isoformat(),
        "last_day": last_day.isoformat(),
        "days": days,
    })


@app.route("/api/calendar/day")
@owner_required
def calendar_day():
    business = get_owned_business()
    date_param = request.args.get("date", "").strip()
    staff_id = request.args.get("staff_id", type=int)

    try:
        chosen = datetime.strptime(date_param, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid date. Use YYYY-MM-DD."}), 400

    query = Appointment.query.filter_by(business_id=business.id, date=chosen)
    if staff_id:
        query = query.filter_by(staff_id=staff_id)

    appointments = query.order_by(Appointment.time).all()

    return jsonify({
        "date": chosen.isoformat(),
        "appointments": [{
            "id": a.id,
            "time": a.time,
            "reference": a.reference,
            "customer_name": a.customer_name,
            "customer_email": a.customer_email,
            "customer_phone": a.customer_phone,
            "service": a.service.name if a.service else "—",
            "duration": a.service.duration if a.service else 0,
            "staff_name": a.staff.name if a.staff else None,
            "notes": a.notes or "",
            "status": a.status,
            "payment_method": a.payment_method,
            "payment_status": a.payment_status,
            "amount_due": float(a.amount_due or 0),
            "amount_paid": float(a.amount_paid or 0),
        } for a in appointments],
    })


@app.route("/business/create", methods=["GET", "POST"])
@owner_required
def create_business():
    """Disabled in single-business mode."""
    flash("This is a single-business deployment. You cannot create additional businesses.", "info")
    return redirect(url_for("dashboard"))


@app.route("/business/services")
@owner_required
def services():
    business = get_owned_business()
    return render_template("business/services.html", business=business,
                           services=Service.query.filter_by(business_id=business.id).order_by(Service.name).all())


@app.route("/business/services/new", methods=["GET", "POST"])
@owner_required
def new_service():
    business = get_owned_business()
    if request.method == "POST":
        db.session.add(Service(
            business_id=business.id,
            name=request.form["name"].strip(),
            description=request.form.get("description", "").strip(),
            duration=request.form.get("duration", type=int) or 30,
            price=float(request.form.get("price") or 0),
            popular="popular" in request.form,
        ))
        db.session.commit()
        flash("Service created.", "success")
        return redirect(url_for("services", business_id=business.id))
    return render_template("business/service_form.html", business=business, service=None)


@app.route("/business/services/<int:service_id>/edit", methods=["GET", "POST"])
@owner_required
def edit_service(service_id):
    business = get_owned_business()
    service = Service.query.filter_by(id=service_id, business_id=business.id).first_or_404()
    if request.method == "POST":
        service.name = request.form["name"].strip()
        service.description = request.form.get("description", "").strip()
        service.duration = request.form.get("duration", type=int) or 30
        service.price = float(request.form.get("price") or 0)
        service.popular = "popular" in request.form
        service.active = "active" in request.form
        db.session.commit()
        flash("Service updated.", "success")
        return redirect(url_for("services", business_id=business.id))
    return render_template("business/service_form.html", business=business, service=service)


@app.route("/business/services/<int:service_id>/delete", methods=["POST"])
@owner_required
def delete_service(service_id):
    business = get_owned_business()
    service = Service.query.filter_by(id=service_id, business_id=business.id).first_or_404()
    if service.appointments:
        service.active = False
        flash("Service has bookings, so it was archived instead of deleted.", "info")
    else:
        db.session.delete(service)
        flash("Service deleted.", "success")
    db.session.commit()
    return redirect(url_for("services", business_id=business.id))


@app.route("/business/staff")
@owner_required
def staff():
    business = get_owned_business()
    return render_template("business/staff.html", business=business,
                           staff=Staff.query.filter_by(business_id=business.id).order_by(Staff.name).all())


@app.route("/business/staff/new", methods=["POST"])
@owner_required
def new_staff():
    business = get_owned_business()
    db.session.add(Staff(
        business_id=business.id,
        name=request.form["name"].strip(),
        role=request.form.get("role", "Team Member").strip(),
        email=request.form.get("email", "").strip(),
    ))
    db.session.commit()
    flash("Team member added.", "success")
    return redirect(url_for("staff", business_id=business.id))


@app.route("/business/appointments/<int:appointment_id>/status", methods=["POST"])
@owner_required
def appointment_status(appointment_id):
    business = get_owned_business()
    appointment = Appointment.query.filter_by(id=appointment_id, business_id=business.id).first_or_404()
    if request.form.get("status") in {"confirmed", "completed", "cancelled", "pending"}:
        appointment.status = request.form["status"]
        db.session.commit()
        flash("Appointment status updated.", "success")
    return redirect(url_for("dashboard", business_id=business.id))


@app.route("/business/settings", methods=["GET", "POST"])
@owner_required
def business_settings():
    business = get_owned_business()
    settings = business.settings or BusinessSetting(business_id=business.id)
    if request.method == "POST":
        for field in ["name", "category", "description", "email", "phone", "address", "city"]:
            setattr(business, field, request.form.get(field, "").strip())
        settings.open_time = request.form.get("open_time", "09:00")
        settings.close_time = request.form.get("close_time", "17:00")
        settings.slot_duration = request.form.get("slot_duration", type=int) or 30
        settings.cancellation_hours = request.form.get("cancellation_hours", type=int) or 24
        settings.cash_enabled = "cash_enabled" in request.form
        settings.yoco_enabled = "yoco_enabled" in request.form
        settings.yoco_public_key = request.form.get("yoco_public_key", "").strip()

        if "remove_yoco_secret" in request.form:
            settings.yoco_secret_key_encrypted = ""
        else:
            yoco_secret = request.form.get("yoco_secret_key", "").strip()
            if yoco_secret:
                settings.yoco_secret_key_encrypted = encrypt_secret(yoco_secret)

        db.session.add(settings)
        db.session.commit()
        flash("Business settings saved.", "success")
        return redirect(url_for("business_settings", business_id=business.id))

    return render_template("business/settings.html", business=business, settings=settings,
                           yoco_public_key_configured=bool(settings.yoco_public_key),
                           yoco_secret_configured=bool(settings.yoco_secret_key_encrypted))


@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin():
        abort(403)
    return render_template("admin/index.html",
                           businesses=Business.query.order_by(Business.created_at.desc()).all(),
                           users=User.query.count(),
                           appointments=Appointment.query.count())


@app.errorhandler(403)
def forbidden(_):
    return render_template("404.html", message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html", message="That page could not be found."), 404


with app.app_context():
    db.create_all()
    ensure_payment_columns()
    ensure_business_payment_columns()
    seed()


if __name__ == "__main__":
    app.run(debug=True)