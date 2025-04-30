from app import app, db
from models import User

def create_test_user():
    with app.app_context():
        # Check if user already exists
        if User.query.filter_by(username='admin').first():
            print('User already exists!')
            return

        # Create new user
        user = User(
            username='admin',
            full_name='Admin User',
            email='admin@example.com',
            role='admin'
        )
        user.set_password('admin123')
        
        # Add user to database
        db.session.add(user)
        db.session.commit()
        print('User created successfully!')

if __name__ == '__main__':
    create_test_user() 