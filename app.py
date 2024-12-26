from flask import Flask, render_template, request, redirect, flash, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from models import *
import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.sqlite3"
app.config["SECRET_KEY"] = "af9d4e10d142994285d0c1f861a70925"

db.init_app(app)

migrate = Migrate(app, db, render_as_batch=True)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return Member.query.get(int(user_id))


@app.before_request
def check_valid_login():
    if request.endpoint is None:
        return render_template("404.html"), 404
    login_valid = (
        current_user.is_authenticated
    )  # or whatever you use to check valid login

    if (
        request.endpoint
        and "static" not in request.endpoint
        and not login_valid
        and not getattr(app.view_functions[request.endpoint], "is_public", False)
    ):
        return redirect(url_for("login", next=request.path))

    if login_valid:
        if (
            getattr(app.view_functions[request.endpoint], "is_librarian", True)
            and current_user.role != "librarian"
            and "static" not in request.endpoint
        ):
            return redirect("/user")


def public_endpoint(f):
    f.is_public = True
    return f


def member_endpoint(f):
    f.is_librarian = False
    return f


@app.route("/register", methods=["GET", "POST"])
@public_endpoint
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        if not name or not email or not password:
            flash("Please fill in all fields")
            return redirect(request.url)

        user = Member.query.filter_by(email=email).first()

        if user:
            flash("Email address already exists")
            return redirect(request.url)

        new_user = Member(
            name=name, email=email, password=generate_password_hash(password)
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/")
def index():
    borrowed_books = (
        db.session.query(Transaction).filter(Transaction.return_date == None).count()
    )
    total_books = Book.query.count()
    total_members = Member.query.count()
    total_rent_current_month = calculate_total_rent_current_month()
    recent_transactions = (
        db.session.query(Transaction, Book)
        .join(Book)
        .order_by(Transaction.issue_date.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "index.html",
        borrowed_books=borrowed_books,
        total_books=total_books,
        total_members=total_members,
        recent_transactions=recent_transactions,
        total_rent_current_month=total_rent_current_month,
    )


def calculate_total_rent_current_month():
    current_month = datetime.datetime.now().month
    current_year = datetime.datetime.now().year
    start_date = datetime.datetime(current_year, current_month, 1)
    if current_month == 12:
        end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)

    total_rent = (
        db.session.query(db.func.sum(Transaction.rent_fee))
        .filter(
            Transaction.issue_date >= start_date, Transaction.issue_date <= end_date
        )
        .scalar()
    )

    return total_rent if total_rent else 0

def calculate_total_rent_member_current_month():
    current_month = datetime.datetime.now().month
    current_year = datetime.datetime.now().year
    start_date = datetime.datetime(current_year, current_month, 1)
    if current_month == 12:
        end_date = datetime.datetime(current_year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.datetime(current_year, current_month + 1, 1) - datetime.timedelta(days=1)

    total_rent = (
        db.session.query(db.func.sum(Transaction.rent_fee))
        .filter(
            Transaction.issue_date >= start_date,
            Transaction.issue_date <= end_date,
            Transaction.member_id == current_user.id,
        )
        .scalar()
    )

    return total_rent if total_rent else 0


@app.route("/login")
@public_endpoint
@member_endpoint
def login():
    # if current_user.is_authenticated:
    #     return redirect('/')
    return render_template("login.html")


@app.route("/login", methods=["POST"])
@public_endpoint
@member_endpoint
def login_post():
    # login code goes here
    email = request.form.get("email")
    password = request.form.get("password")

    user = Member.query.filter_by(email=email).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash("Please check your login details and try again.")
        return redirect(
            "/login"
        )  # if the user doesn't exist or password is wrong, reload the page

    # if the above check passes, then we know the user has the right credentials
    login_user(user)
    dest = request.args.get("next")
    if dest:
        try:
            return redirect(dest)
        except:
            pass
    if user.role == "librarian":
        return redirect("/")
    return redirect("/user")


@app.route("/logout", methods=["POST"])
@member_endpoint
def logout():
    logout_user()
    return redirect("/login")


@app.route("/profile", methods=["GET"])
@member_endpoint
def profile():
    return render_template("profile.html", user=current_user)


@app.route("/edit_profile", methods=["GET", "POST"])
@member_endpoint
def edit_profile():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        address = request.form.get("address")

        current_user.name = name
        current_user.email = email
        current_user.phone = phone
        current_user.address = address

        db.session.commit()

        flash("Profile updated successfully", "success")
        return redirect("/profile")

    return render_template("edit_profile.html", user=current_user)


@app.route("/user", methods=["GET", "POST"])
@member_endpoint
def user():
    borrowed_books = (
        db.session.query(Transaction)
        .filter(
            Transaction.return_date == None, current_user.id == Transaction.member_id
        )
        .count()
    )
    total_books = Book.query.count()
    total_members = Member.query.count()
    total_rent_current_month = calculate_total_rent_member_current_month()
    recent_transactions = (
        db.session.query(Transaction, Book)
        .join(Book)
        .filter(Transaction.member_id == current_user.id)
        .order_by(Transaction.issue_date.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "user.html",
        borrowed_books=borrowed_books,
        total_books=total_books,
        total_members=total_members,
        recent_transactions=recent_transactions,
        total_rent_current_month=total_rent_current_month,
    )


@app.route("/add_section", methods=["GET", "POST"])
def add_section():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        new_section = Sections(name=name, description=description)
        db.session.add(new_section)
        db.session.commit()
        flash("Section added successfully!", "success")
        return redirect(url_for("view_sections"))

    return render_template("add_section.html")


@app.route("/add_book", methods=["GET", "POST"])
def add_book():
    if request.method == "POST":
        title = request.form.get("title")
        author = request.form.get("author")
        isbn = request.form.get("isbn")
        publisher = request.form.get("publisher")
        page = request.form.get("page")
        sections = request.form.get("section").split(",")
        new_book = Book(
            title=title, author=author, isbn=isbn, publisher=publisher, page=page
        )
        for section in sections:
            section = section.strip()
            if section:
                section = Sections.query.filter_by(id=section).first()
                if section:
                    new_book.sections.append(section)
            else:
                flash("Section not found", "error")
                return redirect(url_for("add_book"))

        stock = request.form.get("stock")
        db.session.add(new_book)
        db.session.flush()
        new_stock = Stock(
            book_id=new_book.id, total_quantity=stock, available_quantity=stock
        )
        db.session.add(new_stock)
        db.session.commit()
        flash("Book added successfully!", "success")
        return redirect(url_for("index"))

    return render_template("add_book.html", sections=Sections.query.all())


@app.route("/add_member", methods=["GET", "POST"])
def add_member():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        address = request.form.get("address")

        new_member = Member(name=name, email=email, phone=phone, address=address)

        db.session.add(new_member)
        db.session.commit()

        flash("Member added successfully!", "success")
        return redirect(url_for("add_member"))
    return render_template("add_member.html")


@app.route("/view_books_member", methods=["GET", "POST"])
@member_endpoint
def book_list_member():
    title = request.args.get("searcht")
    author = request.args.get("searcha")
    section_id = request.args.get("searchs")
    if title and author:
        books = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter((Book.title.like(f"%{title}%")), (Book.author.like(f"%{author}%")))
            .all()
        )
    elif title:
        books = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter(Book.title.like(f"%{title}%"))
            .all()
        )
    elif author:
        books = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter(Book.author.like(f"%{author}%"))
            .all()
        )
    elif section_id:
        section = db.session.query(Sections).filter(Sections.id == section_id).first()
        books = (
            db.session.query(BookSection, Book, Stock)
            .filter(BookSection.section_id == section_id)
            .join(Book, BookSection.book_id == Book.id)
            .join(Stock, Stock.book_id == Book.id)
            .all()
        )
        books = [book[1:] for book in books]
    else:
        books = db.session.query(Book, Stock).join(Stock).all()

    return render_template("view_books_member.html", books=books)


@app.route("/view_sections", methods=["GET", "POST"])
def view_sections():
    sections = Sections.query.all()
    return render_template("view_sections.html", sections=sections)


# add a view sections for member endpoint
@app.route("/view_sections_member", methods=["GET", "POST"])
@member_endpoint
def view_sections_member():
    sections = Sections.query.all()
    return render_template("view_sections_member.html", sections=sections)


@app.route("/view_books", methods=["GET", "POST"])
def book_list():
    title = request.args.get("searcht")
    author = request.args.get("searcha")
    section_id = request.args.get("searchs")
    if title and author:
        books = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter((Book.title.like(f"%{title}%")), (Book.author.like(f"%{author}%")))
            .all()
        )
    elif title:
        books = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter(Book.title.like(f"%{title}%"))
            .all()
        )
    elif author:
        books = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter(Book.author.like(f"%{author}%"))
            .all()
        )
    elif section_id:
        section = db.session.query(Sections).filter(Sections.id == section_id).first()
        books = (
            db.session.query(BookSection, Book, Stock)
            .filter(BookSection.section_id == section_id)
            .join(Book, BookSection.book_id == Book.id)
            .join(Stock, Stock.book_id == Book.id)
            .all()
        )
        books = [book[1:] for book in books]
    else:
        books = db.session.query(Book, Stock).join(Stock).all()

    return render_template("view_books.html", books=books)


@app.route("/view_members", methods=["GET", "POST"])
def member_list():
    if request.method == "POST":
        search = request.form.get("search")
        member = db.session.query(Member).filter(Member.name.like(f"%{search}%")).all()
    else:
        member = db.session.query(Member).all()

    return render_template("view_members.html", member=member)


@app.route("/edit_section/<int:id>", methods=["GET", "POST"])
def edit_section(id):
    section = Sections.query.get(id)
    try:
        if request.method == "POST":
            section.name = request.form.get("name")
            section.description = request.form.get("description")
            db.session.commit()
            flash("Updated successfully", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"An error ocuured \n{e}", "error")
    return render_template("edit_section.html", section=section)


@app.route("/edit_book/<int:id>", methods=["GET", "POST"])
def edit_book(id):
    book = Book.query.get(id)
    stock = Stock.query.get(book.id)
    try:
        if request.method == "POST":
            book.title = request.form.get("title")
            book.author = request.form.get("author")
            book.isbn = request.form.get("isbn")
            book.publisher = request.form.get("publisher")
            book.page = request.form.get("page")
            stock.total_quantity = request.form.get("stock")
            section = request.form.get("section").split(",")
            book.sections = []
            for sec in section:
                sec = sec.strip()
                if sec:
                    sec = Sections.query.filter_by(id=sec).first()
                    if sec:
                        book.sections.append(sec)
                else:
                    flash("Section not found", "error")
                    return redirect(url_for("edit_book", id=id))

            db.session.commit()
            flash("Updated Successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error ocuured \n{e}", "error")
    return render_template(
        "edit_book.html", book=book, stock=stock, sections=Sections.query.all()
    )


@app.route("/edit_member/<int:id>", methods=["GET", "POST"])
def edit_member(id):
    try:
        member = Member.query.get(id)
        if member.role == "librarian":
            flash("You are not allowed to edit this user", "error")
            return redirect("/view_members")
        if request.method == "POST":
            member.name = request.form["name"]
            member.phone = request.form["phone"]
            member.email = request.form["email"]
            member.address = request.form["address"]
            member.role = request.form["role"]
            db.session.commit()
            flash("Updated Successfully", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error ocuured \n{e}", "error")
    return render_template("edit_member.html", member=member)


@app.route("/delete_section/<int:id>", methods=["GET", "POST"])
def delete_section(id):
    try:
        section = Sections.query.get(id)
        db.session.delete(section)
        db.session.commit()
        flash("Section removed successfully", "success")
    except Exception as e:
        flash(f"An error ocuured \n{e}", "error")
    return redirect("/view_sections")


@app.route("/delete_member/<int:id>", methods=["GET", "POST"])
def delete_member(id):
    try:
        member = Member.query.get(id)
        if member.role == "librarian":
            flash("You are not allowed to delete this user", "error")
            return redirect("/view_members")
        db.session.delete(member)
        db.session.commit()
        flash("Member removed successfully", "success")
    except Exception as e:
        flash(f"An error ocuured \n{e}", "error")
    return redirect("/view_members")


@app.route("/delete_book/<int:id>", methods=["GET", "POST"])
def delete_book(id):
    try:
        book = Book.query.get(id)
        stock = Stock.query.get(book.id)
        db.session.delete(book)
        db.session.delete(stock)
        db.session.commit()
        flash("Book removed successfully", "success")
    except Exception as e:
        flash(f"An error ocuured \n{e}", "error")
    return redirect("/view_members")


@app.route("/read_book/<int:id>", methods=["GET"])
@member_endpoint
def read_book(id):
    book = Book.query.get(id)
    return render_template("read_book.html", book=book)


@app.route("/view_member/<int:id>")
def view_member(id):
    member = Member.query.get(id)
    transaction = Transaction.query.filter_by(member_id=member.id).all()
    dbt = calculate_dbt(member)
    return render_template(
        "view_member.html", member=member, trans=transaction, debt=dbt
    )


def calculate_dbt(member):
    dbt = 0
    charge = 1  # db.session.query(Charges).first()
    transactions = (
        db.session.query(Transaction)
        .filter_by(member_id=member.id, return_date=None)
        .all()
    )

    for transaction in transactions:
        days_difference = (datetime.date.today() - transaction.issue_date.date()).days
        if days_difference > 0:
            dbt += days_difference * charge  # .rentfee
    return dbt


@app.route("/issuebook", methods=["GET", "POST"])
def issue_book():
    users = db.session.query(Member).all()
    books = db.session.query(Book).all()
    if request.method == "POST":
        memberid = request.form["mk"]
        title = request.form["bk"]

        book = (
            db.session.query(Book, Stock)
            .join(Stock)
            .filter(Book.title.like(f"%{title}%"))
            .first()
            or db.session.query(Book, Stock)
            .join(Stock)
            .filter(Book.id.like(title))
            .first()
        )
        mem = db.session.query(Member).get(memberid)
        dbt = calculate_dbt(mem)
        return render_template(
            "issuebook.html", book=book, member=mem, debt=dbt, users=users, books=books
        )
    return render_template("issuebook.html", users=users, books=books)


@app.route("/issuebookconfirm", methods=["GET", "POST"])
def issue_book_confirm():
    if request.method == "POST":
        memberid = request.form["memberid"]
        bookid = request.form["bookid"]

        stock = db.session.query(Stock).filter_by(book_id=bookid).first()
        if stock.available_quantity <= 0:
            flash("Book is not available for issuance.", "error")
            return redirect("/issuebook")

        new_transaction = Transaction(
            book_id=bookid, member_id=memberid, issue_date=datetime.date.today()
        )

        stock.available_quantity -= 1
        stock.borrowed_quantity += 1
        stock.total_borrowed += 1

        db.session.add(new_transaction)
        db.session.commit()

        flash("Transaction added successfully", "success")
        return redirect("/issuebook")

    return render_template("issuebook.html")


@app.route("/acceptrequest", methods=["POST"])
def accept_request():
    request_id = request.form["request_id"]
    req = Requests.query.get(request_id)
    stock = Stock.query.filter_by(book_id=req.book_id).first()
    if stock.available_quantity <= 0:
        flash("Book is not available for issuance.", "error")
        return redirect("/requests")
    new_transaction = Transaction(
        book_id=req.book_id,
        member_id=req.member_id,
        issue_date=datetime.date.today(),
    )
    stock.available_quantity -= 1
    stock.borrowed_quantity += 1
    stock.total_borrowed += 1
    req.request_status = "accepted"
    db.session.add(new_transaction)
    db.session.commit()
    flash("Transaction added successfully", "success")
    return redirect("/requests")


@app.route("/rejectrequest", methods=["POST"])
def reject_request():
    request_id = request.form["request_id"]
    req = Requests.query.get(request_id)
    req.request_status = "rejected"
    db.session.commit()
    flash("Request rejected successfully", "success")
    return redirect("/requests")


@app.route("/requests", methods=["GET", "POST"])
def view_requests():
    requests = (
        db.session.query(Requests, Member, Book, Stock)
        .join(Book, Requests.book_id == Book.id)
        .join(Member, Requests.member_id == Member.id)
        .join(Stock, Stock.book_id == Book.id)
        .filter(Requests.request_status == "pending")
    )

    if request.method == "POST":
        search = request.form["search"]

        requests_by_name = (
            requests.filter(Member.name.like(f"%{search}%"))
            .filter(Requests.request_status == "pending")
            .all()
        )

        request_by_id = (
            requests.filter(Requests.id == search)
            .filter(Requests.request_status == "pending")
            .all()
        )

        if requests_by_name:
            requests = requests_by_name
        elif request_by_id:
            requests = request_by_id
        else:
            requests = []

    requests = requests.all()
    return render_template("requests.html", requests=requests)


@app.route("/requestbook", methods=["GET", "POST"])
@member_endpoint
def request_book():
    if request.method == "POST":
        member_id = current_user.id
        active_requests = Requests.query.filter_by(
            member_id=member_id, request_status="pending"
        ).count()
        if active_requests >= 5:
            flash("You already have 5 active requests", "error")
            return redirect("/view_books_member")
        book_id = request.form["book_id"]
        new_request = Requests(
            member_id=member_id, book_id=book_id, request_date=datetime.date.today()
        )
        db.session.add(new_request)
        db.session.commit()
        flash("Request added successfully", "success")
        return redirect("/view_books_member")
    requests = (
        db.session.query(Requests, Book)
        .join(Book)
        .filter(Requests.member_id == current_user.id)
        .all()
    )
    return render_template("member_request.html", book_requests=requests)


@app.route("/view_books_member", methods=["GET"])
@member_endpoint
def view_books_member():
    books = db.session.query(Book, Stock).join(Stock).all()
    return render_template("view_books_member.html", books=books)


@app.route("/transactions", methods=["GET", "POST"])
def view_borrowings():
    transactions = (
        db.session.query(Transaction, Member, Book)
        .join(Book)
        .join(Member)
        .order_by(desc(Transaction.return_date.is_(None)))
        .all()
    )

    if request.method == "POST":
        search = request.form["search"]

        transactions_by_name = (
            db.session.query(Transaction, Member, Book)
            .join(Book)
            .join(Member)
            .filter(Member.name.like(f"%{search}%"))
            .order_by(desc(Transaction.return_date.is_(None)))
            .all()
        )

        transaction_by_id = (
            db.session.query(Transaction, Member, Book)
            .join(Book)
            .join(Member)
            .filter(Transaction.id == search)
            .order_by(desc(Transaction.return_date.is_(None)))
            .all()
        )

        if transactions_by_name:
            transactions = transactions_by_name
        elif transaction_by_id:
            transactions = transaction_by_id
        else:
            transactions = []

    return render_template("transactions.html", trans=transactions)


@app.route("/autorevokeaccess", methods=["POST"])
def auto_revoke_access():
    transaction_id = request.form["transaction_id"]
    transaction = Transaction.query.get(transaction_id)

    if is_seven_days_old(transaction):
        stock = Stock.query.filter_by(book_id=transaction.book_id).first()
        stock.available_quantity += 1
        stock.borrowed_quantity -= 1
        transaction.return_date = datetime.date.today()
        db.session.commit()
        flash("Access revoked successfully", "success")

    return redirect("/transactions")


def is_seven_days_old(transaction):
    seven_days_ago = datetime.date.today() - datetime.timedelta(days=7)
    return transaction.borrow_date <= seven_days_ago


@app.route("/revokeaccess", methods=["POST"])
def revoke_access():
    transaction_id = request.form["transaction_id"]
    transaction = Transaction.query.get(transaction_id)
    stock = Stock.query.filter_by(book_id=transaction.book_id).first()
    stock.available_quantity += 1
    stock.borrowed_quantity -= 1
    transaction.return_date = datetime.date.today()
    db.session.commit()
    flash("Access revoked successfully", "success")
    return redirect("/transactions")


@app.route("/returnbook", methods=["GET"])
@member_endpoint
def ret():
    transactions = (
        db.session.query(Transaction, Member, Book)
        .join(Book)
        .join(Member)
        .filter(
            Transaction.member_id == current_user.id, Transaction.return_date == None
        )
        .all()
    )
    return render_template(
        "return.html",
        trans=transactions,
    )


@app.route("/returnbook/<int:id>", methods=["GET"])
@member_endpoint
def return_book(id):
    transaction = (
        db.session.query(Transaction, Member, Book)
        .join(Book)
        .join(Member)
        .filter(
            Transaction.id == id,
            Transaction.return_date == None,
            Transaction.member_id == current_user.id,
        )
        .first()
    )
    if not transaction and not current_user.role == "librarian":
        flash("Invalid transaction ID", "error")
        return redirect("/returnbook")
    elif not transaction and current_user.role == "librarian":
        transaction = (
            db.session.query(Transaction, Member, Book)
            .join(Book)
            .join(Member)
            .filter(Transaction.id == id, Transaction.return_date == None)
            .first()
        )
    rent = calculate_rent(transaction)
    if request.method == "GET":
        return render_template("returnbook.html", trans=transaction, rent=rent)
    else:
        return redirect("/returnbook")


@app.route("/returnbookconfirm", methods=["POST"])
@member_endpoint
def return_book_confirm():
    if request.method == "POST":
        id = request.form["id"]
        trans, member = (
            db.session.query(Transaction, Member)
            .join(Member)
            .filter(Transaction.id == id)
            .first()
        )
        stock = Stock.query.filter_by(book_id=trans.book_id).first()
        charge = 1  # Charges.query.first()
        rent = (
            datetime.date.today() - trans.issue_date.date()
        ).days * charge  # .rentfee
        if stock:
            stock.available_quantity += 1
            stock.borrowed_quantity -= 1

            trans.return_date = datetime.date.today()
            trans.rent_fee = rent
            db.session.commit()
            flash(f"{member.name} Returned book successfully", "success")
        else:
            flash("Error updating stock information", "error")

    return redirect("transactions")


# view contents of a book
@app.route("/view_book/<int:id>", methods=["GET"])
def view_book(id):
    book = Book.query.get(id)
    stock = Stock.query.filter_by(book_id=id).first()
    transaction = Transaction.query.filter_by(book_id=id).all()
    return render_template(
        "view_book.html", book=book, stock=stock, transaction=transaction
    )


@app.route("/revokebook", methods=["GET"])
def revoke():
    transactions = (
        db.session.query(Transaction, Member, Book)
        .join(Book)
        .join(Member)
        .filter(Transaction.return_date == None)
        .all()
    )
    return render_template(
        "revoke.html",
        trans=transactions,
    )


@app.route("/revokebook/<int:id>", methods=["GET"])
def revoke_book(id):
    transaction = (
        db.session.query(Transaction, Member, Book)
        .join(Book)
        .join(Member)
        .filter(
            Transaction.id == id,
            Transaction.return_date == None,
        )
        .first()
    )
    if not transaction:
        flash("Invalid transaction ID", "error")
        return redirect("/revokebook")
    rent = calculate_rent(transaction)
    if request.method == "GET":
        return render_template("revokebook.html", trans=transaction, rent=rent)
    else:
        return redirect("/revokebook")


@app.route("/revokebookconfirm", methods=["POST"])
def revoke_book_confirm():
    if request.method == "POST":
        id = request.form["id"]
        trans, member = (
            db.session.query(Transaction, Member)
            .join(Member)
            .filter(Transaction.id == id)
            .first()
        )
        stock = Stock.query.filter_by(book_id=trans.book_id).first()
        charge = 1  # Charges.query.first()
        rent = (
            datetime.date.today() - trans.issue_date.date()
        ).days * charge  # .rentfee
        if stock:
            stock.available_quantity += 1
            stock.borrowed_quantity -= 1

            trans.return_date = datetime.date.today()
            trans.rent_fee = rent
            db.session.commit()
            flash(f"Revoked book successfully for {member.name}", "success")
        else:
            flash("Error updating stock information", "error")

    return redirect("transactions")


def calculate_rent(transaction):
    charge = 1  # Charges.query.first()
    rent = (
        datetime.date.today() - transaction.Transaction.issue_date.date()
    ).days * charge  # .rentfee
    return rent


API_BASE_URL = "https://frappe.io/api/method/frappe-library"


@app.route("/import_book", methods=["GET", "POST"])
def imp():
    if request.method == "POST":
        title = request.form.get("title", default="", type=str)
        num_books = request.form.get("num_books", default=20, type=int)
        num_pages = (num_books + 19) // 20
        all_books = []
        for page in range(1, num_pages + 1):
            url = f"{API_BASE_URL}?page={page}&title={title}"
            response = requests.get(url)
            data = response.json()
            all_books.extend(data.get("message", []))
        return render_template(
            "imp.html", data=all_books[:num_books], title=title, num_books=num_books
        )

    return render_template("imp.html", data=[], title="", num_books=20)


@app.route("/save_all_books", methods=["POST"])
def save_all_books():
    data = request.json

    for book_data in data:
        book_id = book_data["id"]
        existing_book = Book.query.get(book_id)

        if existing_book is None:
            book = Book(
                id=book_id,
                title=book_data["title"],
                author=book_data["authors"],
                isbn=book_data["isbn"],
                publisher=book_data["publisher"],
                page=book_data["numPages"],
            )
            st = book_data["stock"]

            try:
                db.session.add(book)
                stock = Stock(book_id=book_id, total_quantity=st, available_quantity=st)
                db.session.add(stock)
                db.session.commit()

                flash("Books added successfully", "success")
            except IntegrityError as e:
                db.session.rollback()
                flash(f"Error adding book with ID {book_id}: {str(e)}", "failure")
        else:
            flash(f"Book with ID {book_id} already exists, skipping.", "warning")

    return redirect("/import_book")


@app.route("/stockupdate/<int:id>", methods=["GET", "POST"])
def stock_update(id):
    stock, book = (
        db.session.query(Stock, Book).join(Book).filter(Stock.book_id == id).first()
    )
    if request.method == "POST":
        qty = int(request.form["qty"])
        if qty > stock.total_quantity:
            stock.available_quantity += qty
            stock.total_quantity += qty
        else:
            stock.available_quantity -= qty
            stock.total_quantity -= qty
        db.session.commit()
        flash("Stock Updated", "success")
    return render_template("stockupdate.html", stock=stock, book=book)


@app.route("/feedback/<int:book_id>", methods=["GET", "POST"])
@member_endpoint
def feedback(book_id):
    if request.method == "POST":
        rating = request.form.get("rating")
        review = request.form.get("review")

        # Save the feedback and rating to the database
        new_feedback = Reviews(
            member_id=current_user.id, book_id=book_id, rating=rating, review=review
        )
        db.session.add(new_feedback)
        db.session.commit()

        flash("Thank you for your feedback!", "success")
        return redirect("/returnbook")

    return render_template(
        "feedback.html", book_id=book_id, book=Book.query.get(book_id)
    )


@app.route("/view_feedback", methods=["GET"])
def view_feedback():
    reviews = db.session.query(Reviews, Member).join(Member).all()
    print(reviews)
    return render_template("view_feedback.html", reviews=reviews)


def start_auto_revoke():
    scheduler = BackgroundScheduler()
    scheduler.add_job(auto_revoke_access, "interval", days=1)
    scheduler.start()


if __name__ == "__main__":
    start_auto_revoke()
    app.run(debug=True, port=5000)
