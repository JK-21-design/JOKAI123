from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(200))
    email = db.Column(db.String(200))
    department = db.Column(db.String(100))
    role = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sign_in = db.Column(db.DateTime)
    sign_in_time = db.Column(db.DateTime)
    sign_out_time = db.Column(db.DateTime)
    patients_seen = db.Column(db.Integer, default=0)
    shift_start = db.Column(db.String(50))
    shift_end = db.Column(db.String(50))
    remember_me = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def sign_in(self):
        self.last_sign_in = datetime.utcnow()
        self.sign_in_time = datetime.utcnow()
        self.sign_out_time = None
        self.patients_seen = 0

    def sign_out(self):
        self.sign_out_time = datetime.utcnow()

    def increment_patients_seen(self):
        self.patients_seen += 1

class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    id_number = db.Column(db.String(50), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    address = db.Column(db.Text, nullable=False)
    blood_type = db.Column(db.String(5), nullable=False)
    allergies = db.Column(db.Text)
    medical_conditions = db.Column(db.Text)
    emergency_contact = db.Column(db.String(100), nullable=False)
    emergency_phone = db.Column(db.String(20), nullable=False)
    relationship = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    readings = db.relationship('HealthReading', backref='patient', lazy=True)

class HealthReading(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reading_type = db.Column(db.String(20), nullable=False)  # 'bp', 'temp', 'hr'
    systolic = db.Column(db.Float)  # Optional for blood pressure
    diastolic = db.Column(db.Float)  # Optional for blood pressure
    pulse = db.Column(db.Float)  # Optional for blood pressure
    temperature = db.Column(db.Float)  # Optional for temperature
    heart_rate = db.Column(db.Float)  # Optional for heart rate
    status = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
