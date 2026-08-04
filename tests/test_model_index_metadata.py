from app.models.company_media import CompanyMediaAlbum
from app.models.project_document import ProjectDocumentFolder


def _index_by_name(model, name):
    return next(index for index in model.__table__.indexes if index.name == name)


def _index_expression_names(index):
    return [getattr(expression, "name", None) or str(expression) for expression in index.expressions]


def test_company_media_album_active_name_unique_index_is_declared_in_metadata(app):
    index = _index_by_name(CompanyMediaAlbum, "uq_company_media_albums_active_name")

    assert index.unique is True
    assert _index_expression_names(index) == ["lower(name)"]


def test_project_document_folder_sibling_name_unique_index_is_declared_in_metadata(app):
    index = _index_by_name(ProjectDocumentFolder, "uq_project_document_folders_sibling_name")

    assert index.unique is True
    assert _index_expression_names(index) == ["project_id", "parent_id", "lower(name)"]
