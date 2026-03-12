"""
Initialize database for the Event Scheduler application
"""
from app import app, db

if __name__ == '__main__':
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ Database tables created successfully!")
        print("📍 Database location: events.db")
        print("\nNext steps:")
        print("1. Run the app: python app.py")
        print("2. Visit http://localhost:5000/seed to add sample data")
        print("3. Access the app at http://localhost:5000")
