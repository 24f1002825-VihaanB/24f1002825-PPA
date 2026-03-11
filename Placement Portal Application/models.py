from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'company', 'student'

    student_profile = db.relationship("StudentProfile", back_populates="user", uselist=False)
    company_profile = db.relationship("CompanyProfile", back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"


class StudentProfile(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    name = db.Column(db.String(120), nullable=False)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)
    department = db.Column(db.String(80), nullable=False)
    cgpa = db.Column(db.Float, nullable=False)
    graduation_year = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    skills = db.Column(db.String(500), nullable=True)
    resume_filename = db.Column(db.String(255), nullable=True)
    blacklisted = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="student_profile")
    applications = db.relationship("Application", back_populates="student", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Student {self.roll_number} - {self.name}>"


class CompanyProfile(db.Model):
    __tablename__ = "companies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True)

    name = db.Column(db.String(150), nullable=False, unique=True)
    website = db.Column(db.String(255))
    contact_person = db.Column(db.String(120))
    contact_email = db.Column(db.String(120))
    industry = db.Column(db.String(120), nullable=True)
    approved = db.Column(db.Boolean, default=False, nullable=False)
    blacklisted = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship("User", back_populates="company_profile")
    jobs = db.relationship("Job", back_populates="company", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Company {self.name} approved={self.approved}>"


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(120))
    ctc = db.Column(db.String(80))
    description = db.Column(db.Text)
    min_cgpa = db.Column(db.Float, nullable=False, default=0.0)
    application_deadline = db.Column(db.Date, nullable=True)

    # status: 'pending', 'approved', 'rejected', 'closed'
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    company = db.relationship("CompanyProfile", back_populates="jobs")
    applications = db.relationship("Application", back_populates="job", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<Job {self.title} ({self.status})>"


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)

    # status: 'applied', 'shortlisted', 'interview', 'selected', 'rejected', 'placed'
    status = db.Column(db.String(20), nullable=False, default="applied")
    applied_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    job = db.relationship("Job", back_populates="applications")
    student = db.relationship("StudentProfile", back_populates="applications")
    placement = db.relationship("Placement", back_populates="application", uselist=False)

    __table_args__ = (
        db.UniqueConstraint("job_id", "student_id", name="uq_application_job_student"),
    )

    def __repr__(self) -> str:
        return f"<Application job={self.job_id} student={self.student_id} status={self.status}>"


class Placement(db.Model):
    __tablename__ = "placements"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False, unique=True)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    application = db.relationship("Application", back_populates="placement")

    def __repr__(self) -> str:
        return f"<Placement app={self.application_id}>"

