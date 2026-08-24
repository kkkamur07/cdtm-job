#!/usr/bin/env python3
"""Load the output of ``ingest.mjs`` into Postgres.

``ingest.mjs`` stays the single place that matches LinkedIn scrapes to the roster and renders
avatars; this script only moves its JSON into the relational schema (classes, members,
positions, educations, CA details) and then asks the paths context to recompute its read
model over what was just written. The two steps are separate because they belong to two
bounded contexts: members owns the rows, paths owns the verdict about them.

Usage (from the repo root, with DATABASE_URL set or backend/core/.env present)::

    uv run python scripts/platform/load_community.py \
        --index frontend/public/data/index.json \
        --profiles frontend/public/profiles \
        [--avatar-base https://<project>.supabase.co/storage/v1/object/public/avatars] \
        [--emails emails.csv]   # slug,email  (binds Workspace accounts to members)
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from _bootstrap import ensure_repo_on_path

ensure_repo_on_path()

from backend.core.cache import clear_all  # noqa: E402
from backend.members.application.commands import ClassImport, MemberImport  # noqa: E402
from backend.members.application.import_service import ImportService  # noqa: E402
from backend.members.domain import CaDetail, Education, Position  # noqa: E402
from backend.members.infrastructure.members_repository import SqlMemberRepository  # noqa: E402
from backend.paths.application.path_service import PathService  # noqa: E402
from backend.paths.infrastructure.career_history import SqlCareerHistorySource  # noqa: E402
from backend.paths.infrastructure.member_cards import SqlMemberCards  # noqa: E402
from backend.paths.infrastructure.paths_classifier import compute_member_path  # noqa: E402
from backend.paths.infrastructure.paths_repository import SqlPathRepository  # noqa: E402
from infrastructure.db import get_session_factory  # noqa: E402


def _month(value: str | None) -> date | None:
    if not value:
        return None
    try:
        y, m = value.split("-")[:2]
        return date(int(y), int(m), 1)
    except (ValueError, AttributeError):
        try:
            return date(int(value[:4]), 1, 1)
        except ValueError:
            return None


def _avatar(url: str | None, base: str | None) -> str | None:
    if not url:
        return None
    if base and url.startswith("/avatars/"):
        return base.rstrip("/") + url[len("/avatars") :]
    return url


def _member_import(
    tile: dict, profile: dict | None, avatar_base: str | None, synced_at: datetime
) -> MemberImport:
    p = profile or {}
    avatar = tile.get("avatar") or {}
    positions = [
        Position(
            title=x.get("title"),
            company=x.get("company"),
            company_url=x.get("companyUrl"),
            description=x.get("description"),
            location=x.get("location"),
            start_date=_month(x.get("start")),
            end_date=_month(x.get("end")),
            date_range=x.get("dateRange"),
            is_current=bool(x.get("current")),
            sort_order=i,
        )
        for i, x in enumerate(p.get("positions") or [])
    ]
    educations = [
        Education(
            school=s.get("school"),
            degree=s.get("degree"),
            date_range=s.get("dateRange"),
            sort_order=i,
        )
        for i, s in enumerate(p.get("schools") or [])
    ]
    ca_raw = p.get("ca")
    ca = (
        CaDetail(
            alumni=bool(ca_raw.get("alumni")),
            about=ca_raw.get("about"),
            responsibilities=list(ca_raw.get("responsibilities") or []),
            research_fields=list(ca_raw.get("researchFields") or []),
            email=ca_raw.get("email"),
        )
        if ca_raw
        else None
    )
    company_info = p.get("company")
    if company_info:
        company_info = {
            "name": company_info.get("name"),
            "tagline": company_info.get("tagline"),
            "description": company_info.get("description"),
            "industry": company_info.get("industry"),
            "website": company_info.get("website"),
            "linkedin_url": company_info.get("linkedInUrl"),
            "employee_count": company_info.get("employeeCount"),
            "founded_year": company_info.get("foundedYear"),
            "location": company_info.get("location"),
            "specialities": list(company_info.get("specialities") or []),
        }
    return MemberImport(
        slug=tile["id"],
        roster_person_id=tile.get("personId"),
        name=tile["name"],
        first_name=tile.get("firstName"),
        last_name=tile.get("lastName"),
        roster_name=p.get("rosterName"),
        email=(ca.email if ca and ca.email and ca.email.endswith("@cdtm.com") else None),
        headline=tile.get("headline"),
        summary=p.get("summary"),
        location=tile.get("location"),
        linkedin_url=tile.get("linkedInUrl"),
        avatar_sm_url=_avatar(avatar.get("sm"), avatar_base),
        avatar_lg_url=_avatar(avatar.get("lg"), avatar_base),
        avatar_blur=avatar.get("blur"),
        class_ids=[c["id"] for c in tile.get("classes") or []],
        class_label=tile.get("classLabel"),
        major=tile.get("major"),
        roles=list(tile.get("roles") or []),
        is_ca=bool(tile.get("isCA")),
        ca_alumni=tile.get("caAlumni"),
        matched=bool(tile.get("matched")),
        match_method=tile.get("matchMethod"),
        needs_review=bool(tile.get("needsReview")),
        current_company=tile.get("company")
        or (positions[0].company if positions and positions[0].is_current else None),
        current_title=tile.get("title")
        or (positions[0].title if positions and positions[0].is_current else None),
        skills=list(p.get("skills") or []),
        languages=list(p.get("languages") or []),
        company_info=company_info,
        ca=ca,
        positions=positions,
        educations=educations,
        linkedin_synced_at=synced_at,
    )


async def run(
    index_path: Path, profiles_dir: Path, avatar_base: str | None, emails_csv: Path | None
) -> int:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    synced_at = (
        datetime.fromisoformat(index["generatedAt"].replace("Z", "+00:00"))
        if index.get("generatedAt")
        else datetime.now(UTC)
    )
    classes = [
        ClassImport(
            id=c["id"],
            label=c["label"],
            season=c.get("season"),
            year=c["year"],
            location=c.get("location"),
        )
        for c in index.get("classes", [])
    ]
    tiles = index["members"]

    async with get_session_factory()() as session:
        service = ImportService(SqlMemberRepository(session))
        print(f"classes: {await service.import_classes(classes)} upserted")
        done = 0
        for tile in tiles:
            profile_file = profiles_dir / f"{tile['id']}.json"
            profile = (
                json.loads(profile_file.read_text(encoding="utf-8"))
                if profile_file.exists()
                else None
            )
            await service.import_member(_member_import(tile, profile, avatar_base, synced_at))
            done += 1
            if done % 100 == 0:
                print(f"members: {done}/{len(tiles)}")
        print(f"members: {done}/{len(tiles)} upserted")
        if emails_csv:
            with emails_csv.open(encoding="utf-8", newline="") as fh:
                pairs = {
                    row["slug"].strip(): row["email"].strip()
                    for row in csv.DictReader(fh)
                    if row.get("slug") and row.get("email")
                }
            print(f"emails: {await service.bind_emails(pairs)}/{len(pairs)} bound")

        # Paths is a read model over the rows just written, so it is recomputed here rather
        # than member by member during the import: the classifier's keyword tables change
        # more often than the scrape does, and a full pass is the only honest answer after
        # they do.
        paths = PathService(
            SqlPathRepository(session),
            SqlMemberCards(session),
            SqlCareerHistorySource(session),
            compute_member_path,
        )
        print(f"paths: {await paths.recompute_all()} recomputed")
    # This process is about to exit, so the cache it just emptied is its own; the line is
    # here for the case where a load is driven from inside a running API process, and so
    # that "the loader busts the read caches" is written down where the loader is.
    clear_all()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--index", type=Path, default=Path("frontend/public/data/index.json"))
    ap.add_argument("--profiles", type=Path, default=Path("frontend/public/profiles"))
    ap.add_argument(
        "--avatar-base", default=None, help="public base URL replacing the /avatars prefix"
    )
    ap.add_argument("--emails", type=Path, default=None, help="CSV with slug,email columns")
    args = ap.parse_args()
    return asyncio.run(run(args.index, args.profiles, args.avatar_base, args.emails))


if __name__ == "__main__":
    sys.exit(main())
