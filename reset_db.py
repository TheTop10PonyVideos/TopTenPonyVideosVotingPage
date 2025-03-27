from app import app, db
import models  
print("Dropping all tables...")
with app.app_context():
    db.drop_all()
    print("All tables dropped successfully!")
    print("Creating all tables...")
    db.create_all()
    print("All tables created successfully!")
    print("Database reset complete!")