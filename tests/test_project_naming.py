from app.services.project_naming import derive_title, sanitize_name


def test_sanitize_name():
    assert sanitize_name('a:b*c?') == "a_b_c_"


def test_derive_title_prefers_override():
    assert derive_title("https://example.com/video", "我的项目") == "我的项目"
