"""HTTP smoke tests for every local static dependency of the 3D page."""
from html.parser import HTMLParser
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from app.main import app


class _Dependencies(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.urls.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet" and attrs.get("href"):
            self.urls.append(attrs["href"])


def test_3d_html_dependencies_are_publicly_served():
    client = TestClient(app)
    page = client.get("/static/viewer.html")
    assert page.status_code == 200
    parser = _Dependencies()
    parser.feed(page.text)
    local_urls = [url for url in parser.urls if urlsplit(url).path.startswith("/static/")]
    assert len(local_urls) >= 7
    assert any("defender3d_stadium.js" in url for url in local_urls)
    for url in local_urls:
        response = client.get(url)
        assert response.status_code == 200, f"Missing static asset {url}: {response.status_code}"
        assert response.content, f"Empty static asset {url}"
        if urlsplit(url).path.endswith(".js"):
            assert "javascript" in response.headers["content-type"]


def test_stadium_module_is_available_and_precedes_3d_bootstrap():
    client = TestClient(app)
    page = client.get("/static/viewer.html").text
    assert page.index("/static/defender3d_stadium.js") < page.index("/static/defender3d.js")
    script = client.get("/static/defender3d_stadium.js?v=0913")
    assert script.status_code == 200
    assert "root.TIDStadium=api" in script.text
    assert "function build(" in script.text
