"""Designated role logins: the teacher page only ever yields teacher
sessions, the student page only student sessions.

Contract: correct credentials + matching role → 200 with the standard login
payload; wrong password or unknown email → 401 with no role hint (no
enumeration beyond what /token already gives); correct password but wrong
role → 403 naming the expected role. The generic /token endpoint is
unchanged — it stays the login for parents and admins.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def register(client, email, role):
    r = client.post("/auth/register", json={
        "email": email, "name": f"Role {role}", "password": "Role@1234",
        "role": role})
    assert r.status_code == 201, r.text
    return r.json()


def login_as(client, path, email, password="Role@1234"):
    return client.post(path, data={"username": email, "password": password})


def check_teacher_path(client, teacher_email, student_email):
    """Paths as literals: the route-coverage canary parses string literals
    out of the test sources, so they must not hide in variables."""
    ok = login_as(client, "/auth/token/teacher", teacher_email)
    assert ok.status_code == 200, ok.text
    assert ok.json()["role"] == "teacher"

    wrong_role = login_as(client, "/auth/token/teacher", student_email)
    assert wrong_role.status_code == 403
    assert "teacher" in wrong_role.json()["detail"]

    bad_pw = client.post("/auth/token/teacher",
                         data={"username": teacher_email, "password": "Wrong@1234"})
    assert bad_pw.status_code == 401

    unknown = login_as(client, "/auth/token/teacher", "nobody@x.in")
    assert unknown.status_code == 401


def check_student_path(client, teacher_email, student_email):
    ok = login_as(client, "/auth/token/student", student_email)
    assert ok.status_code == 200, ok.text
    assert ok.json()["role"] == "student"

    wrong_role = login_as(client, "/auth/token/student", teacher_email)
    assert wrong_role.status_code == 403
    assert "student" in wrong_role.json()["detail"]

    bad_pw = client.post("/auth/token/student",
                         data={"username": student_email, "password": "Wrong@1234"})
    assert bad_pw.status_code == 401


def test_teacher_endpoint_accepts_only_teachers(client):
    register(client, "desig-teacher@x.in", "teacher")
    register(client, "desig-student@x.in", "student")

    check_teacher_path(client, "desig-teacher@x.in", "desig-student@x.in")
    # /api twin answers identically behind the production rewrite.
    assert client.post("/api/auth/token/teacher",
                       data={"username": "desig-teacher@x.in",
                             "password": "Role@1234"}).status_code == 200


def test_student_endpoint_accepts_only_students(client):
    register(client, "desig-teacher2@x.in", "teacher")
    register(client, "desig-student2@x.in", "student")

    check_student_path(client, "desig-teacher2@x.in", "desig-student2@x.in")
    assert client.post("/api/auth/token/student",
                       data={"username": "desig-student2@x.in",
                             "password": "Role@1234"}).status_code == 200
