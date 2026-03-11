import os
from pathlib import Path
from typing import Optional
from functools import wraps
from datetime import date, datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_from_directory,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import Application, CompanyProfile, Job, Placement, StudentProfile, User, db


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "placement_portal.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads" / "resumes"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-this-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB max upload

    db.init_app(app)

    # Ensure upload directory exists
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        db.create_all()
        seed_default_admin()

    @app.context_processor
    def inject_current_user():
        return {"current_user": get_current_user()}

    register_routes(app)
    return app


def seed_default_admin() -> None:
    if User.query.filter_by(role="admin").first() is None:
        admin = User(
            email="admin@example.com",
            password_hash=generate_password_hash("admin123"),
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()


def get_current_user() -> Optional[User]:
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not user or user.role not in roles:
                abort(403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return render_template("index.html")

    # Authentication
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password_hash, password):
                flash("Invalid email or password.", "danger")
                return redirect(url_for("index"))

            if user.role == "company":
                company = user.company_profile
                if not company or not company.approved or getattr(company, "blacklisted", False):
                    flash("Your company account is not approved for login. Please contact the placement cell.", "danger")
                    return render_template("auth/login.html", email=email)

            if user.role == "student":
                student = user.student_profile
                if student and getattr(student, "blacklisted", False):
                    flash("Your student account has been restricted. Please contact the placement cell.", "danger")
                    return render_template("auth/login.html", email=email)

            session["user_id"] = user.id
            session["role"] = user.role

            if user.role == "admin":
                return redirect(url_for("admin_dashboard"))
            if user.role == "company":
                return redirect(url_for("company_dashboard"))
            if user.role == "student":
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("index"))

        # For GET requests, always show the main index login page
        return redirect(url_for("index"))

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # Registration
    @app.route("/register/student", methods=["GET", "POST"])
    def register_student():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            name = request.form.get("name", "").strip()
            roll_number = request.form.get("roll_number", "").strip().upper()
            department = request.form.get("department", "").strip()
            cgpa = request.form.get("cgpa", "").strip()
            graduation_year = request.form.get("graduation_year", "").strip()
            phone = request.form.get("phone", "").strip()
            skills = request.form.get("skills", "").strip()

            if not email or not password:
                flash("Email and password are required.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            if not name or not roll_number or not department or not cgpa or not graduation_year:
                flash("Please fill in all required fields.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            if User.query.filter_by(email=email).first():
                flash("Email is already registered.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            try:
                cgpa_val = float(cgpa)
                grad_year_val = int(graduation_year)
            except ValueError:
                flash("Please enter valid numeric values for CGPA and graduation year.", "danger")
                return render_template("auth/register_student.html", form=request.form)

            # Handle resume upload
            resume_filename = None
            resume_file = request.files.get("resume")
            if resume_file and resume_file.filename and allowed_file(resume_file.filename):
                safe_name = secure_filename(resume_file.filename)
                # Prefix with roll number for uniqueness
                resume_filename = f"{roll_number}_{safe_name}"
                resume_file.save(str(UPLOAD_FOLDER / resume_filename))

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="student",
            )
            db.session.add(user)
            db.session.flush()

            profile = StudentProfile(
                user_id=user.id,
                name=name,
                roll_number=roll_number,
                department=department,
                cgpa=cgpa_val,
                graduation_year=grad_year_val,
                phone=phone or None,
                skills=skills or None,
                resume_filename=resume_filename,
            )
            db.session.add(profile)
            db.session.commit()

            flash("Student registered successfully. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("auth/register_student.html", form=request.form)

    @app.route("/register/company", methods=["GET", "POST"])
    def register_company():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            name = request.form.get("name", "").strip()
            website = request.form.get("website", "").strip()
            contact_person = request.form.get("contact_person", "").strip()
            contact_email = request.form.get("contact_email", "").strip()
            industry = request.form.get("industry", "").strip()

            if not email or not password:
                flash("Email and password are required.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            if not name:
                flash("Company name is required.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            if User.query.filter_by(email=email).first():
                flash("Email is already registered.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            if CompanyProfile.query.filter_by(name=name).first():
                flash("Company name is already registered.", "danger")
                return render_template("auth/register_company.html", form=request.form)

            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                role="company",
            )
            db.session.add(user)
            db.session.flush()

            company = CompanyProfile(
                user_id=user.id,
                name=name,
                website=website,
                contact_person=contact_person,
                contact_email=contact_email,
                industry=industry or None,
                approved=False,
            )
            db.session.add(company)
            db.session.commit()

            flash("Company registered. Await admin approval before you can post jobs.", "success")
            return redirect(url_for("login"))

        return render_template("auth/register_company.html", form=request.form)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
