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
    department_id = db.Column(db.Integer, db.ForeignKey('department.id', name='fk_user_department'), nullable=True)
    role = db.Column(db.String(100))
    profile_picture = db.Column(db.String(200))  # Store the filename of the profile picture
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sign_in = db.Column(db.DateTime)
    sign_in_time = db.Column(db.DateTime)
    sign_out_time = db.Column(db.DateTime)
    patients_seen = db.Column(db.Integer, default=0)
    phone = db.Column(db.String(20))

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

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = db.relationship('Patient', backref='appointments')
    doctor = db.relationship('User', backref='appointments')

class Prescription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    medication_name = db.Column(db.String(200), nullable=False)
    dosage = db.Column(db.String(100), nullable=False)
    frequency = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.Text)
    prescribed_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled
    
    patient = db.relationship('Patient', backref='prescriptions')
    doctor = db.relationship('User', backref='prescriptions')

class MedicalRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    diagnosis = db.Column(db.Text, nullable=False)
    treatment = db.Column(db.Text)
    notes = db.Column(db.Text)
    record_date = db.Column(db.DateTime, default=datetime.utcnow)
    follow_up_date = db.Column(db.DateTime)
    
    patient = db.relationship('Patient', backref='medical_records')
    doctor = db.relationship('User', backref='medical_records')

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    head_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_department_head'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    head = db.relationship('User', backref='headed_department', foreign_keys=[head_id])
    staff = db.relationship('User', backref='department', foreign_keys='User.department_id')

class StaffSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0-6 for Monday-Sunday
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    
    staff = db.relationship('User', backref='schedules')

class MedicalSupply(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=0)
    unit = db.Column(db.String(50))
    minimum_quantity = db.Column(db.Integer, default=0)
    location = db.Column(db.String(100))
    last_restocked = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime)
    
    def needs_restock(self):
        return self.quantity <= self.minimum_quantity

class PatientVisit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    visit_date = db.Column(db.DateTime, nullable=False)
    visit_type = db.Column(db.String(50))  # Regular, Emergency, Follow-up
    symptoms = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    treatment = db.Column(db.Text)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='completed')  # scheduled, completed, cancelled
    
    patient = db.relationship('Patient', backref='visits')
    doctor = db.relationship('User', backref='patient_visits')
