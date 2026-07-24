from app.extensions import db
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class Company(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "companies"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    industry = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    company_photo_storage_object_id = db.Column(db.BigInteger, db.ForeignKey("storage_objects.id"), nullable=True, index=True)

    partners = db.relationship("Partner", back_populates="company")
    company_photo_storage_object = db.relationship("StorageObject", foreign_keys=[company_photo_storage_object_id])
    departments = db.relationship(
        "CompanyDepartment",
        back_populates="company",
        cascade="all, delete-orphan",
        order_by="CompanyDepartment.display_order.asc(), CompanyDepartment.name.asc()",
    )


class CompanyDepartment(TimestampMixin, db.Model):
    __tablename__ = "company_departments"
    __table_args__ = (
        db.UniqueConstraint("company_id", "name", name="uq_company_departments_company_name"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    company_id = db.Column(db.BigInteger, db.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    parent_department_id = db.Column(
        db.BigInteger,
        db.ForeignKey("company_departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    is_special_department = db.Column(db.Boolean, nullable=False, default=False, server_default="false")

    company = db.relationship("Company", back_populates="departments")
    parent_department = db.relationship("CompanyDepartment", remote_side=[id], backref="child_departments")


class Partner(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "partners"

    id = db.Column(db.BigInteger, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False, index=True)
    company_id = db.Column(db.BigInteger, db.ForeignKey("companies.id"), nullable=True, index=True)
    department_id = db.Column(db.BigInteger, db.ForeignKey("company_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    department = db.Column(db.String(255), nullable=True)
    position = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    address = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_department_head = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")
    created_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    updated_by_user_id = db.Column(db.BigInteger, db.ForeignKey("users.id"), nullable=True)
    profile_photo_storage_object_id = db.Column(db.BigInteger, db.ForeignKey("storage_objects.id"), nullable=True, index=True)

    company = db.relationship("Company", back_populates="partners")
    profile_photo_storage_object = db.relationship("StorageObject", foreign_keys=[profile_photo_storage_object_id])
    company_department = db.relationship("CompanyDepartment")
    field_values = db.relationship(
        "PartnerFieldValue",
        back_populates="partner",
        cascade="all, delete-orphan",
        order_by="PartnerFieldValue.sort_order.asc(), PartnerFieldValue.id.asc()",
    )
    outgoing_relationships = db.relationship(
        "PartnerRelationship",
        foreign_keys="PartnerRelationship.from_partner_id",
        back_populates="from_partner",
        cascade="all, delete-orphan",
    )
    incoming_relationships = db.relationship(
        "PartnerRelationship",
        foreign_keys="PartnerRelationship.to_partner_id",
        back_populates="to_partner",
        cascade="all, delete-orphan",
    )


class PartnerFieldDefinition(TimestampMixin, db.Model):
    __tablename__ = "partner_field_definitions"

    id = db.Column(db.BigInteger, primary_key=True)
    label = db.Column(db.String(255), nullable=False)
    field_key = db.Column(db.String(120), nullable=False, unique=True)
    field_type = db.Column(db.String(50), nullable=False)
    group_name = db.Column(db.String(255), nullable=True)
    options_json = db.Column(db.JSON, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_required = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")

    values = db.relationship("PartnerFieldValue", back_populates="field_definition")
    collection_items = db.relationship("PartnerFieldCollectionItem", back_populates="field_definition")


class PartnerFieldCollection(TimestampMixin, db.Model):
    __tablename__ = "partner_field_collections"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")

    items = db.relationship(
        "PartnerFieldCollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="PartnerFieldCollectionItem.sort_order.asc(), PartnerFieldCollectionItem.id.asc()",
    )


class PartnerFieldCollectionItem(TimestampMixin, db.Model):
    __tablename__ = "partner_field_collection_items"
    __table_args__ = (
        db.UniqueConstraint("collection_id", "field_definition_id", name="uq_partner_field_collection_field"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    collection_id = db.Column(
        db.BigInteger,
        db.ForeignKey("partner_field_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_definition_id = db.Column(
        db.BigInteger,
        db.ForeignKey("partner_field_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    collection = db.relationship("PartnerFieldCollection", back_populates="items")
    field_definition = db.relationship("PartnerFieldDefinition", back_populates="collection_items")


class PartnerFieldValue(TimestampMixin, db.Model):
    __tablename__ = "partner_field_values"
    __table_args__ = (
        db.Index("idx_partner_field_values_partner_id", "partner_id"),
    )

    id = db.Column(db.BigInteger, primary_key=True)
    partner_id = db.Column(
        db.BigInteger,
        db.ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_definition_id = db.Column(
        db.BigInteger,
        db.ForeignKey("partner_field_definitions.id"),
        nullable=True,
    )
    field_label_snapshot = db.Column(db.String(255), nullable=False)
    field_key_snapshot = db.Column(db.String(120), nullable=True)
    field_type_snapshot = db.Column(db.String(50), nullable=False)
    group_name_snapshot = db.Column(db.String(255), nullable=True)
    value_text = db.Column(db.Text, nullable=True)
    value_number = db.Column(db.Numeric(18, 4), nullable=True)
    value_date = db.Column(db.Date, nullable=True)
    value_boolean = db.Column(db.Boolean, nullable=True)
    value_json = db.Column(db.JSON, nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    partner = db.relationship("Partner", back_populates="field_values")
    field_definition = db.relationship("PartnerFieldDefinition", back_populates="values")


class PartnerRelationship(TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = "partner_relationships"

    id = db.Column(db.BigInteger, primary_key=True)
    from_partner_id = db.Column(
        db.BigInteger,
        db.ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_partner_id = db.Column(
        db.BigInteger,
        db.ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = db.Column(db.BigInteger, db.ForeignKey("companies.id"), nullable=True, index=True)
    department_id = db.Column(db.BigInteger, db.ForeignKey("company_departments.id", ondelete="SET NULL"), nullable=True, index=True)
    partner_id = db.Column(db.BigInteger, db.ForeignKey("partners.id", ondelete="CASCADE"), nullable=True, index=True)
    department = db.Column(db.String(255), nullable=True)
    position_title = db.Column(db.String(255), nullable=True)
    parent_partner_id = db.Column(db.BigInteger, db.ForeignKey("partners.id", ondelete="SET NULL"), nullable=True, index=True)
    parent_relationship_id = db.Column(db.BigInteger, db.ForeignKey("partner_relationships.id", ondelete="SET NULL"), nullable=True)
    relationship_type = db.Column(db.String(120), nullable=False)
    is_department_head = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    display_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    note = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default="true")

    company = db.relationship("Company")
    company_department = db.relationship("CompanyDepartment")
    partner = db.relationship("Partner", foreign_keys=[partner_id])
    parent_partner = db.relationship("Partner", foreign_keys=[parent_partner_id])
    parent_relationship = db.relationship("PartnerRelationship", remote_side=[id])
    from_partner = db.relationship(
        "Partner",
        foreign_keys=[from_partner_id],
        back_populates="outgoing_relationships",
    )
    to_partner = db.relationship(
        "Partner",
        foreign_keys=[to_partner_id],
        back_populates="incoming_relationships",
    )
