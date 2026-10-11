from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(160), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), default="customer", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    businesses = db.relationship("Business", back_populates="owner", cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", back_populates="customer")
    def is_business_owner(self):
        return self.role in ("business_owner", "platform_admin")
    def is_admin(self):
        return self.role == "platform_admin"
    
class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    category = db.Column(db.String(80), default="Services")
    description = db.Column(db.Text, default="")
    logo_url = db.Column(db.String(500), default="")
    cover_url = db.Column(db.String(500), default="")
    email = db.Column(db.String(160), default="")
    phone = db.Column(db.String(80), default="")
    address = db.Column(db.String(250), default="")
    city = db.Column(db.String(100), default="")
    country = db.Column(db.String(100), default="South Africa")
    status = db.Column(db.String(30), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner = db.relationship("User", back_populates="businesses")
    services = db.relationship("Service", back_populates="business", cascade="all, delete-orphan")
    staff = db.relationship("Staff", back_populates="business", cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", back_populates="business", cascade="all, delete-orphan")
    settings = db.relationship("BusinessSetting", back_populates="business", uselist=False, cascade="all, delete-orphan")

class BusinessSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), unique=True, nullable=False)
    slot_duration = db.Column(db.Integer, default=30)
    open_time = db.Column(db.String(5), default="09:00")
    close_time = db.Column(db.String(5), default="17:00")
    working_days = db.Column(db.String(30), default="0,1,2,3,4")
    cancellation_hours = db.Column(db.Integer, default=24)
    # Payment configuration is stored per business. Secrets are encrypted at rest.
    cash_enabled = db.Column(db.Boolean, default=True, nullable=False)
    yoco_enabled = db.Column(db.Boolean, default=False, nullable=False)
    yoco_public_key = db.Column(db.String(255), default="")
    yoco_secret_key_encrypted = db.Column(db.Text, default="")
    yoco_webhook_secret_encrypted = db.Column(db.Text, default="")
    business = db.relationship("Business", back_populates="settings")

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    duration = db.Column(db.Integer, default=30)
    price = db.Column(db.Float, default=0)
    active = db.Column(db.Boolean, default=True)
    popular = db.Column(db.Boolean, default=False)
    business = db.relationship("Business", back_populates="services")
    appointments = db.relationship("Appointment", back_populates="service")

class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(120), default="Team Member")
    email = db.Column(db.String(160), default="")
    active = db.Column(db.Boolean, default=True)
    business = db.relationship("Business", back_populates="staff")
    appointments = db.relationship("Appointment", back_populates="staff")

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(30), unique=True, nullable=False, index=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    service_id = db.Column(db.Integer, db.ForeignKey("service.id"), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    customer_name = db.Column(db.String(120), nullable=False)
    customer_email = db.Column(db.String(160), nullable=False)
    customer_phone = db.Column(db.String(60), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(30), default="confirmed")
    notes = db.Column(db.Text, default="")
    # Payment tracking
    payment_method = db.Column(db.String(30), default="cash", nullable=False)
    payment_status = db.Column(db.String(30), default="unpaid", nullable=False)
    amount_due = db.Column(db.Float, default=0)
    amount_paid = db.Column(db.Float, default=0)
    payment_reference = db.Column(db.String(120), default="")
    yoco_checkout_id = db.Column(db.String(120), default="", index=True)
    payment_email_sent = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    business = db.relationship("Business", back_populates="appointments")
    service = db.relationship("Service", back_populates="appointments")
    staff = db.relationship("Staff", back_populates="appointments")
    customer = db.relationship("User", back_populates="appointments")
