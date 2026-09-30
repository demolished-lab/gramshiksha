"""Growth & monetization surface: referral virality, public money config, RSS.

Revenue philosophy (see docs/GROWTH.md): every stream pays *in* — ads,
affiliates, donations, premium links, sponsorships — and every tool stays on
its free tier forever. Each money slot is config-gated: the frontend renders
it ONLY when the corresponding setting is filled, so an unconfigured slot is
invisible, never a broken box. Nothing here can charge the operator.

Referral design: the public code is derived ("GS%06d" % user id), so no code
column, no uniqueness problem, no backfill. No monetary reward is attached
(counts + leaderboard only), so farming fake accounts buys nothing.
"""
import json
import logging
import re
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, func, select

from ..config import settings
from ..db import get_session
from ..models import Course, Material, User
from ..ratelimit import rate_limit
from ..security import get_current_user

log = logging.getLogger("gramshiksha")

router = APIRouter(tags=["growth"])

_REF_RE = re.compile(r"^GS(\d{1,10})$")


def referral_code(user_id: int) -> str:
    """Public invite code for a user id. Derived, so it never collides and
    needs no storage."""
    return f"GS{user_id:06d}"


def resolve_referrer(code: str, session: Session) -> User | None:
    """The user behind an invite code, or None for garbage/unknown codes."""
    m = _REF_RE.match((code or "").strip().upper())
    if not m:
        return None
    return session.get(User, int(m.group(1)))


def affiliate_links() -> list[dict]:
    """Validated affiliate list. Only https URLs with a host survive — a
    typo'd env value degrades to an empty list, never a broken link."""
    try:
        raw = json.loads(settings.affiliate_links or "[]")
    except (json.JSONDecodeError, TypeError):
        log.warning("AFFILIATE_LINKS is not valid JSON — affiliate slot hidden")
        return []
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()[:80]
        url = str(item.get("url", "")).strip()
        parts = urlparse(url)
        if name and parts.scheme == "https" and parts.netloc:
            out.append({"name": name, "url": url})
    return out


@router.get("/growth/config")
def growth_config():
    """Public money/virality config. Values returned here are rendered into
    HTML by design (AdSense IDs, donate links) — nothing secret leaves."""
    ads = None
    if settings.adsense_client and settings.adsense_slot:
        ads = {"client": settings.adsense_client, "slot": settings.adsense_slot}
    donate = None
    if settings.donate_upi or settings.donate_url:
        donate = {"upi": settings.donate_upi or None, "url": settings.donate_url or None}
    sponsor = None
    if settings.sponsor_text and settings.sponsor_url:
        sponsor = {"text": settings.sponsor_text, "url": settings.sponsor_url}
    return {
        "site_url": settings.site_url,
        "referral_enabled": settings.referral_enabled,
        "ads": ads,
        "donate": donate,
        "affiliates": affiliate_links(),
        "sponsor": sponsor,
        "premium_url": settings.premium_url or None,
    }


@router.get("/growth/me")
def my_referrals(user=Depends(get_current_user),
                 session: Session = Depends(get_session)):
    """My invite code + how many accounts used it."""
    count = session.exec(
        select(func.count(User.id)).where(User.referred_by == user.id)
    ).one()
    return {"referral_code": referral_code(user.id), "referrals": count}


@router.get("/growth/leaderboard",
            dependencies=[Depends(rate_limit("growth.leaderboard", 60))])
def leaderboard(session: Session = Depends(get_session)):
    """Top inviters. Names only — no emails, no ids — and only accounts that
    actually referred someone appear."""
    rows = session.exec(
        select(User.referred_by, func.count(User.id))
        .where(User.referred_by.is_not(None))
        .group_by(User.referred_by)
        .order_by(func.count(User.id).desc())
        .limit(10)
    ).all()
    board = []
    for referrer_id, count in rows:
        referrer = session.get(User, referrer_id)
        if referrer:
            board.append({"name": referrer.name, "referrals": count})
    return board


@router.get("/feed.xml", dependencies=[Depends(rate_limit("growth.feed", 60))])
def rss_feed(session: Session = Depends(get_session)):
    """RSS 2.0 of the newest public content. This is the automation hook for
    the free tier of cross-posters (IFTTT/Make/Buffer): new lessons and
    materials fan out to social accounts with zero maintenance."""
    base = settings.site_url.rstrip("/")
    items: list[tuple[str, str, str, str]] = []  # title, link, desc, date

    materials = session.exec(
        select(Material)
        .where(Material.status == "approved", Material.visibility == "public")
        .order_by(Material.created_at.desc())
        .limit(20)
    ).all()
    for m in materials:
        created = m.created_at.isoformat() if m.created_at else ""
        items.append((
            f"{m.title} — Class {m.class_grade} {m.subject_name}",
            f"{base}/#/materials",
            f"{m.type} by a GramShiksha teacher ({m.board})",
            created,
        ))

    courses = session.exec(
        select(Course)
        .where(Course.published.is_(True))
        .order_by(Course.created_at.desc())
        .limit(10)
    ).all()
    for c in courses:
        created = c.created_at.isoformat() if c.created_at else ""
        items.append((
            f"{c.title_en} — Class {c.class_grade} {c.board}",
            f"{base}/#/courses",
            (c.desc_en or "")[:200],
            created,
        ))

    entries = "\n".join(
        "    <item>\n"
        f"      <title>{xml_escape(title)}</title>\n"
        f"      <link>{xml_escape(link)}</link>\n"
        f"      <description>{xml_escape(desc)}</description>\n"
        + (f"      <pubDate>{xml_escape(date)}</pubDate>\n" if date else "")
        + "    </item>"
        for title, link, desc, date in items
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{xml_escape(settings.app_name)} — new lessons &amp; materials</title>\n"
        f"    <link>{xml_escape(base)}</link>\n"
        "    <description>Latest free Class 1-12 lessons, notes and papers.</description>\n"
        f"{entries}\n"
        "  </channel>\n"
        "</rss>"
    )
    return Response(content=body, media_type="application/rss+xml")
