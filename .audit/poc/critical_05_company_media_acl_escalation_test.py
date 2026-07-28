"""Secure regression: a share-only album ACL must not be able to add edit rights."""

pytest_plugins = ("tests.conftest",)

from app.extensions import db
from app.models import CompanyMediaAlbum, CompanyMediaAlbumPermission, User


def _login(client, username):
    # The shared TestConfig disables CSRF, which is the repository's normal test convention.
    return client.post("/login", data={"username_or_email": username, "password": "password123"})


def test_share_only_acl_holder_cannot_escalate_own_album_capabilities(client, app):
    with app.app_context():
        actor = User.query.filter_by(username="reporter").one()
        album = CompanyMediaAlbum(id=9005, name="Audit restricted album", is_restricted=True, created_by_id=6)
        db.session.add(album)
        db.session.flush()
        acl = CompanyMediaAlbumPermission(
            album_id=album.id,
            principal_type="user",
            user_id=actor.id,
            created_by_id=6,
            can_share=True,
        )
        db.session.add(acl)
        db.session.commit()
        album_id, actor_id = album.id, actor.id

    assert _login(client, "reporter").status_code == 302
    response = client.post(
        f"/company-media/albums/{album_id}/permissions",
        data={
            "principal_type": "user",
            "principal_id": str(actor_id),
            "can_view": "1",
            "can_edit": "1",
            "can_delete": "1",
            "can_upload": "1",
            "can_download": "1",
            "can_share": "1",
        },
    )

    with app.app_context():
        db.session.expire_all()
        persisted_acl = CompanyMediaAlbumPermission.query.filter_by(album_id=album_id, user_id=actor_id).one()
        escalation_present = any(
            getattr(persisted_acl, flag)
            for flag in ("can_edit", "can_delete", "can_upload", "can_download")
        )

    secure = response.status_code in {400, 403, 404, 422} and not escalation_present
    assert secure, (
        "secure behavior must reject a share-only ACL holder's permission rewrite; "
        f"got HTTP {response.status_code}, escalated flags present={escalation_present}"
    )
