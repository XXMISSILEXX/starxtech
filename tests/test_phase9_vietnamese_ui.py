from pathlib import Path


UI_FILES = [
    "app/templates/project_operations/updates/form.html",
    "app/templates/project_operations/updates/index.html",
    "app/templates/project_operations/project_assignments.html",
    "app/templates/dashboard/contractor.html",
]


def test_reports_project_operations_templates_do_not_render_raw_internal_enums():
    rendered_sources = "\n".join(Path(path).read_text() for path in UI_FILES)
    # Enum values are allowed only in option values, comparisons, route data,
    # and JS/API identifiers; user-facing text must pass through label helpers.
    for token in (">GENERAL<", ">PROGRESS<", ">HANDOVER<", ">CONTRACTOR<", ">STATUS_CHANGE<", ">NOTE<"):
        assert token not in rendered_sources
    assert "Vấn đề đang mở" not in rendered_sources
    assert "Section status" not in rendered_sources


def test_project_update_and_assignment_templates_use_central_label_filters():
    rendered_sources = "\n".join(Path(path).read_text() for path in UI_FILES)
    assert "project_update_type_label" in rendered_sources
    assert "contractor_role_label" in rendered_sources
    assert "assignment_status_label" in rendered_sources
