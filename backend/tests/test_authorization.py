"""Authorization and abuse-limit coverage for the P1 fixes:

* approval alone must not make a private/school file downloadable,
* the pending queue and review action are confined to the uploader's school,
* non-auth write endpoints are rate limited,
* unexpected errors return a request id instead of a traceback,
* the API reference is not published in production.
"""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, docs_paths

PDF = b"%PDF-1.4 fake content"


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def login(client, email, password):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def signup(client, email, school_name=""):
    r = client.post("/auth/register", json={
        "email": email, "name": "Probe", "password": "Original@123",
        "role": "student", "class_grade": 8, "board": "Maharashtra SSC",
        "school_name": school_name})
    assert r.status_code == 201, r.text
    return login(client, email, "Original@123")


def upload(client, headers, visibility="public", title="Probe notes"):
    r = client.post("/materials", data={
        "title": title, "type": "notes", "class_grade": 8,
        "board": "Maharashtra SSC", "subject_name": "Science", "lang": "en",
        "visibility": visibility, "source_of_content": "test fixture"},
        files={"file": ("a.pdf", PDF, "application/pdf")}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_private_material_is_not_downloadable_by_others(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")
    mid = upload(client, teacher, visibility="private", title="Private key")

    # Owner keeps access.
    assert client.get(f"/materials/{mid}/download", headers=teacher).status_code == 200
    # Anyone else gets 404 — including on the direct file endpoint, which used
    # to check approval only.
    assert client.get(f"/materials/{mid}/download", headers=student).status_code == 404
    assert client.get(f"/materials/{mid}/download").status_code == 401
    # And it never shows up in their listing.
    listed = client.get("/materials", params={"limit": 100}, headers=student).json()
    assert mid not in [m["id"] for m in listed]


def test_school_material_is_scoped_to_the_uploaders_school(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    classmate = login(client, "student1@gramshiksha.in", "Learn@1234")
    outsider = signup(client, "outsider-a@gramshiksha.in", school_name="Other School A")
    mid = upload(client, teacher, visibility="school", title="School only")

    assert client.get(f"/materials/{mid}/download", headers=classmate).status_code == 200
    assert client.get(f"/materials/{mid}/download", headers=outsider).status_code == 404
    listed = client.get("/materials", params={"limit": 100}, headers=outsider).json()
    assert mid not in [m["id"] for m in listed]


def test_pending_queue_is_school_scoped(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    classmate = login(client, "student1@gramshiksha.in", "Learn@1234")
    outsider = signup(client, "outsider-b@gramshiksha.in", school_name="Other School B")

    mine = upload(client, classmate, title="Classmate pending")
    theirs = upload(client, outsider, title="Other school pending")

    teacher_queue = [m["id"] for m in client.get("/materials/pending", headers=teacher).json()]
    assert mine in teacher_queue          # same school → moderatable
    assert theirs not in teacher_queue    # other school → invisible

    admin_queue = [m["id"] for m in client.get("/materials/pending", headers=admin).json()]
    assert theirs in admin_queue          # platform admin sees everything


def test_review_cannot_target_another_school_by_id(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    outsider = signup(client, "outsider-c@gramshiksha.in", school_name="Other School C")
    mid = upload(client, outsider, title="Foreign pending")

    # Knowing the id is not enough: review is scoped like the queue.
    r = client.post(f"/materials/{mid}/review", data={"decision": "approved"},
                    headers=teacher)
    assert r.status_code == 404

    r = client.post(f"/materials/{mid}/review", data={"decision": "approved"},
                    headers=admin)
    assert r.status_code == 200
    assert r.json()["status"] == "approved"


def test_report_endpoint_is_rate_limited(client):
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    mid = upload(client, teacher, title="Spam target")

    statuses = []
    for _ in range(12):
        r = client.post(f"/materials/{mid}/report",
                        data={"reason": "incorrect"}, headers=teacher)
        statuses.append(r.status_code)
    assert statuses.count(429) >= 1, f"no rate limiting applied: {statuses}"
    assert statuses[0] == 201


def test_unhandled_error_returns_json_with_request_id(client):
    def boom():
        raise ValueError("SECRET-TRACEBACK-MARKER")

    app.add_api_route("/__boom", boom, methods=["GET"])
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/__boom")
    finally:
        app.router.routes = [route for route in app.router.routes
                             if getattr(route, "path", None) != "/__boom"]

    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error"
    assert body["request_id"] and body["request_id"] != "-"
    assert r.headers.get("X-Request-ID") == body["request_id"]
    # The traceback stays server-side.
    assert "SECRET-TRACEBACK-MARKER" not in r.text


def test_every_response_carries_a_request_id(client):
    assert client.get("/health").headers.get("X-Request-ID")
    # Health checks stay quiet but still get an id.
    assert client.get("/ready").headers.get("X-Request-ID")


def test_api_reference_is_hidden_in_production():
    prod = Settings(database_url="postgresql+psycopg://user:pass@host/db",
                    jwt_secret="x" * 64)
    assert docs_paths(prod) == (None, None)

    dev = Settings(database_url="sqlite:///./local.db")
    assert docs_paths(dev) == ("/docs", "/openapi.json")

    # Deliberate override still wins either way.
    forced = Settings(database_url="postgresql+psycopg://user:pass@host/db",
                      docs_enabled=True)
    assert docs_paths(forced) == ("/docs", "/openapi.json")
    hidden = Settings(database_url="sqlite:///./local.db", docs_enabled=False)
    assert docs_paths(hidden) == (None, None)
