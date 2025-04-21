from app import app, db
from models import User, Patient, HealthReading

with app.app_context():
    # Drop all tables
    db.drop_all()
    
    # Create all tables
    db.create_all()
    
    # Create a test user
    test_user = User(
        username='admin',
        email='admin@example.com',
        role='admin'
    )
    test_user.set_password('admin123')
    db.session.add(test_user)
    
    # Create a test patient
    test_patient = Patient(
        name='Test Patient',
        device_id='TEST001',
        id_number='12345678',
        date_of_birth='1990-01-01',
        gender='Male',
        phone='+254700000000',
        email='patient@example.com',
        address='123 Test Street',
        blood_type='O+',
        allergies='None',
        medical_conditions='None',
        emergency_contact='Emergency Contact',
        emergency_phone='+254711111111',
        relationship='Family'
    )
    db.session.add(test_patient)
    
    # Commit changes
    db.session.commit()
    
    print("Database initialized successfully!") 