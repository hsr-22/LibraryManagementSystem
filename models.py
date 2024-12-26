from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200))
    isbn = db.Column(db.String(20))
    publisher = db.Column(db.String(100))
    page = db.Column(db.Integer, default=0)
    requests = db.relationship(
        "Requests", back_populates="book", cascade="all, delete-orphan"
    )
    stocks = db.relationship(
        "Stock", back_populates="book", cascade="all, delete-orphan"
    )
    sections = db.relationship(
        "Sections",
        secondary="book_section",
        backref=db.backref("books", lazy="dynamic"),
        lazy="dynamic",
    )


class Member(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True)
    phone = db.Column(db.String(15))
    address = db.Column(db.String(200))
    password = db.Column(db.String(100), default=generate_password_hash("password"))
    requests = db.relationship(
        "Requests", back_populates="member", cascade="all, delete-orphan"
    )
    role = db.Column(db.String(10), default="member")


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    issue_date = db.Column(db.DateTime, nullable=False)
    return_date = db.Column(db.DateTime)
    rent_fee = db.Column(db.Float, default=0.0)


class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    total_quantity = db.Column(db.Integer, default=0)
    available_quantity = db.Column(db.Integer, default=0)
    borrowed_quantity = db.Column(db.Integer, default=0)
    total_borrowed = db.Column(db.Integer, default=0)

    book = db.relationship("Book", back_populates="stocks")


class Requests(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    request_date = db.Column(db.DateTime, nullable=False)
    request_status = db.Column(db.String(10), default="pending")

    book = db.relationship("Book", back_populates="requests")
    member = db.relationship("Member", back_populates="requests")


class Sections(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True, default="General")
    description = db.Column(db.String(200))


class BookSection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"), nullable=False)

    book = db.relationship("Book", backref="book_sections")
    section = db.relationship("Sections", backref="book_sections")


class Reviews(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("book.id"), nullable=False)
    review = db.Column(db.String(200), nullable=True)
    rating = db.Column(db.Integer, default=0)

    book = db.relationship("Book", backref="reviews")
    member = db.relationship("Member", backref="reviews")
