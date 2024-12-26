from werkzeug.security import generate_password_hash
from app import app, db
from models import Member

def create_librarian():
    with app.app_context():
        name = input("Enter librarian name: ")
        email = input("Enter librarian email: ")
        password = input("Enter librarian password: ")

        if not name or not email or not password:
            print("All fields are required.")
            return

        existing_user = Member.query.filter_by(email=email).first()
        if existing_user:
            print("Email address already exists.")
            return

        librarian = Member(
            name=name,
            email=email,
            password=generate_password_hash(password),
            role="librarian"
        )

        db.session.add(librarian)
        db.session.commit()
        print("Librarian user created successfully.")

if __name__ == "__main__":
    create_librarian()
