from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from models import db, Patient, HealthReading, User
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)
app.secret_key = 'secret-key'  # Change this in production

# Database configuration
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'iot_health.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Helper to determine blood pressure status
def evaluate_status(systolic, diastolic):
    if systolic >= 140 or diastolic >= 90:
        return "hypertension"
    elif systolic >= 130 or diastolic >= 80:
        return "elevated"
    else:
        return "normal"

@app.route('/')
def index():
    return render_template('index.html', hospital_name="JOKAI Hospital")

@app.route('/register-user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            return "User already exists", 400

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register_user.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('index'))
        return "Invalid credentials", 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        device_id = request.form.get('device_id')

        if Patient.query.filter_by(device_id=device_id).first():
            return "Device already registered", 400

        patient = Patient(name=name, device_id=device_id)
        db.session.add(patient)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/submit-reading', methods=['GET', 'POST'])
def submit_reading():
    if request.method == 'POST':
        device_id = request.form.get('device_id')
        systolic = float(request.form.get('systolic'))
        diastolic = float(request.form.get('diastolic'))

        patient = Patient.query.filter_by(device_id=device_id).first()
        if not patient:
            return "Device not registered", 404

        status = evaluate_status(systolic, diastolic)
        reading = HealthReading(
            systolic=systolic,
            diastolic=diastolic,
            status=status,
            patient_id=patient.id
        )
        db.session.add(reading)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('submit_reading.html')

@app.route('/readings/<device_id>')
def view_readings(device_id):
    patient = Patient.query.filter_by(device_id=device_id).first()
    if not patient:
        return "Device not found", 404

    readings = HealthReading.query.filter_by(patient_id=patient.id).order_by(HealthReading.timestamp.desc()).all()
    return render_template('readings.html', patient=patient, readings=readings)

@app.route('/patients')
def list_patients():
    patients = Patient.query.all()
    return jsonify([{ 'name': p.name, 'device_id': p.device_id } for p in patients])

@app.route('/readings')
def view_all_readings():
    patients = Patient.query.all()
    all_data = []

    for patient in patients:
        readings = HealthReading.query.filter_by(patient_id=patient.id).order_by(HealthReading.timestamp.desc()).all()
        all_data.append({
            'patient': patient,
            'readings': readings
        })

    return render_template('all_readings.html', data=all_data)




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
