# Library Management System

This project is a comprehensive Library Management System built with Python and Flask. It provides a user-friendly interface for managing books, borrowers, and borrowing transactions efficiently.

## Features

- Add, update, and delete books
- Register and manage borrowers
- Record and track borrowing transactions
- Search for books and borrowers

## Installation

To install the Library Management System, follow these steps:

1. **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2. **Install the required dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Database Setup

To set up the database, follow these steps:

1. **Initialize the database**:
    ```bash
    flask db init
    ```

2. **Apply the database migrations**:
    ```bash
    flask db upgrade
    ```

3. **Create the database tables**:
    ```bash
    flask shell
    ```

    ```python
    from app import db
    db.create_all()
    exit()
    ```

4. **Create an initial librarian user**:
    ```bash
    python create_librarian.py
    ```

## Usage

To start the application, run the following command in your terminal:

```bash
python3 app.py
```

or

```bash
flask --app app run
```