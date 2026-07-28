"""Integrity checks for the partner reporting hierarchy."""

from app.models import Partner, PartnerRelationship


class RelationshipGraphValidationError(ValueError):
    pass


def validate_proposed_relationship_graph(company_id, proposed_edge, replacing_relationship_id=None):
    """Validate the full post-submit hierarchy before any ORM row is changed.

    Partner relationships retain their own history rows.  Multiple active
    descriptive rows can refer to the same reporting parent, but conflicting
    parent edges are rejected.  Applying a replacement in memory first catches
    cycles that only become visible when all submitted/current edges are
    considered together.
    """
    rows = (
        PartnerRelationship.query.filter(
            PartnerRelationship.company_id == company_id,
            PartnerRelationship.deleted_at.is_(None),
            PartnerRelationship.is_active.is_(True),
        )
        .order_by(PartnerRelationship.id.asc())
        .all()
    )
    edges = [
        {
            "relationship_id": row.id,
            "partner_id": row.partner_id,
            "parent_partner_id": row.parent_partner_id,
            "relationship_type": row.relationship_type,
        }
        for row in rows
        if row.id != replacing_relationship_id
    ]
    edges.append({"relationship_id": replacing_relationship_id, **proposed_edge})

    active_partner_ids = {
        row.id
        for row in Partner.query.filter(
            Partner.company_id == company_id,
            Partner.deleted_at.is_(None),
            Partner.is_active.is_(True),
        ).all()
    }
    parent_by_partner = {}
    for edge in edges:
        partner_id = edge["partner_id"]
        parent_id = edge["parent_partner_id"]
        if partner_id not in active_partner_ids:
            raise RelationshipGraphValidationError("Đối tác trong quan hệ không hợp lệ.")
        if parent_id is not None and parent_id not in active_partner_ids:
            raise RelationshipGraphValidationError("Cấp trên không hợp lệ.")
        if parent_id == partner_id:
            raise RelationshipGraphValidationError("Đối tác không thể báo cáo cho chính mình.")
        if partner_id in parent_by_partner and parent_by_partner[partner_id] != parent_id:
            raise RelationshipGraphValidationError("Đối tác có quan hệ cấp trên mâu thuẫn.")
        parent_by_partner[partner_id] = parent_id

    # Walk every proposed node.  The local visited set both bounds traversal
    # and detects direct, indirect, and multi-edge cycles deterministically.
    for start_partner_id in parent_by_partner:
        visited = {start_partner_id}
        current = parent_by_partner[start_partner_id]
        while current is not None:
            if current in visited:
                raise RelationshipGraphValidationError("Không thể tạo quan hệ vòng lặp.")
            visited.add(current)
            current = parent_by_partner.get(current)
