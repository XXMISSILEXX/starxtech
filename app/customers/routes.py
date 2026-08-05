from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from app.audit import log_audit
from app.customers import bp
from app.customers.services import (
    accessible_customers_query,
    active_manageable_customer_choices,
    can_access_customer,
    can_manage_customer,
    customer_name_is_available,
    manageable_unclassified_projects,
    normalize_customer_name,
)
from app.extensions import db
from app.models import Customer, Project
from app.project_memberships import accessible_project_ids, can_manage_project_scope


def _permission_required(code):
    if not current_user.can(code):
        abort(403)


def _customer_or_404(customer_id):
    return Customer.query.filter_by(id=customer_id).first_or_404()


def _visible_projects(customer):
    query = Project.query.filter(
        Project.customer_id == customer.id,
        Project.deleted_at.is_(None),
    )
    project_ids = accessible_project_ids(current_user, ("can_view_project",))
    if project_ids is not None:
        query = query.filter(Project.id.in_(project_ids or [0]))
    return query.order_by(Project.code.asc()).all()


def _customer_snapshot(customer):
    return {
        "name": customer.name,
        "normalized_name": customer.normalized_name,
        "description": customer.description,
        "is_active": customer.is_active,
        "archived_at": customer.archived_at.isoformat() if customer.archived_at else None,
        "created_by_id": customer.created_by_id,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
    }


def _save_customer(customer=None):
    is_new = customer is None
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip() or None
    errors = []
    if not name:
        errors.append("Tên khách hàng là bắt buộc.")
    elif not customer_name_is_available(name, customer.id if customer else None):
        errors.append("Tên khách hàng đã tồn tại.")

    if errors:
        for error in errors:
            flash(error, "danger")
        return render_template("customers/form.html", customer=customer), 400

    old_values = _customer_snapshot(customer) if customer else None
    if customer is None:
        customer = Customer(created_by_id=current_user.id)
        db.session.add(customer)
    customer.name = name
    customer.normalized_name = normalize_customer_name(name)
    customer.description = description
    customer.updated_by_id = current_user.id
    db.session.flush()
    if not is_new:
        log_audit(
            "customer.update",
            "Customer",
            customer.id,
            old_values=old_values,
            new_values=_customer_snapshot(customer),
        )
    db.session.commit()
    flash("Đã lưu khách hàng.", "success")
    return redirect(url_for("customers.detail", customer_id=customer.id))


@bp.get("")
def index():
    _permission_required("customers.view")
    query = accessible_customers_query(current_user, include_archived=request.args.get("archived") == "1")
    search = request.args.get("q", "").strip()
    if search:
        pattern = f"%{search}%"
        query = query.filter(Customer.name.ilike(pattern))
    customers = query.order_by(Customer.is_active.desc(), Customer.name.asc()).all()
    return render_template("customers/index.html", customers=customers, search=search)


@bp.get("/<int:customer_id>")
def detail(customer_id):
    _permission_required("customers.view")
    customer = _customer_or_404(customer_id)
    if not can_access_customer(current_user, customer):
        abort(403)
    projects = _visible_projects(customer)
    can_edit = current_user.can("customers.edit") and can_manage_customer(current_user, customer)
    can_move_projects = bool(can_edit and customer.is_active and customer.archived_at is None)
    return render_template(
        "customers/detail.html",
        customer=customer,
        projects=projects,
        customer_choices=active_manageable_customer_choices(current_user),
        unclassified_projects=manageable_unclassified_projects(current_user) if can_move_projects else [],
        can_edit=can_edit,
        can_move_projects=can_move_projects,
        can_attach_projects=can_move_projects,
        can_archive=current_user.can("customers.archive") and can_manage_customer(current_user, customer),
    )


@bp.route("/new", methods=["GET", "POST"])
def create():
    _permission_required("customers.create")
    if request.method == "POST":
        return _save_customer()
    return render_template("customers/form.html", customer=None)


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
def edit(customer_id):
    _permission_required("customers.edit")
    customer = _customer_or_404(customer_id)
    if not can_access_customer(current_user, customer) or not can_manage_customer(current_user, customer):
        abort(403)
    if request.method == "POST":
        return _save_customer(customer)
    return render_template("customers/form.html", customer=customer)


@bp.post("/<int:customer_id>/archive")
def archive(customer_id):
    _permission_required("customers.archive")
    customer = _customer_or_404(customer_id)
    if not can_access_customer(current_user, customer) or not can_manage_customer(current_user, customer):
        abort(403)
    if not customer.is_active:
        return redirect(url_for("customers.detail", customer_id=customer.id))
    old_values = _customer_snapshot(customer)
    customer.is_active = False
    customer.archived_at = datetime.utcnow()
    customer.updated_by_id = current_user.id
    log_audit("customer.archive", "Customer", customer.id, old_values=old_values, new_values=_customer_snapshot(customer))
    db.session.commit()
    flash("Đã lưu trữ khách hàng. Dự án và báo cáo vẫn được giữ nguyên.", "success")
    return redirect(url_for("customers.index", archived="1"))


@bp.post("/<int:customer_id>/restore")
def restore(customer_id):
    _permission_required("customers.archive")
    customer = _customer_or_404(customer_id)
    if not can_access_customer(current_user, customer) or not can_manage_customer(current_user, customer):
        abort(403)
    if customer.is_active:
        return redirect(url_for("customers.detail", customer_id=customer.id))
    if not customer_name_is_available(customer.name, customer.id):
        flash("Không thể khôi phục vì tên khách hàng đã được dùng.", "danger")
        return redirect(url_for("customers.detail", customer_id=customer.id))
    old_values = _customer_snapshot(customer)
    customer.is_active = True
    customer.archived_at = None
    customer.updated_by_id = current_user.id
    log_audit("customer.restore", "Customer", customer.id, old_values=old_values, new_values=_customer_snapshot(customer))
    db.session.commit()
    flash("Đã khôi phục khách hàng.", "success")
    return redirect(url_for("customers.detail", customer_id=customer.id))


@bp.post("/<int:customer_id>/projects/<int:project_id>/move")
def move_project(customer_id, project_id):
    _permission_required("customers.edit")
    customer = Customer.query.filter(
        Customer.id == customer_id,
        Customer.is_active.is_(True),
        Customer.archived_at.is_(None),
    ).first_or_404()
    project = Project.query.filter(Project.id == project_id, Project.deleted_at.is_(None)).first_or_404()
    # The URL customer ID is the client-supplied source.  Never move a project
    # unless it still belongs to that persisted source customer.
    if project.customer_id != customer.id:
        abort(403)
    if not can_access_customer(current_user, customer) or not can_manage_project_scope(current_user, project):
        abort(403)
    if not can_manage_customer(current_user, customer):
        abort(403)
    target_id = request.form.get("target_customer_id", type=int)
    if target_id is None:
        abort(400)
    target = Customer.query.filter(
        Customer.id == target_id,
        Customer.is_active.is_(True),
        Customer.archived_at.is_(None),
    ).first_or_404()
    if not can_access_customer(current_user, target) or not can_manage_customer(current_user, target):
        abort(403)
    if target.id == customer.id:
        abort(400, description="Dự án đã thuộc khách hàng này.")
    old_values = {"customer_id": project.customer_id}
    project.customer_id = target.id
    log_audit("project.customer.move", "Project", project.id, old_values=old_values, new_values={"customer_id": target.id})
    db.session.commit()
    flash("Đã chuyển dự án sang khách hàng mới.", "success")
    return redirect(url_for("customers.detail", customer_id=target.id))


def _attach_project(customer_id, project_id):
    """Attach an unclassified project to the customer shown in the URL."""
    _permission_required("customers.edit")
    customer = Customer.query.filter(
        Customer.id == customer_id,
        Customer.is_active.is_(True),
        Customer.archived_at.is_(None),
    ).first_or_404()
    project = Project.query.filter(
        Project.id == project_id,
        Project.deleted_at.is_(None),
    ).first_or_404()
    if project.customer_id is not None:
        abort(403)
    if (
        not can_access_customer(current_user, customer)
        or not can_manage_customer(current_user, customer)
        or not can_manage_project_scope(current_user, project)
    ):
        abort(403)

    project.customer_id = customer.id
    log_audit(
        "project.customer.attach",
        "Project",
        project.id,
        old_values={"customer_id": None},
        new_values={"customer_id": customer.id},
    )
    db.session.commit()
    flash("Đã gắn dự án vào khách hàng.", "success")
    return redirect(url_for("customers.detail", customer_id=customer.id))


@bp.post("/<int:customer_id>/projects/attach")
def attach_project_from_form(customer_id):
    project_id = request.form.get("project_id", type=int)
    if project_id is None:
        abort(400)
    return _attach_project(customer_id, project_id)


@bp.post("/<int:customer_id>/projects/<int:project_id>/attach")
def attach_project(customer_id, project_id):
    """Compatibility endpoint for attaching a known unclassified project."""
    return _attach_project(customer_id, project_id)
