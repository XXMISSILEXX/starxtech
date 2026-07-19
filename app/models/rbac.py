from app.extensions import db
from app.models.mixins import TimestampMixin

RBAC_ID = db.BigInteger().with_variant(db.Integer(), "sqlite")


class Role(TimestampMixin, db.Model):
    __tablename__ = "roles"

    id = db.Column(RBAC_ID, primary_key=True)
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    users = db.relationship("User", back_populates="role")
    role_permissions = db.relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class Permission(TimestampMixin, db.Model):
    __tablename__ = "permissions"

    id = db.Column(RBAC_ID, primary_key=True)
    code = db.Column(db.String(100), nullable=False, unique=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    module = db.Column(db.String(100), nullable=False)
    group_name = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    resource = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_dangerous = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    is_deprecated = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    role_permissions = db.relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(db.Model):
    __tablename__ = "role_permissions"
    __table_args__ = (db.UniqueConstraint("role_id", "permission_id", name="uq_role_permissions_role_permission"),)

    id = db.Column(RBAC_ID, primary_key=True)
    role_id = db.Column(RBAC_ID, db.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    permission_id = db.Column(RBAC_ID, db.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.relationship("Role", back_populates="role_permissions")
    permission = db.relationship("Permission", back_populates="role_permissions")
