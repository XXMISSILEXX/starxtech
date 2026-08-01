from app.extensions import db
from app.models.mixins import TimestampMixin


class ProgressType(TimestampMixin, db.Model):
    __tablename__ = "progress_types"
    __table_args__ = (
        db.UniqueConstraint("project_id", "name", name="uq_progress_types_project_name"),
        db.CheckConstraint(
            "value_mode IN ('quantity', 'money')",
            name="ck_progress_types_value_mode",
        ),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(200), nullable=False)
    value_mode = db.Column(db.String(20), nullable=False, default="quantity", server_default="quantity")
    description = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project", back_populates="progress_types")
    groups = db.relationship("ProgressGroup", back_populates="progress_type")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


class ProgressGroup(TimestampMixin, db.Model):
    __tablename__ = "progress_groups"
    __table_args__ = (
        db.UniqueConstraint("progress_type_id", "name", name="uq_progress_groups_type_name"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    progress_type_id = db.Column(
        db.BigInteger,
        db.ForeignKey("progress_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(200), nullable=False)
    note = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project")
    progress_type = db.relationship("ProgressType", back_populates="groups")
    items = db.relationship("ProgressItem", back_populates="progress_group")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


class ProgressItem(TimestampMixin, db.Model):
    __tablename__ = "progress_items"
    __table_args__ = (
        db.UniqueConstraint("progress_group_id", "name", name="uq_progress_items_group_name"),
        db.CheckConstraint("planned_quantity >= 0", name="ck_progress_items_planned_quantity_nonnegative"),
        db.CheckConstraint("opening_quantity >= 0", name="ck_progress_items_opening_quantity_nonnegative"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    progress_group_id = db.Column(
        db.BigInteger,
        db.ForeignKey("progress_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(300), nullable=False)
    unit = db.Column(db.String(30), nullable=False)
    planned_quantity = db.Column(db.Numeric(18, 3), nullable=False, default=0, server_default="0")
    opening_quantity = db.Column(db.Numeric(18, 3), nullable=False, default=0, server_default="0")
    completed_quantity = db.Column(db.Numeric(18, 3), nullable=False, default=0, server_default="0")
    assignee_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    note = db.Column(db.Text, nullable=True)
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project")
    progress_group = db.relationship("ProgressGroup", back_populates="items")
    entries = db.relationship("ProgressEntry", back_populates="progress_item")
    assignee_user = db.relationship("User", foreign_keys=[assignee_user_id])
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])


class ProgressEntry(TimestampMixin, db.Model):
    __tablename__ = "progress_entries"
    __table_args__ = (
        db.UniqueConstraint("progress_item_id", "report_date", name="uq_progress_entries_item_date"),
        db.CheckConstraint("quantity > 0", name="ck_progress_entries_quantity_positive"),
        db.Index("ix_progress_entries_project_date", "project_id", "report_date"),
    )

    id = db.Column(db.BigInteger().with_variant(db.Integer(), "sqlite"), primary_key=True)
    project_id = db.Column(
        db.BigInteger,
        db.ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    progress_item_id = db.Column(
        db.BigInteger,
        db.ForeignKey("progress_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    report_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.Numeric(18, 3), nullable=False)
    note = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=False)
    updated_by_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)

    project = db.relationship("Project")
    progress_item = db.relationship("ProgressItem", back_populates="entries")
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    updated_by = db.relationship("User", foreign_keys=[updated_by_id])
