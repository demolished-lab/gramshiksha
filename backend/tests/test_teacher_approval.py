"""Teacher approval: registration hands out the role, approval confers it.

`POST /auth/register` has always accepted role="teacher" with no gate, and the
`teacher` role carries publishing, moderation and roster powers. This suite
pins the new contract: a self-registered teacher is `pending`, every one of
those powers refuses them with a specific reason, material they upload goes
into the review queue instead of auto-publishing, and only a platform admin
can approve them.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

PDF = b"%PDF-1.4 fake content"


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def login(client, email, password):
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def register_teacher(client, email):
    """Sign up a brand-new teacher exactly as the public form would."""
    r = client.post("/auth/register", json={
        "email": email, "name": "New Teacher", "password": "Original@123",
        "role": "teacher"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "teacher" and body["role_status"] == "pending"
    return {"Authorization": f"Bearer {body['access_token']}"}, body["id"]


def first_chapter_id(client):
    courses = client.get("/courses", params={"class_grade": 8, "board": "Maharashtra SSC"}).json()
    return client.get(f"/courses/{courses['items'][0]['id']}").json()["chapters"][0]["id"]


def lesson_payload(chapter_id, title="Approval payload"):
    return {"chapter_id": chapter_id, "title_en": title,
            "title_hi": "स्वीकृति", "title_mr": "मान्यता", "body_en": "body"}


def upload(client, headers, title="Pending teacher notes"):
    r = client.post("/materials", data={
        "title": title, "type": "notes", "class_grade": 8,
        "board": "Maharashtra SSC", "subject_name": "Science", "lang": "en",
        "visibility": "public", "source_of_content": "test fixture"},
        files={"file": ("a.pdf", PDF, "application/pdf")}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"], r.json()["status"]


def test_self_registered_teacher_starts_pending_and_is_powerless(client):
    h, _ = register_teacher(client, "newteacher@x.in")

    me = client.get("/auth/me", headers=h).json()
    assert me["role"] == "teacher" and me["role_status"] == "pending"

    # Reading is open to everyone, so browsing still works.
    assert client.get("/courses", headers=h).status_code == 200
    chapter_id = first_chapter_id(client)

    # Every endpoint whose allowed roles include `teacher` refuses them with a
    # reason that explains the approval — not "Requires role: teacher", which
    # would be untrue (they *are* a teacher; they're just not approved).
    teacher_powers = [
        client.post("/lessons", json=lesson_payload(chapter_id), headers=h),
        client.post("/lessons/1/questions", json={"prompt_en": "q", "prompt_hi": "q",
                                                  "prompt_mr": "q"}, headers=h),
        client.post("/progress/batches", json={"name": "Section A"}, headers=h),
        client.post("/materials/1/review", data={"decision": "approved"}, headers=h),
        client.post("/doubts/1/reply", json={"body": "answer"}, headers=h),
        client.get("/teacher/students", headers=h),
        client.get("/teacher/overview", headers=h),
        client.get("/progress/teacher/overview", headers=h),
        client.get("/materials/pending", headers=h),
    ]
    for r in teacher_powers:
        assert r.status_code == 403, f"{r.request.method} {r.url} -> {r.status_code}"
        assert r.json()["detail"] == "Account pending approval", r.text

    # Admin-only endpoints never admit the teacher role, so the role test
    # fails first — that is the accurate reason and it must not change.
    announce = client.post("/school/announce", params={"title": "x"}, headers=h)
    assert announce.status_code == 403
    assert announce.json()["detail"] == "Requires role: platform_admin, school_admin"

    # And a submit is not merely blocked by route dependencies: the inline
    # role checks are approval-aware too.
    student = login(client, "student1@gramshiksha.in", "Learn@1234")
    assert client.post("/doubts", json={"text": "Why is the sky blue?"},
                       headers=student).status_code == 201
    doubt_id = client.get("/doubts", headers=student).json()[0]["id"]
    assert client.post(f"/doubts/{doubt_id}/resolve", headers=h).status_code == 403

    material_id, _ = upload(client, student, title="Student upload")
    assert client.delete(f"/materials/{material_id}", headers=h).status_code == 403


def test_pending_teacher_upload_goes_through_review(client):
    pending, _ = register_teacher(client, "uploader@x.in")

    # Contribute freely — but as a student's upload would: never auto-publish.
    material_id, status = upload(client, pending)
    assert status == "pending", "an unapproved teacher must not self-publish"

    # The platform admin sees it in the moderation queue...
    admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    queue = [m["id"] for m in client.get("/materials/pending", headers=admin).json()]
    assert material_id in queue
    # ...and the uploader cannot approve their own file either.
    r = client.post(f"/materials/{material_id}/review",
                    data={"decision": "approved"}, headers=pending)
    assert r.status_code == 403 and r.json()["detail"] == "Account pending approval"


def test_admin_approval_grants_teacher_powers(client):
    pending, pending_id = register_teacher(client, "promoted@x.in")
    admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    chapter_id = first_chapter_id(client)

    assert client.post("/lessons", json=lesson_payload(chapter_id),
                       headers=pending).status_code == 403

    # Approve through the production mount, so the /api twin is exercised too.
    r = client.post(f"/api/admin/users/{pending_id}/approve", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "id": pending_id, "email": "promoted@x.in",
                        "role": "teacher", "role_status": "active"}

    assert client.get("/auth/me", headers=pending).json()["role_status"] == "active"
    assert client.post("/lessons", json=lesson_payload(chapter_id),
                       headers=pending).status_code == 201
    assert client.post("/progress/batches", json={"name": "Approved batch"},
                       headers=pending).status_code == 201
    assert client.get("/teacher/overview", headers=pending).status_code == 200
    # An approved teacher's own upload publishes immediately again.
    _, status = upload(client, pending, title="Approved teacher notes")
    assert status == "approved"

    # Approval is idempotent.
    assert client.post(f"/admin/users/{pending_id}/approve",
                       headers=admin).status_code == 200


def test_approve_endpoint_is_platform_admin_only(client):
    pending, pending_id = register_teacher(client, "gated@x.in")
    teacher = login(client, "teacher1@gramshiksha.in", "Teach@1234")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")

    assert client.post(f"/admin/users/{pending_id}/approve",
                       headers=student).status_code == 403
    # Even an approved teacher may not promote someone.
    assert client.post(f"/admin/users/{pending_id}/approve",
                       headers=teacher).status_code == 403
    assert client.post(f"/admin/users/{pending_id}/approve").status_code == 401
    assert client.post("/admin/users/999999/approve",
                       headers=login(client, "admin@gramshiksha.in",
                                     "Admin@1234")).status_code == 404

    # The listing shows the flag so an admin can find who to approve.
    rows = client.get("/admin/users", params={"role": "teacher"},
                      headers=login(client, "admin@gramshiksha.in", "Admin@1234")).json()
    mine = [u for u in rows if u["id"] == pending_id]
    assert mine and mine[0]["role_status"] == "pending"


def test_suspension_withdraws_powers_and_is_reversible(client):
    """Approval must not be a permanent grant: an admin can withdraw it,
    the account survives with its coursework, and approve is the way back.
    """
    teacher, teacher_id = register_teacher(client, "revoked@x.in")
    admin = login(client, "admin@gramshiksha.in", "Admin@1234")
    chapter_id = first_chapter_id(client)

    # Approve, and confirm the powers actually work first...
    assert client.post(f"/admin/users/{teacher_id}/approve",
                       headers=admin).status_code == 200
    assert client.post("/lessons", json=lesson_payload(chapter_id, "Revocable lesson"),
                       headers=teacher).status_code == 201

    # ...then withdraw the approval, through the /api mount so the twin
    # route is exercised too.
    r = client.post(f"/api/admin/users/{teacher_id}/suspend", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "id": teacher_id, "email": "revoked@x.in",
                        "role": "teacher", "role_status": "suspended"}

    # Suspended is its own distinct reason — not "Account pending approval",
    # which would send the user looking for an approval that already happened.
    for r in (client.post("/lessons", json=lesson_payload(chapter_id, "Suspended lesson"),
                          headers=teacher),
              client.get("/teacher/overview", headers=teacher),
              client.get("/materials/pending", headers=teacher)):
        assert r.status_code == 403, f"{r.request.method} {r.url} -> {r.status_code}"
        assert r.json()["detail"] == "Account suspended", r.text

    # The account itself survives: still logged in, still readable...
    assert client.get("/auth/me", headers=teacher).json()["role_status"] == "suspended"
    assert client.get("/courses", headers=teacher).status_code == 200
    # ...but new uploads fall back to the review queue, like an unapproved
    # teacher's — a suspended account must not be able to publish.
    _, status = upload(client, teacher, title="Suspended teacher notes")
    assert status == "pending"

    # Idempotent in both directions; approve restores every power.
    assert client.post(f"/admin/users/{teacher_id}/suspend",
                       headers=admin).status_code == 200
    assert client.post(f"/admin/users/{teacher_id}/approve",
                       headers=admin).status_code == 200
    assert client.get("/teacher/overview", headers=teacher).status_code == 200


def test_status_changes_are_admin_only_and_never_self_targeted(client):
    """Only a platform admin may change approval status, and nobody may
    change their own: the sole admin suspending themselves would strand the
    platform with nobody able to approve anything.
    """
    _, pending_id = register_teacher(client, "gated2@x.in")
    student = login(client, "student1@gramshiksha.in", "Learn@1234")
    admin = login(client, "admin@gramshiksha.in", "Admin@1234")

    assert client.post(f"/admin/users/{pending_id}/suspend",
                       headers=student).status_code == 403
    assert client.post(f"/admin/users/{pending_id}/suspend").status_code == 401
    assert client.post("/admin/users/999999/suspend", headers=admin).status_code == 404

    admin_id = client.get("/auth/me", headers=admin).json()["id"]
    for action in ("suspend", "approve"):
        r = client.post(f"/admin/users/{admin_id}/{action}", headers=admin)
        assert r.status_code == 400, f"{action}: {r.status_code}"
        assert r.json()["detail"] == "Cannot change your own approval status"
    # The refused self-suspend really did nothing.
    assert client.get("/auth/me", headers=admin).json()["role_status"] == "active"
