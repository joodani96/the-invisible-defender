from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from fastapi.testclient import TestClient
from app.main import app


class Dependencies(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.urls.append(attrs["src"])
        if tag == "link" and attrs.get("href", "").startswith("/static/"):
            self.urls.append(attrs["href"])
        if tag == "iframe" and attrs.get("src"):
            self.urls.append(attrs["src"])


client = TestClient(app)
assert app.version == "0.9.16"
for path in ("/studio", "/about", "/static/viewer.html", "/static/shield.svg"):
    assert client.get(path).status_code == 200, path
assert client.get("/demo").status_code == 404
assert client.get("/3d").status_code == 404
assert client.get("/api/analyze/central-through-ball").status_code == 404
assert client.get("/api/hybrid/central-through-ball").status_code == 404
for page in ("/studio", "/about", "/static/viewer.html"):
    html = client.get(page).text
    parser = Dependencies()
    parser.feed(html)
    for url in parser.urls:
        if urlsplit(url).path.startswith("/static/"):
            response = client.get(url)
            assert response.status_code == 200 and response.content, url
print("Project package consistent: 0.9.16 (Studio, About, internal viewer, static assets OK)")
