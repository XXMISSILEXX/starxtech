import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class LoginPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []
        self.videos = []
        self.in_title = False
        self.title = ""
        self.text = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link":
            self.links.append(attributes)
        elif tag == "img":
            self.images.append(attributes)
        elif tag == "video":
            self.videos.append(attributes)
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        self.text += data
        if self.in_title:
            self.title += data


def _parse_login_page(client):
    response = client.get("/login")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    parser = LoginPageParser()
    parser.feed(html)
    return response, html, parser


def _assert_versioned_static_url(url, expected_path):
    parsed = urlsplit(url)
    assert parsed.path == expected_path
    assert parse_qs(parsed.query).get("v")


def test_login_page_includes_versioned_favicons_and_manifest(client):
    _, _, parser = _parse_login_page(client)
    links_by_target = {link.get("href", "").split("?", 1)[0]: link for link in parser.links}

    for path in (
        "/static/img/favicon.ico",
        "/static/img/favicon-96x96.png",
        "/static/img/apple-touch-icon.png",
        "/static/site.webmanifest",
    ):
        _assert_versioned_static_url(links_by_target[path]["href"], path)

    assert links_by_target["/static/site.webmanifest"]["rel"] == "manifest"


def test_login_page_uses_starx_technology_brand_and_background_video(client):
    _, html, parser = _parse_login_page(client)

    assert "brand-mark" not in html
    assert "SX" not in html
    assert "starx-logo.webp" in html
    assert "StarX Technology" in html
    assert "Made by Tran Hieu Slayer" in parser.text
    assert html.index("login-credit") > html.rindex("card-body")
    assert '<span class="login-credit-slayer-text">Slayer</span>' in html
    assert "StarX Technology" in parser.title
    assert "Daily Report" not in parser.title

    images_by_target = {image.get("src", "").split("?", 1)[0]: image for image in parser.images}
    logo = images_by_target["/static/img/starx-logo.webp"]
    assert logo["width"] == "120"
    assert logo["height"] == "47"
    swords = images_by_target["/static/img/crossed-swords.svg"]
    assert swords["aria-hidden"] == "true"
    assert swords["tabindex"] == "-1"
    _assert_versioned_static_url(swords["src"], "/static/img/crossed-swords.svg")

    assert len(parser.videos) == 1
    video = parser.videos[0]
    for attribute in ("muted", "autoplay", "loop", "playsinline"):
        assert attribute in video
    assert video["preload"] == "metadata"
    assert video["aria-hidden"] == "true"
    assert video["tabindex"] == "-1"
    _assert_versioned_static_url(video["poster"], "/static/img/login-background-poster.webp")
    assert "login-background.webm" in html


def test_login_page_remains_public_and_form_authentication_works(client):
    public_response = client.get("/login")
    assert public_response.status_code == 200

    for path in (
        "/static/img/starx-logo.webp",
        "/static/img/crossed-swords.svg",
        "/static/img/login-background-poster.webp",
        "/static/video/login-background.webm",
        "/static/img/favicon.ico",
        "/static/img/favicon-96x96.png",
        "/static/img/apple-touch-icon.png",
        "/static/site.webmanifest",
    ):
        with client.get(path) as asset_response:
            assert asset_response.status_code == 200

    rejected = client.post("/login", data={"username_or_email": "reporter", "password": "wrong-password"})
    assert rejected.status_code == 401
    assert "Tên đăng nhập/email hoặc mật khẩu không đúng" in rejected.get_data(as_text=True)

    accepted = client.post("/login", data={"username_or_email": "reporter", "password": "password123"})
    assert accepted.status_code == 302


def test_webmanifest_has_static_web_app_icon_paths():
    manifest_path = Path(__file__).parents[1] / "app/static/site.webmanifest"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["name"] == "StarX Technology"
    assert all(icon["src"].startswith("/static/") for icon in manifest["icons"])
