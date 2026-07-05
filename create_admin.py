import hashlib
from datetime import datetime
from models import User, get_db

def hash_password(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def create_users():
    admin_email = "admin@skillecho.com"
    student_email = "student@skillecho.com"
    
    with get_db() as db:
        # Create admin user if not exists
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                name="Admin User",
                email=admin_email,
                role="admin",
                password_hash=hash_password("admin123"),
                created_at=datetime.utcnow()
            )
            db.add(admin)
            print(f"✓ Queued admin user creation: {admin_email} (password: admin123)")
        else:
            print(f"ℹ Admin user already exists: {admin_email}")

        # Create student user if not exists
        student = db.query(User).filter(User.email == student_email).first()
        if not student:
            student = User(
                name="Student User",
                email=student_email,
                role="student",
                password_hash=hash_password("student123"),
                created_at=datetime.utcnow()
            )
            db.add(student)
            print(f"✓ Queued student user creation: {student_email} (password: student123)")
        else:
            print(f"ℹ Student user already exists: {student_email}")
            
        db.commit()
        print("✓ Database changes successfully committed to Cloud PostgreSQL!")

        # Query all users to print them
        users = db.query(User).all()
        print("\n--- Current Users in Database ---")
        for u in users:
            print(f"ID: {u.user_id} | Name: {u.name} | Email: {u.email} | Role: {u.role}")

if __name__ == "__main__":
    create_users()
