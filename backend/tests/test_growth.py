"""Growth surface: referral loop, public money config, RSS feed.

Contract under test: registration with a valid invite code credits the
inviter (visible in /growth/me and /growth/leaderboard); garbage codes are
ignored, never rejected; /growth/config exposes only public values with
every money slot off by default; /feed.xml is valid RSS.
"""
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    with TestClient(app) as c:
        yield c


def register(client, email, ref=""):
    r = client.post("/auth/register", json={
        "email": email, "name": "Growth User", "password": "Growth@123",
        "role": "student", "ref": ref})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["id"]


def test_config_defaults_have_every_money_slot_off(client):
    for path in ("/growth/config", "/api/growth/config"):
        cfg = client.get(path).json()
        assert cfg["referral_enabled"] is True
        assert cfg["site_url"].startswith("https://")
        assert cfg["ads"] is None
        assert cfg["donate"] is None
        assert cfg["affiliates"] == []
        assert cfg["sponsor"] is None
        assert cfg["premium_url"] is None
    # Literal calls so the route-coverage canary (AST-based) sees them.
    assert client.get("/growth/config").status_code == 200
    assert client.get("/api/growth/config").status_code == 200


def test_money_links_reject_invalid_or_unsafe_values(client, monkeypatch):
    monkeypatch.setattr(settings, "donate_upi", "gramshiksha@upi")
    monkeypatch.setattr(settings, "donate_url", "https://example.org/donate")
    monkeypatch.setattr(settings, "premium_url", "https://example.org/premium")
    monkeypatch.setattr(settings, "sponsor_text", "A local bookshop")
    monkeypatch.setattr(settings, "sponsor_url", "https://example.org/sponsor")
    cfg = client.get("/growth/config").json()
    assert cfg["donate"] == {"upi": "gramshiksha@upi", "url": "https://example.org/donate"}
    assert cfg["premium_url"] == "https://example.org/premium"
    assert cfg["sponsor"]["url"] == "https://example.org/sponsor"

    # A malformed UPI id is hidden, but a safe donation URL still works.
    monkeypatch.setattr(settings, "donate_upi", "not a upi id")
    cfg = client.get("/growth/config").json()
    assert cfg["donate"] == {"upi": None, "url": "https://example.org/donate"}

    # Non-HTTPS and javascript: URLs never reach the page.
    monkeypatch.setattr(settings, "donate_url", "javascript:alert(1)")
    monkeypatch.setattr(settings, "premium_url", "http://example.org/premium")
    monkeypatch.setattr(settings, "sponsor_url", "javascript:alert(1)")
    cfg = client.get("/growth/config").json()
    assert cfg["donate"] is None
    assert cfg["premium_url"] is None
    assert cfg["sponsor"] is None


def test_referral_loop_credits_inviter_and_lists_leaderboard(client):
    h_alice, _ = register(client, "alice-growth@x.in")
    my_code = client.get("/growth/me", headers=h_alice).json()
    assert my_code["referral_code"].startswith("GS")
    assert my_code["referrals"] == 0

    register(client, "bob-growth@x.in", ref=my_code["referral_code"])
    assert client.get("/growth/me", headers=h_alice).json()["referrals"] == 1

    board = client.get("/growth/leaderboard").json()
    assert any(row["name"] == "Growth User" and row["referrals"] == 1 for row in board)
    assert all(set(row) == {"name", "referrals"} for row in board)


def test_garbage_ref_code_is_ignored_not_rejected(client):
    h, _ = register(client, "carol-growth@x.in", ref="NOT-A-CODE")
    assert client.get("/growth/me", headers=h).json()["referrals"] == 0


def test_feed_is_valid_rss(client):
    r = client.get("/feed.xml")
    assert r.status_code == 200
    assert "rss" in r.headers["content-type"]
    root = ET.fromstring(r.text)
    assert root.tag == "rss"
    assert root.find("channel") is not None
    r2 = client.get("/api/feed.xml")
    assert r2.status_code == 200


def test_ads_txt_stays_hidden_until_a_valid_publisher_id_exists(client, monkeypatch):
    monkeypatch.setattr(settings, "adsense_client", "")
    hidden = client.get("/ads.txt")
    assert hidden.status_code == 404
    assert hidden.headers["cache-control"] == "no-store"

    monkeypatch.setattr(settings, "adsense_client", "not-a-publisher-id")
    assert client.get("/ads.txt").status_code == 404

    monkeypatch.setattr(settings, "adsense_client", "ca-pub-1234567890123456")
    for path in ("/ads.txt", "/api/ads.txt"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.text == "google.com, pub-1234567890123456, DIRECT, f08c47fec0942fa0\n"
        assert r.headers["content-type"].startswith("text/plain")
    # Literal calls so the route-coverage canary sees the endpoint.
    assert client.get("/ads.txt").status_code == 200
