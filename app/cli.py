import click
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User, UserRole


def register_cli(app):
    @app.cli.command("seed-admin")
    @click.option("--username", required=True, help="Admin username.")
    @click.option("--password", required=True, help="Admin password.")
    @click.option("--email", required=True, help="Admin email.")
    @click.option("--full-name", required=True, help="Admin full name.")
    def seed_admin(username, password, email, full_name):
        existing_admin = User.query.filter_by(role=UserRole.SUPER_ADMIN.value).first()
        if existing_admin:
            click.echo(f"SUPER_ADMIN already exists: username={existing_admin.username}")
            return

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            click.echo(f"Username already exists: {username}")
            return

        user = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=generate_password_hash(password),
            role=UserRole.SUPER_ADMIN.value,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created SUPER_ADMIN: username={username}")
