from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from models import db, Patient, HealthReading, User
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

# ESP32 API Key configuration
ESP32_API_KEYS = {
    'device1': 'your-secure-api-key-1',
    'device2': 'your-secure-api-key-2'
}

# ESP32 connection state management
ESP32_CONNECTIONS = {}

def verify_esp32_api_key(api_key):
    return api_key in ESP32_API_KEYS.values()

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
        try:
            total_patients = Patient.query.count()
            total_readings = HealthReading.query.count()
            abnormal_readings = HealthReading.query.filter(HealthReading.status != 'normal').count()
            recent_activity = HealthReading.query.order_by(HealthReading.timestamp.desc()).limit(5).all()
            
            return render_template('index.html',
                                total_patients=total_patients,
                                total_readings=total_readings,
                                abnormal_readings=abnormal_readings,
                                recent_activity=recent_activity,
                                emergency_readings=[],  # Add empty list for emergency readings
                                today_appointments=[])  # Add empty list for appointments
        except Exception as e:
            flash('Error loading dashboard data', 'error')
            return render_template('index.html',
                                total_patients=0,
                                total_readings=0,
                                abnormal_readings=0,
                                recent_activity=[],
                                emergency_readings=[],
                                today_appointments=[])
    return render_template('public_home.html')

@app.route('/about')
def about():
    if current_user.is_authenticated:
        return render_template('about.html')
    return render_template('public_about.html')

@app.route('/public-about')
def public_about():
    return render_template('public_about.html')

@app.route('/register-user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        email = request.form.get('email')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register_user'))

        try:
            user = User(username=username, full_name=full_name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration', 'error')
            return redirect(url_for('register_user'))
    
    return render_template('register_user.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        device_id = request.form.get('device_id')

        if Patient.query.filter_by(device_id=device_id).first():
            flash('Device already registered', 'error')
            return redirect(url_for('register'))

        try:
            patient = Patient(name=name, device_id=device_id)
            db.session.add(patient)
            db.session.commit()
            flash('Patient registered successfully', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration', 'error')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/submit-reading', methods=['GET', 'POST'])
@login_required
def submit_reading():
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        systolic = float(request.form.get('systolic'))
        diastolic = float(request.form.get('diastolic'))

        patient = Patient.query.filter_by(device_id=device_id).first()
        if not patient:
            flash('Device not registered', 'error')
            return redirect(url_for('submit_reading'))

        try:
            status = evaluate_status(systolic, diastolic)
            reading = HealthReading(
                systolic=systolic,
                diastolic=diastolic,
                status=status,
                patient_id=patient.id
            )
            db.session.add(reading)
            db.session.commit()
            flash('Reading submitted successfully', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while submitting the reading', 'error')
            return redirect(url_for('submit_reading'))

    return render_template('submit_reading.html')

@app.route('/readings/<device_id>')
@login_required
def view_readings(device_id):
    patient = Patient.query.filter_by(device_id=device_id).first()
    if not patient:
        flash('Device not found', 'error')
        return redirect(url_for('index'))

    readings = HealthReading.query.filter_by(patient_id=patient.id).order_by(HealthReading.timestamp.desc()).all()
    return render_template('readings.html', patient=patient, readings=readings)

@app.route('/patients')
@login_required
def list_patients():
    patients = Patient.query.all()
    return render_template('list_patients.html', patients=patients)

@app.route('/readings')
@login_required
@cache.memoize(timeout=30)  # Cache for 30 seconds
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

@app.route('/patient/<int:patient_id>')
@login_required
def patient_profile(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    return render_template('patient_profile.html', patient=patient)

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    current_user.full_name = request.form.get('full_name')
    current_user.email = request.form.get('email')
    current_user.department = request.form.get('department')
    current_user.role = request.form.get('role')
    current_user.shift_start = request.form.get('shift_start')
    current_user.shift_end = request.form.get('shift_end')
    db.session.commit()
    flash('Profile updated successfully', 'success')
    return redirect(url_for('profile'))

@app.route('/profile/change-password', methods=['POST'])
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

    current_user.set_password(new_password)
    db.session.commit()
    flash('Password changed successfully', 'success')
    return redirect(url_for('profile'))

@app.route('/hospital_questions', methods=['GET', 'POST'])
@login_required
def hospital_questions():
    if request.method == 'POST':
        current_user.department = request.form.get('department')
        current_user.role = request.form.get('role')
        current_user.shift_start = request.form.get('shift_start')
        current_user.shift_end = request.form.get('shift_end')
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('hospital_questions.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = serializer.dumps(email, salt='password-reset')
            reset_url = url_for('reset_password', token=token, _external=True)
            msg = Message('Password Reset Request',
                         recipients=[email])
            msg.body = f'Click the following link to reset your password: {reset_url}'
            mail.send(msg)
            flash('Password reset link sent to your email', 'success')
        else:
            flash('Email not found', 'error')
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = serializer.loads(token, salt='password-reset', max_age=3600)
    except:
        flash('The password reset link is invalid or has expired', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(request.form.get('password'))
@login_required
def dashboard():
    try:
        total_patients = Patient.query.count()
        total_readings = HealthReading.query.count()
        emergency_count = HealthReading.query.filter(
            (HealthReading.systolic >= 140) | (HealthReading.diastolic >= 90)
        ).count()
        
        recent_activity = HealthReading.query.order_by(HealthReading.timestamp.desc()).limit(5).all()
        
        # Get ESP32 devices and their connection status
        esp32_devices = []
        for device_id in ESP32_API_KEYS.keys():
            device = {
                'device_id': device_id,
                'is_connected': False
            }
            if device_id in ESP32_CONNECTIONS:
                try:
                    device['is_connected'] = (datetime.utcnow() - ESP32_CONNECTIONS[device_id]).total_seconds() < 10
                except (TypeError, AttributeError):
                    device['is_connected'] = False
            esp32_devices.append(device)
        
        return render_template('dashboard.html',
                            total_patients=total_patients,
                            total_readings=total_readings,
                            emergency_count=emergency_count,
                            recent_activity=recent_activity,
                            esp32_devices=esp32_devices)
    except Exception as e:
        app.logger.error(f'Dashboard error: {str(e)}')
        flash('Error loading dashboard data', 'error')
        return render_template('dashboard.html',
                            total_patients=0,
                            total_readings=0,
                            emergency_count=0,
                            recent_activity=[],
                            esp32_devices=[])

@app.route('/register-patient', methods=['GET', 'POST'])
@login_required
@app.route('/new_patient', methods=['GET', 'POST'])
@login_required
def new_patient():
    if request.method == 'POST':
        name = request.form.get('name')
        device_id = request.form.get('device_id')
        id_number = request.form.get('id_number')
        date_of_birth = datetime.strptime(request.form.get('date_of_birth'), '%Y-%m-%d').date()
        gender = request.form.get('gender')
        phone = request.form.get('phone')
        email = request.form.get('email')
        address = request.form.get('address')
        blood_type = request.form.get('blood_type')
        allergies = request.form.get('allergies')
        medical_conditions = request.form.get('medical_conditions')
        emergency_contact = request.form.get('emergency_contact')
        emergency_phone = request.form.get('emergency_phone')
        relationship = request.form.get('relationship')

        # Check if device ID already exists
        existing_device = Patient.query.filter_by(device_id=device_id).first()
        if existing_device:
            flash('Device ID already registered', 'error')
            return redirect(url_for('new_patient'))

        # Check if ID number already exists
        existing_id = Patient.query.filter_by(id_number=id_number).first()
        if existing_id:
            flash('ID number already registered', 'error')
            return redirect(url_for('new_patient'))

        # Create new patient
        new_patient = Patient(
            name=name,
            device_id=device_id,
            id_number=id_number,
            date_of_birth=date_of_birth,
            gender=gender,
            phone=phone,
            email=email,
            address=address,
            blood_type=blood_type,
            allergies=allergies,
            medical_conditions=medical_conditions,
            emergency_contact=emergency_contact,
            emergency_phone=emergency_phone,
            relationship=relationship
        )

        try:
            db.session.add(new_patient)
            db.session.commit()
            flash('Patient registered successfully!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error registering patient. Please try again.', 'error')
            return redirect(url_for('new_patient'))

    return render_template('register.html')

@app.route('/api/register', methods=['POST'])
def api_register_patient():
    data = request.get_json()
    patient = Patient(name=data['name'], device_id=data['device_id'])
    db.session.add(patient)
    db.session.commit()
    return jsonify({'message': 'Patient registered successfully'})

@app.route('/api/readings/<device_id>', methods=['GET'])
def get_readings(device_id):
    patient = Patient.query.filter_by(device_id=device_id).first()
    if not patient:
        return jsonify({'error': 'Device not found'}), 404
    
    readings = HealthReading.query.filter_by(patient_id=patient.id).order_by(HealthReading.timestamp.desc()).all()
    return jsonify([{
        'systolic': r.systolic,
        'diastolic': r.diastolic,
        'status': r.status,
        'timestamp': r.timestamp.isoformat()
    } for r in readings])

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        
        msg = Message('New Contact Form Submission',
                     recipients=[app.config['MAIL_DEFAULT_SENDER']])
        msg.body = f'Name: {name}\nEmail: {email}\nMessage: {message}'
        mail.send(msg)
        
        flash('Your message has been sent successfully', 'success')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/professional_features')
@login_required
def professional_features():
    if current_user.role != 'doctor':
        flash('Only doctors can access professional features', 'error')
        return redirect(url_for('index'))
    return render_template('professional_features.html')

@app.route('/api/esp32/reading', methods=['POST'])
def esp32_reading():
    try:
        # Get API key from request headers
        api_key = request.headers.get('X-API-Key')
        if not api_key or not verify_esp32_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401

        # Get device ID and readings from request
        data = request.get_json()
        device_id = data.get('device_id')
        systolic = data.get('systolic')
        diastolic = data.get('diastolic')
        pulse = data.get('pulse')
        temperature = data.get('temperature')
        heart_rate = data.get('heart_rate')

        if not device_id:
            return jsonify({'error': 'Device ID is required'}), 400

        # Find or create patient
        patient = Patient.query.filter_by(device_id=device_id).first()
        if not patient:
            return jsonify({'error': 'Device not registered'}), 404

        # Create new reading
        reading = HealthReading(
            reading_type='bp',
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            temperature=temperature,
            heart_rate=heart_rate,
            status=evaluate_status(systolic, diastolic),
            patient_id=patient.id
        )
        
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
    try:
        # Get API key from request headers
        api_key = request.headers.get('X-API-Key')
        if not api_key or not verify_esp32_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401

        # Check if device is connected and connection hasn't timed out
        current_time = datetime.utcnow()
        if device_id in ESP32_CONNECTIONS:
            connection_time = ESP32_CONNECTIONS[device_id]
            if (current_time - connection_time).total_seconds() <= 10:
                return jsonify({
                    'status': 'connected',
                    'message': 'Device is connected'
                })
            else:
                # Connection has timed out
                ESP32_CONNECTIONS.pop(device_id, None)

        return jsonify({
            'status': 'disconnected',
            'message': 'Device is disconnected'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/workwi/status/<device_id>', methods=['GET'])
def workwi_get_status(device_id):
    api_key = request.headers.get('X-API-Key')
    if not api_key or not verify_esp32_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401

    patient = Patient.query.filter_by(device_id=device_id).first()
    if not patient:
        return jsonify({'error': 'Device not registered'}), 404

    # Get the latest reading
    latest_reading = HealthReading.query.filter_by(patient_id=patient.id)\
        .order_by(HealthReading.timestamp.desc()).first()

    if not latest_reading:
        return jsonify({'message': 'No readings available'}), 200

    return jsonify({
        'device_id': device_id,
        'last_reading': {
            'systolic': latest_reading.systolic,
            'diastolic': latest_reading.diastolic,
            'pulse': latest_reading.pulse,
            'status': latest_reading.status,
            'timestamp': latest_reading.timestamp.isoformat()
        }
    })

@app.route('/api/workwi/reading', methods=['POST'])
def workwi_submit_reading():
    # Get API key from request headers
    api_key = request.headers.get('X-API-Key')
    if not api_key or not verify_esp32_api_key(api_key):
        return jsonify({'error': 'Invalid API key'}), 401

    try:
        data = request.get_json()
        device_id = data.get('device_id')
        systolic = float(data.get('systolic'))
        diastolic = float(data.get('diastolic'))
        pulse = float(data.get('pulse', 0))  # Optional pulse reading

        # Validate required fields
        if not all([device_id, systolic, diastolic]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Check if device is registered
        patient = Patient.query.filter_by(device_id=device_id).first()
        if not patient:
            return jsonify({'error': 'Device not registered'}), 404

        # Evaluate blood pressure status
        status = evaluate_status(systolic, diastolic)

        # Create new reading
        reading = HealthReading(
            systolic=systolic,
            diastolic=diastolic,
            pulse=pulse,
            status=status,
            patient_id=patient.id
        )
        db.session.add(reading)
        db.session.commit()

        return jsonify({
            'message': 'Reading submitted successfully',
            'status': status,
            'reading_id': reading.id
        }), 201

    except ValueError:
        return jsonify({'error': 'Invalid data format'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/random-stats', methods=['GET'])
def random_stats():
    try:
        # Get current counts
        total_patients = Patient.query.count()
        total_readings = HealthReading.query.count()
        abnormal_readings = HealthReading.query.filter(HealthReading.status != 'normal').count()
        
        # Generate random readings for demonstration
        patients = Patient.query.all()
        if patients:
            # Select a random patient
            patient = random.choice(patients)
            
            # Generate random readings
            systolic = random.randint(90, 180)
            diastolic = random.randint(60, 120)
            pulse = random.randint(60, 100)
            temperature = round(random.uniform(36.0, 39.0), 1)
            heart_rate = random.randint(60, 120)
            
            # Create new readings
            bp_reading = HealthReading(
                patient_id=patient.id,
                reading_type='bp',
                systolic=systolic,
                diastolic=diastolic,
                pulse=pulse,
                status=evaluate_status(systolic, diastolic)
            )
            
            temp_reading = HealthReading(
                patient_id=patient.id,
                reading_type='temp',
                temperature=temperature,
                status=evaluate_status(temperature, temperature)
            )
            
            hr_reading = HealthReading(
                patient_id=patient.id,
                reading_type='hr',
                heart_rate=heart_rate,
                status=evaluate_status(heart_rate, heart_rate)
            )
            
            # Add readings to database
            db.session.add(bp_reading)
            db.session.add(temp_reading)
            db.session.add(hr_reading)
            db.session.commit()
            
            # Update counts
            total_readings += 3
            abnormal_readings = HealthReading.query.filter(HealthReading.status != 'normal').count()
        
        return jsonify({
            'total_patients': total_patients,
            'total_readings': total_readings,
            'abnormal_readings': abnormal_readings
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset-readings', methods=['POST'])
@login_required
def reset_readings():
    try:
        # Get current time
        current_time = datetime.utcnow()
        # Calculate time 24 hours ago
        cutoff_time = current_time - timedelta(hours=24)
        
        # Delete readings older than 24 hours
        deleted_count = HealthReading.query.filter(HealthReading.timestamp < cutoff_time).delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Successfully deleted {deleted_count} readings older than 24 hours'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error resetting readings: {str(e)}'
        }), 500

@app.route('/esp32-management')
@login_required
def esp32_management():
    return render_template('esp32_management.html')

@app.route('/api/esp32/connect', methods=['POST'])
def esp32_connect():
    try:
        # Get API key from request headers
        api_key = request.headers.get('X-API-Key')
        if not api_key or not verify_esp32_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401

        data = request.get_json()
        device_id = data.get('device_id')
        
        if not device_id:
            return jsonify({'error': 'Device ID is required'}), 400

        # Store connection time
        ESP32_CONNECTIONS[device_id] = datetime.utcnow()

        return jsonify({
            'message': 'ESP32 connected successfully',
            'device_id': device_id,
            'timeout': 10  # Indicate timeout in seconds
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/esp32/disconnect', methods=['POST'])
def esp32_disconnect():
    try:
        # Get API key from request headers
        api_key = request.headers.get('X-API-Key')
        if not api_key or not verify_esp32_api_key(api_key):
            return jsonify({'error': 'Invalid API key'}), 401

        data = request.get_json()
        device_id = data.get('device_id')
        
        if not device_id:
            return jsonify({'error': 'Device ID is required'}), 400

        # Remove connection state
        ESP32_CONNECTIONS.pop(device_id, None)

        return jsonify({
            'message': 'ESP32 disconnected successfully',
            'device_id': device_id
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        # Create upload folder if it doesn't exist
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        
        # Secure the filename and add timestamp to make it unique
        filename = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
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

@app.route('/new-appointment', methods=['GET', 'POST'])
@login_required
def new_appointment():
    if request.method == 'POST':
        try:
            # Get form data
            patient_name = request.form.get('patient_name')
            doctor_name = request.form.get('doctor_name')
            department = request.form.get('department')
            appointment_date = request.form.get('appointment_date')
            appointment_time = request.form.get('appointment_time')
            appointment_type = request.form.get('appointment_type')
            notes = request.form.get('notes')

            # Create appointment datetime
            appointment_datetime = datetime.strptime(f'{appointment_date} {appointment_time}', '%Y-%m-%d %H:%M')

            # Here you would typically save the appointment to your database
            # For now, we'll just show a success message
            flash('Appointment scheduled successfully!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            app.logger.error(f'Error creating appointment: {str(e)}')
            flash('Error scheduling appointment. Please try again.', 'error')

    return render_template('new_appointment.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
