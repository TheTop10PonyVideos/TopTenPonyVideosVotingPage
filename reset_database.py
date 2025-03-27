
from app import app, db
import os

def reset_database():
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        
        print("Creating tables from scratch...")
        db.create_all()
        
        print("Database has been reset successfully!")

if __name__ == "__main__":
    reset_database()