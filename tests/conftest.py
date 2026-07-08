import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.auth.permissions import project_read_required, project_write_required
from app.extensions import db
from app.models import Project, ProjectUser, ReportCategory, User, UserRole


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    UPLOAD_ROOT = "/tmp/starx-test-uploads"
    MAX_UPLOAD_MB = 10
    MAX_IMAGES_PER_SECTION = 3


@pytest.fixture
def app():
    app = create_app(TestConfig)

    @app.get("/test/projects/<int:project_id>/read")
    @project_read_required()
    def test_project_read(project_id):
        return {"project_id": project_id}

    @app.post("/test/projects/<int:project_id>/write")
    @project_write_required()
    def test_project_write(project_id):
        return {"project_id": project_id}

    with app.app_context():
        db.create_all()
        seed_test_data()

    yield app

    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def seed_test_data():
    users = [
        make_user(1, "super", "super@example.com", UserRole.SUPER_ADMIN.value),
        make_user(2, "viewer", "viewer@example.com", UserRole.VIEWER_ADMIN.value),
        make_user(3, "reporter", "reporter@example.com", UserRole.REPORTER.value),
        make_user(4, "inactive", "inactive@example.com", UserRole.REPORTER.value, is_active=False),
        make_user(5, "pm", "pm@example.com", UserRole.PROJECT_MANAGER.value),
    ]
    projects = [
        Project(id=1, code="P001", name="Assigned Project"),
        Project(id=2, code="P002", name="Other Project"),
    ]
    assignments = [
        ProjectUser(id=1, project_id=1, user_id=3),
        ProjectUser(id=2, project_id=1, user_id=5),
    ]
    categories = [
        ReportCategory(id=1, project_id=1, name="Progress", icon="tools", sort_order=1, is_active=True),
        ReportCategory(id=2, project_id=1, name="Quality", sort_order=2, is_active=True),
        ReportCategory(id=3, project_id=2, name="Other Progress", sort_order=1, is_active=True),
    ]

    db.session.add_all([*users, *projects, *assignments, *categories])
    db.session.commit()


def make_user(user_id, username, email, role, is_active=True):
    return User(
        id=user_id,
        username=username,
        email=email,
        full_name=username.title(),
        password_hash=generate_password_hash("password123"),
        role=role,
        is_active=is_active,
    )
