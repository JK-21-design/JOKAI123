from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from models import db, Patient, HealthReading, User, Appointment, Prescription, MedicalRecord, Department, StaffSchedule, MedicalSupply, PatientVisit
from flask_cors import CORS
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_caching import Cache
from flask_compress import Compress
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from pytz import timezone
import random
from werkzeug.routing.exceptions import BuildError
from werkzeug.utils import secure_filename

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['DEBUG'] = os.environ.get('FLASK_ENV') != 'production'
CORS(app)
app.secret_key = os.environ.get('SECRET_KEY', 'secret-key')

# Add these configurations after the existing app configurations
UPLOAD_FOLDER = 'static/profile_pictures'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(BuildError)
def handle_build_error(error):
    app.logger.error(f'URL build error: {error}')
    return f'Error building URL: {error}', 500

# Email configuration
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

# Initialize Flask-Mail
mail = Mail(app)

# Initialize serializer for password reset tokens
serializer = URLSafeTimedSerializer(app.secret_key)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Cache
cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

# Initialize Compress
Compress(app)

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'iot_health.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Healthcare system configuration
HEALTHCARE_SETTINGS = {
    'max_patients_per_doctor': 50,
    'emergency_threshold': {
        'systolic': 180,
        'diastolic': 120,
        'heart_rate': 120,
        'temperature': 39.0
    },
    'notification_interval': 30  # minutes
}

# System-wide settings
SYSTEM_SETTINGS = {
    'maintenance_mode': False,
    'backup_frequency': 'daily',
    'data_retention_days': 365
}

# ESP32 API Key configuration
ESP32_API_KEYS = {
    'device1': 'esp32-secure-key-1',
    'device2': 'esp32-secure-key-2',
    'device3': 'esp32-secure-key-3'
}

# ESP32 connection state management
ESP32_CONNECTIONS = {}

def verify_esp32_api_key(api_key):
    return api_key in ESP32_API_KEYS.values()

def check_emergency_condition(reading):
    """Check if a health reading indicates an emergency condition"""
    if reading.reading_type == 'bp':
        return (reading.systolic >= HEALTHCARE_SETTINGS['emergency_threshold']['systolic'] or 
                reading.diastolic >= HEALTHCARE_SETTINGS['emergency_threshold']['diastolic'])
    elif reading.reading_type == 'hr':
        return reading.heart_rate >= HEALTHCARE_SETTINGS['emergency_threshold']['heart_rate']
    elif reading.reading_type == 'temp':
        return reading.temperature >= HEALTHCARE_SETTINGS['emergency_threshold']['temperature']
    return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Make current_user available to all templates
@app.context_processor
def inject_user():
    return dict(user=current_user)

def evaluate_status(systolic, diastolic):
    if systolic >= 140 or diastolic >= 90:
        return "hypertension"
    elif systolic >= 130 or diastolic >= 80:
        return "elevated"
    else:
        return "normal"

@app.route('/')
def index():
    if current_user.is_authenticated:
        total_patients = Patient.query.count()
        total_readings = HealthReading.query.count()
        abnormal_readings = HealthReading.query.filter(HealthReading.status != 'normal').count()
        recent_activity = HealthReading.query.order_by(HealthReading.timestamp.desc()).limit(5).all()
        
        # Get ESP32 devices data
        esp32_devices = [
            {
                'device_id': device_id,
                'is_connected': device_id in ESP32_CONNECTIONS
            }
            for device_id in ESP32_API_KEYS.keys()
        ]
        
        return render_template('index.html',
                             total_patients=total_patients,
                             total_readings=total_readings,
                             abnormal_readings=abnormal_readings,
                             recent_activity=recent_activity,
                             esp32_devices=esp32_devices)
    return redirect(url_for('login'))

@app.route('/about')
def about():
    if current_user.is_authenticated:
        return render_template('about.html')
    return render_template('public_about.html')

@app.route('/contact')
def contact():
    if current_user.is_authenticated:
        return render_template('contact.html')
    return render_template('public_contact.html')

@app.route('/submit-reading')
def submit_reading():
    if current_user.is_authenticated:
        return render_template('submit_reading.html')
    return redirect(url_for('login'))

@app.route('/professional-features')
def professional_features():
    if current_user.is_authenticated:
        return render_template('professional_features.html')
    return redirect(url_for('login'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@app.route('/patients')
@login_required
def list_patients():
    patients = Patient.query.all()
    return render_template('list_patients.html', patients=patients)

@app.route('/patient/new', methods=['GET', 'POST'])
@login_required
def new_patient():
    if request.method == 'POST':
        try:
            patient = Patient(
                name=request.form.get('name'),
                device_id=request.form.get('device_id'),
                id_number=request.form.get('id_number'),
                date_of_birth=datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d'),
                gender=request.form.get('gender'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                address=request.form.get('address'),
                blood_type=request.form.get('blood_type'),
                allergies=request.form.get('allergies'),
                medical_conditions=request.form.get('medical_conditions'),
                emergency_contact=request.form.get('emergency_contact'),
                emergency_phone=request.form.get('emergency_phone'),
                relationship=request.form.get('relationship')
            )
            db.session.add(patient)
            db.session.commit()
            flash('Patient added successfully', 'success')
            return redirect(url_for('list_patients'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding patient', 'error')
    
    return render_template('new_patient.html')

@app.route('/register-user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        email = request.form.get('email')

        if not username or not password or not full_name or not email:
            flash('All fields are required', 'error')
            return redirect(url_for('register_user'))

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register_user'))

        try:
            user = User(username=username, full_name=full_name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            # Log the user in immediately after registration
            login_user(user)
            flash('Registration successful! Welcome!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration', 'error')
            return redirect(url_for('register_user'))
    
    return render_template('register_user.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        app.logger.debug(f'Login attempt for username: {username}')
        
        if not username:
            app.logger.warning('Login attempt with missing username')
            flash('Please provide a username', 'error')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()
        if not user:
            flash('User not found. Please register first.', 'error')
            return redirect(url_for('register_user'))
        
        if not user.check_password(password):
            flash('Invalid password. Please try again.', 'error')
            return render_template('login.html')
        
        login_user(user, remember=remember)
        app.logger.info(f'Login successful for user: {username}')
        flash('Login successful!', 'success')
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/upload-profile-picture', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Add timestamp to filename to make it unique
        filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}_{filename}"
        
        # Create upload folder if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Update user's profile picture
        current_user.profile_picture = filename
        db.session.commit()
        
        flash('Profile picture updated successfully', 'success')
    else:
        flash('Invalid file type. Allowed types: png, jpg, jpeg, gif', 'error')
    
    return redirect(url_for('profile'))

@app.route('/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        current_user.full_name = request.form.get('full_name')
        current_user.email = request.form.get('email')
        current_user.department = request.form.get('department')
        current_user.license_number = request.form.get('license_number')
        current_user.specialization = request.form.get('specialization')
        current_user.years_experience = request.form.get('years_experience')
        current_user.shift_hours = request.form.get('shift_hours')
        current_user.working_days = request.form.get('working_days')
        
        db.session.commit()
        flash('Profile updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating profile', 'error')
    
    return redirect(url_for('profile'))

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_user.check_password(current_password):
        flash('Current password is incorrect', 'error')
        return redirect(url_for('profile'))
    
    if new_password != confirm_password:
        flash('New passwords do not match', 'error')
        return redirect(url_for('profile'))
    
    try:
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error changing password', 'error')
    
    return redirect(url_for('profile'))

@app.route('/patient/<int:patient_id>/readings')
@login_required
def patient_readings(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    readings = HealthReading.query.filter_by(patient_id=patient_id).order_by(HealthReading.timestamp.desc()).all()
    return render_template('patient_readings.html', patient=patient, readings=readings)

@app.route('/emergency-alerts')
@login_required
def emergency_alerts():
    # Get readings that exceed emergency thresholds
    emergency_readings = []
    for reading in HealthReading.query.all():
        if check_emergency_condition(reading):
            emergency_readings.append(reading)
    
    return render_template('emergency_alerts.html', emergency_readings=emergency_readings)

@app.route('/patient/<int:patient_id>/history')
@login_required
def patient_history(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    readings = HealthReading.query.filter_by(patient_id=patient_id).order_by(HealthReading.timestamp.desc()).all()
    
    # Calculate statistics
    stats = {
        'total_readings': len(readings),
        'abnormal_readings': sum(1 for r in readings if r.status != 'normal'),
        'latest_reading': readings[0] if readings else None,
        'average_heart_rate': sum(r.heart_rate for r in readings if r.heart_rate) / len([r for r in readings if r.heart_rate]) if readings else 0
    }
    
    return render_template('patient_history.html', patient=patient, readings=readings, stats=stats)

@app.route('/departments')
@login_required
def departments():
    departments = Department.query.all()
    return render_template('departments.html', departments=departments)

@app.route('/department/<int:dept_id>')
@login_required
def department_detail(dept_id):
    department = Department.query.get_or_404(dept_id)
    staff = User.query.filter_by(department_id=dept_id).all()
    return render_template('department_detail.html', department=department, staff=staff)

@app.route('/staff/schedule')
@login_required
def staff_schedule():
    schedules = StaffSchedule.query.filter_by(staff_id=current_user.id).all()
    return render_template('staff_schedule.html', schedules=schedules)

@app.route('/staff/schedule/new', methods=['GET', 'POST'])
@login_required
def new_staff_schedule():
    if request.method == 'POST':
        try:
            schedule = StaffSchedule(
                staff_id=current_user.id,
                day_of_week=int(request.form.get('day_of_week')),
                start_time=datetime.strptime(request.form.get('start_time'), '%H:%M').time(),
                end_time=datetime.strptime(request.form.get('end_time'), '%H:%M').time(),
                is_available=request.form.get('is_available') == 'true'
            )
            db.session.add(schedule)
            db.session.commit()
            flash('Schedule added successfully', 'success')
            return redirect(url_for('staff_schedule'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding schedule', 'error')
    
    return render_template('new_staff_schedule.html')

@app.route('/medical-supplies')
@login_required
def medical_supplies():
    supplies = MedicalSupply.query.all()
    low_stock = [supply for supply in supplies if supply.needs_restock()]
    return render_template('medical_supplies.html', supplies=supplies, low_stock=low_stock)

@app.route('/medical-supply/new', methods=['GET', 'POST'])
@login_required
def new_medical_supply():
    if request.method == 'POST':
        try:
            supply = MedicalSupply(
                name=request.form.get('name'),
                description=request.form.get('description'),
                quantity=int(request.form.get('quantity')),
                unit=request.form.get('unit'),
                minimum_quantity=int(request.form.get('minimum_quantity')),
                location=request.form.get('location'),
                expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d') if request.form.get('expiry_date') else None
            )
            db.session.add(supply)
            db.session.commit()
            flash('Medical supply added successfully', 'success')
            return redirect(url_for('medical_supplies'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding medical supply', 'error')
    
    return render_template('new_medical_supply.html')

@app.route('/patient/<int:patient_id>/visits')
@login_required
def patient_visits(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    visits = PatientVisit.query.filter_by(patient_id=patient_id).order_by(PatientVisit.visit_date.desc()).all()
    return render_template('patient_visits.html', patient=patient, visits=visits)

@app.route('/patient/<int:patient_id>/visit/new', methods=['GET', 'POST'])
@login_required
def new_patient_visit(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    if request.method == 'POST':
        try:
            visit = PatientVisit(
                patient_id=patient_id,
                doctor_id=current_user.id,
                visit_date=datetime.strptime(request.form.get('visit_date'), '%Y-%m-%dT%H:%M'),
                visit_type=request.form.get('visit_type'),
                symptoms=request.form.get('symptoms'),
                diagnosis=request.form.get('diagnosis'),
                treatment=request.form.get('treatment'),
                notes=request.form.get('notes')
            )
            db.session.add(visit)
            db.session.commit()
            flash('Patient visit recorded successfully', 'success')
            return redirect(url_for('patient_visits', patient_id=patient_id))
        except Exception as e:
            db.session.rollback()
            flash('Error recording patient visit', 'error')
    
    return render_template('new_patient_visit.html', patient=patient)

@app.route('/dashboard')
@login_required
def dashboard():
    # Get counts for statistics
    total_patients = Patient.query.count()
    total_readings = 0  # You'll implement this later
    emergency_count = 0  # You'll implement this later

    # Get today's appointments
    today = datetime.now().date()
    today_appointments = Appointment.query.filter(
        db.func.date(Appointment.appointment_date) == today
    ).order_by(Appointment.appointment_date).all()

    return render_template('dashboard.html',
                         total_patients=total_patients,
                         total_readings=total_readings,
                         emergency_count=emergency_count,
                         today_appointments=today_appointments)

@app.route('/appointments')
@login_required
def appointments():
    if current_user.role == 'doctor':
        appointments = Appointment.query.filter_by(doctor_id=current_user.id).order_by(Appointment.appointment_date).all()
    else:
        appointments = Appointment.query.order_by(Appointment.appointment_date).all()
    return render_template('appointments.html', appointments=appointments)

@app.route('/appointment/new', methods=['GET', 'POST'])
@login_required
def new_appointment():
    if request.method == 'POST':
        try:
            appointment = Appointment(
                patient_id=request.form.get('patient_id'),
                doctor_id=current_user.id,
                appointment_date=datetime.strptime(request.form.get('appointment_date'), '%Y-%m-%dT%H:%M'),
                notes=request.form.get('notes')
            )
            db.session.add(appointment)
            db.session.commit()
            flash('Appointment scheduled successfully', 'success')
            return redirect(url_for('appointments'))
        except Exception as e:
            db.session.rollback()
            flash('Error scheduling appointment', 'error')
    
    patients = Patient.query.all()
    return render_template('new_appointment.html', patients=patients)

@app.route('/prescriptions')
@login_required
def prescriptions():
    if current_user.role == 'doctor':
        prescriptions = Prescription.query.filter_by(doctor_id=current_user.id).order_by(Prescription.prescribed_date.desc()).all()
    else:
        prescriptions = Prescription.query.order_by(Prescription.prescribed_date.desc()).all()
    return render_template('prescriptions.html', prescriptions=prescriptions)

@app.route('/prescription/new', methods=['GET', 'POST'])
@login_required
def new_prescription():
    if request.method == 'POST':
        try:
            prescription = Prescription(
                patient_id=request.form.get('patient_id'),
                doctor_id=current_user.id,
                medication_name=request.form.get('medication_name'),
                dosage=request.form.get('dosage'),
                frequency=request.form.get('frequency'),
                duration=request.form.get('duration'),
                notes=request.form.get('notes'),
                expiry_date=datetime.strptime(request.form.get('expiry_date'), '%Y-%m-%d')
            )
            db.session.add(prescription)
            db.session.commit()
            flash('Prescription created successfully', 'success')
            return redirect(url_for('prescriptions'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating prescription', 'error')
    
    patients = Patient.query.all()
    return render_template('new_prescription.html', patients=patients)

@app.route('/medical-records')
@login_required
def medical_records():
    if current_user.role == 'doctor':
        records = MedicalRecord.query.filter_by(doctor_id=current_user.id).order_by(MedicalRecord.record_date.desc()).all()
    else:
        records = MedicalRecord.query.order_by(MedicalRecord.record_date.desc()).all()
    return render_template('medical_records.html', records=records)

@app.route('/medical-record/new', methods=['GET', 'POST'])
@login_required
def new_medical_record():
    if request.method == 'POST':
        try:
            record = MedicalRecord(
                patient_id=request.form.get('patient_id'),
                doctor_id=current_user.id,
                diagnosis=request.form.get('diagnosis'),
                treatment=request.form.get('treatment'),
                notes=request.form.get('notes'),
                follow_up_date=datetime.strptime(request.form.get('follow_up_date'), '%Y-%m-%d') if request.form.get('follow_up_date') else None
            )
            db.session.add(record)
            db.session.commit()
            flash('Medical record created successfully', 'success')
            return redirect(url_for('medical_records'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating medical record', 'error')
    
    patients = Patient.query.all()
    return render_template('new_medical_record.html', patients=patients)

@app.route('/patient/<int:patient_id>/summary')
@login_required
def patient_summary(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    
    # Get all relevant information
    readings = HealthReading.query.filter_by(patient_id=patient_id).order_by(HealthReading.timestamp.desc()).all()
    appointments = Appointment.query.filter_by(patient_id=patient_id).order_by(Appointment.appointment_date.desc()).all()
    prescriptions = Prescription.query.filter_by(patient_id=patient_id).order_by(Prescription.prescribed_date.desc()).all()
    medical_records = MedicalRecord.query.filter_by(patient_id=patient_id).order_by(MedicalRecord.record_date.desc()).all()
    
    return render_template('patient_summary.html',
                         patient=patient,
                         readings=readings,
                         appointments=appointments,
                         prescriptions=prescriptions,
                         medical_records=medical_records)

@app.route('/api/esp32/reading', methods=['POST'])
def esp32_reading():
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    
    if not api_key or not verify_esp32_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        device_id = data.get('device_id')
        reading_type = data.get('reading_type')
        timestamp = datetime.utcnow()
        
        if reading_type == 'bp':
            systolic = data.get('systolic')
            diastolic = data.get('diastolic')
            pulse = data.get('pulse')
            status = evaluate_status(systolic, diastolic)
            
            reading = HealthReading(
                reading_type='bp',
                systolic=systolic,
                diastolic=diastolic,
                pulse=pulse,
                status=status,
                timestamp=timestamp,
                patient_id=device_id
            )
        elif reading_type == 'temp':
            temperature = data.get('temperature')
            status = 'normal' if 36.1 <= temperature <= 37.2 else 'abnormal'
            
            reading = HealthReading(
                reading_type='temp',
                temperature=temperature,
                status=status,
                timestamp=timestamp,
                patient_id=device_id
            )
        elif reading_type == 'hr':
            heart_rate = data.get('heart_rate')
            status = 'normal' if 60 <= heart_rate <= 100 else 'abnormal'
            
            reading = HealthReading(
                reading_type='hr',
                heart_rate=heart_rate,
                status=status,
                timestamp=timestamp,
                patient_id=device_id
            )
        else:
            return jsonify({'error': 'Invalid reading type'}), 400
        
        db.session.add(reading)
        db.session.commit()
        
        return jsonify({
            'message': 'Reading recorded successfully',
            'reading_id': reading.id
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp32/status/<device_id>', methods=['GET'])
def esp32_get_status(device_id):
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    
    if not api_key or not verify_esp32_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401
    
    if device_id in ESP32_CONNECTIONS:
        connection_time = ESP32_CONNECTIONS[device_id]
        if datetime.utcnow() - connection_time > timedelta(minutes=5):
            # Remove stale connection
            ESP32_CONNECTIONS.pop(device_id, None)
            return jsonify({'status': 'disconnected'}), 200
        
        return jsonify({
            'status': 'connected',
            'connected_since': connection_time.isoformat()
        }), 200
    
    return jsonify({'status': 'disconnected'}), 200

@app.route('/api/esp32/connect', methods=['POST'])
def esp32_connect():
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    
    if not api_key or not verify_esp32_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data or 'device_id' not in data:
        return jsonify({'error': 'Device ID required'}), 400
    
    device_id = data['device_id']
    ESP32_CONNECTIONS[device_id] = datetime.utcnow()
    
    return jsonify({
        'message': 'ESP32 connected successfully',
        'device_id': device_id
    }), 200

@app.route('/api/esp32/disconnect', methods=['POST'])
def esp32_disconnect():
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    
    if not api_key or not verify_esp32_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    if not data or 'device_id' not in data:
        return jsonify({'error': 'Device ID required'}), 400
    
    device_id = data['device_id']
    ESP32_CONNECTIONS.pop(device_id, None)
    
    return jsonify({
        'message': 'ESP32 disconnected successfully',
        'device_id': device_id
    }), 200

@app.route('/esp32-management')
@login_required
def esp32_management():
    return render_template('esp32_management.html')

@app.route('/hospital_questions', methods=['GET', 'POST'])
@login_required
def hospital_questions():
    if request.method == 'POST':
        try:
            current_user.department = request.form.get('department')
            current_user.role = request.form.get('role')
            current_user.years_experience = request.form.get('years_experience')
            current_user.shift_hours = request.form.get('shift')
            current_user.notes = request.form.get('notes')
            
            db.session.commit()
            flash('Your preferences have been saved successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while saving your preferences.', 'error')
            return redirect(url_for('hospital_questions'))
    
    return render_template('hospital_questions.html')

def create_test_user():
    with app.app_context():
        # Check if test user exists
        test_user = User.query.filter_by(username='test').first()
        if not test_user:
            test_user = User(
                username='test',
                full_name='Test User',
                email='test@example.com',
                role='doctor'
            )
            test_user.set_password('password123')
            db.session.add(test_user)
            db.session.commit()
            print("Test user created successfully!")
        else:
            print("Test user already exists!")

@app.route('/view-all-readings')
@login_required
def view_all_readings():
    patients = Patient.query.all()
    all_data = []

    # Initialize counters for abnormal readings
    temp_high_count = 0
    temp_normal_count = 0
    temp_low_count = 0
    bp_high_count = 0
    bp_normal_count = 0
    bp_low_count = 0
    hr_high_count = 0
    hr_normal_count = 0
    hr_low_count = 0

    for patient in patients:
        readings = HealthReading.query.filter_by(patient_id=patient.id).order_by(HealthReading.timestamp.desc()).all()
        
        # Count abnormal readings for each patient
        for reading in readings:
            if reading.reading_type == 'temp':
                if reading.temperature > 38:
                    temp_high_count += 1
                elif reading.temperature < 36:
                    temp_low_count += 1
                else:
                    temp_normal_count += 1
            elif reading.reading_type == 'bp':
                if reading.systolic >= 140 or reading.diastolic >= 90:
                    bp_high_count += 1
                elif reading.systolic < 90 or reading.diastolic < 60:
                    bp_low_count += 1
                else:
                    bp_normal_count += 1
            elif reading.reading_type == 'hr':
                if reading.heart_rate > 100:
                    hr_high_count += 1
                elif reading.heart_rate < 60:
                    hr_low_count += 1
                else:
                    hr_normal_count += 1

        all_data.append({
            'patient': patient,
            'readings': readings
        })

    return render_template('all_readings.html', 
                         data=all_data,
                         temp_high_count=temp_high_count,
                         temp_normal_count=temp_normal_count,
                         temp_low_count=temp_low_count,
                         bp_high_count=bp_high_count,
                         bp_normal_count=bp_normal_count,
                         bp_low_count=bp_low_count,
                         hr_high_count=hr_high_count,
                         hr_normal_count=hr_normal_count,
                         hr_low_count=hr_low_count)

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a unique token
            token = serializer.dumps(user.email, salt='password-reset-salt')
            
            # Create the reset password link
            reset_url = url_for('reset_password', token=token, _external=True)
            
            # Create and send the email
            msg = Message('Password Reset Request',
                        recipients=[user.email])
            msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email.
'''
            mail.send(msg)
            
            flash('Password reset instructions sent to your email.', 'info')
            return redirect(url_for('login'))
        
        flash('Email address not found.', 'error')
        return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)  # Token expires in 1 hour
    except:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user = User.query.filter_by(email=email).first()
        if user:
            new_password = request.form.get('password')
            user.set_password(new_password)
            db.session.commit()
            flash('Your password has been updated!', 'success')
            return redirect(url_for('login'))
    
    return render_template('reset_password.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_test_user()  # Create test user if it doesn't exist
    app.run(debug=True, host='0.0.0.0', port=5000)