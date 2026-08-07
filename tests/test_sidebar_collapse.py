from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def login(client, username, password="password123"):
    return client.post("/login", data={"username_or_email": username, "password": password})


def _sidebars(markup):
    desktop_start = markup.index('<aside class="sidebar')
    desktop_end = markup.index("</aside>", desktop_start) + len("</aside>")
    mobile_start = markup.index('<div class="offcanvas', desktop_end)
    mobile_end = markup.index('<div class="app-content">', mobile_start)
    return markup[desktop_start:desktop_end], markup[mobile_start:mobile_end]


def test_sidebar_toggle_is_outside_desktop_sidebar_and_preloaded_before_render(client):
    login(client, "super")

    response = client.get("/reports/dashboard/system")

    assert response.status_code == 200
    markup = response.get_data(as_text=True)
    desktop_end = markup.index("</aside>", markup.index('<aside class="sidebar'))
    toggle_position = markup.index("data-sidebar-toggle")
    preload_position = markup.index("js/sidebar-toggle.js")

    assert toggle_position > desktop_end
    assert preload_position < markup.index('<aside class="sidebar')
    assert 'data-sidebar-storage-key="starx.sidebar.' in markup
    toggle = markup[toggle_position:markup.index("</button>", toggle_position)]
    assert 'aria-expanded="true"' in toggle
    assert 'aria-label="Thu gọn thanh điều hướng"' in toggle


def test_sidebar_watermarks_and_navigation_render_on_desktop_and_mobile(client):
    login(client, "super")

    response = client.get("/reports/dashboard/system")

    assert response.status_code == 200
    markup = response.get_data(as_text=True)
    desktop, mobile = _sidebars(markup)
    labels = (
        "Đổi phân hệ",
        "Dashboard quản trị",
        "Hôm nay",
        "Quản lý dự án &amp; đối tác",
        "Cấu hình",
        "Cài đặt cá nhân",
    )

    assert markup.count("img/crossed-swords.svg") == 2
    for label in labels:
        assert f"<span>{label}</span>" in desktop
        assert f"<span>{label}</span>" in mobile


def test_sidebar_collapse_assets_define_shared_width_and_accessible_label_hiding():
    styles = (PROJECT_ROOT / "app/static/css/app.css").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "app/static/js/sidebar-toggle.js").read_text(encoding="utf-8")

    assert "--sx-sidebar-width: 250px" in styles
    assert "html.sidebar-collapsed" in styles
    assert "--sx-sidebar-width: 76px" in styles
    assert "overflow-x: hidden" in styles
    assert "overflow-y: auto" in styles
    assert "left: calc(var(--sx-sidebar-width) - 17px)" in styles
    assert "position: fixed" in styles
    assert "width: 1px" in styles and "clip: rect(0, 0, 0, 0)" in styles
    assert "white-space: normal" in styles
    assert "cubic-bezier(0.4, 0, 0.2, 1)" in styles
    assert "collapsedValue" in script
