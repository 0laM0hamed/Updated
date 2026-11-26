import argparse
import asyncio
import difflib
import html
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from sqlalchemy import select

from app.db import SessionLocal, engine
from app.mailer import send_email
from app.models import Item, Notification, Source, User

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def fetch_source(url: str) -> dict[str, Any]:
    result = subprocess.run(
        ["node", str(PROJECT_ROOT / "app" / "check_source.mjs"), url],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        encoding="utf-8",
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Page fetch failed.")
    return json.loads(result.stdout)


def added_lines(previous: str, current: str) -> list[str]:
    diff = difflib.unified_diff(
        previous.splitlines(),
        current.splitlines(),
        fromfile="previous",
        tofile="current",
        lineterm="",
    )
    return [
        line[1:].strip()
        for line in diff
        if line.startswith("+") and not line.startswith("+++")
    ]


def changed_lines(previous: str, current: str) -> list[str]:
    diff = difflib.unified_diff(
        previous.splitlines(),
        current.splitlines(),
        fromfile="previous",
        tofile="current",
        lineterm="",
    )
    return [
        line
        for line in diff
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    ]


def matching_new_lines(lines: list[str], keywords: str) -> list[str]:
    terms = [term.strip().casefold() for term in keywords.replace("\n", ",").split(",") if term.strip()]
    if not terms:
        return lines
    return [line for line in lines if any(term in line.casefold() for term in terms)]


def make_email(source: Source, lines: list[str]) -> tuple[str, str, str]:
    diff_text = "\n".join(
        line if line.startswith(("+", "-")) else f"+ {line}" for line in lines
    )
    subject = f"Scholarship update: {source.name}"
    text = f"New content was found on {source.name}:\n{source.url}\n\n{diff_text}"
    safe_diff = html.escape(diff_text)
    safe_url = html.escape(source.url, quote=True)
    body = (
        f"<p>New content was found on "
        f'<a href="{safe_url}">{html.escape(source.name)}</a>:</p>'
        f"<pre>{safe_diff}</pre>"
    )
    return subject, body, text


async def check_one_source(
    source: Source,
    recipient: str,
    session: Any,
    fetcher: Callable[[str], dict[str, Any]] = fetch_source,
    email_sender: Callable[..., str] = send_email,
) -> str:
    snapshot = await asyncio.to_thread(fetcher, source.url)
    current_hash = snapshot["hash"]
    current_content = snapshot["clean_text"]
    checked_at = datetime.now(timezone.utc)

    if not source.last_hash or source.last_content is None:
        source.last_hash = current_hash
        source.last_content = current_content
        source.last_checked = checked_at
        await session.commit()
        return "baseline"

    if source.last_hash == current_hash:
        source.last_checked = checked_at
        await session.commit()
        return "unchanged"

    new_lines = added_lines(source.last_content, current_content)
    keywords = source.keywords or ""
    has_keywords = any(term.strip() for term in keywords.replace("\n", ",").split(","))
    alert_lines = (
        matching_new_lines(new_lines, keywords)
        if has_keywords
        else changed_lines(source.last_content, current_content)
    )
    if alert_lines:
        subject, body, text = make_email(source, alert_lines)
        await asyncio.to_thread(email_sender, recipient, subject, body, text)
        item = Item(
            source_id=source.id,
            title=f"Update detected: {source.name}",
            link=f"{source.url}#snapshot-{current_hash}-{uuid4()}",
            content="\n".join(alert_lines),
        )
        session.add(item)
        await session.flush()
        session.add(Notification(user_id=source.user_id, item_id=item.id))
        outcome = "alerted"
    else:
        outcome = "changed_without_keyword_match"

    source.last_hash = current_hash
    source.last_content = current_content
    source.last_checked = checked_at
    await session.commit()
    return outcome


async def run_checks(user_id: UUID | None = None) -> dict[str, int]:
    counts = {
        "baseline": 0,
        "unchanged": 0,
        "alerted": 0,
        "changed_without_keyword_match": 0,
        "failed": 0,
    }

    async with SessionLocal() as session:
        statement = select(Source, User.email).join(User, Source.user_id == User.id)
        if user_id is not None:
            statement = statement.where(Source.user_id == user_id)
        sources = [
            (source.id, recipient)
            for source, recipient in (await session.execute(statement)).all()
        ]

        for source_id, recipient in sources:
            try:
                source = await session.scalar(select(Source).where(Source.id == source_id))
                if source is None:
                    continue
                outcome = await check_one_source(source, recipient, session)
                counts[outcome] += 1
                logger.info("Checked source %s: %s", source_id, outcome)
            except Exception:
                await session.rollback()
                counts["failed"] += 1
                logger.exception("Could not check source %s", source_id)

    return counts


async def main() -> None:
    parser = argparse.ArgumentParser(description="Check saved scholarship sources for changes.")
    parser.add_argument("--user-id", type=UUID, help="Only check sources belonging to this user.")
    args = parser.parse_args()
    try:
        counts = await run_checks(args.user_id)
        logger.info("Source check summary: %s", counts)
        if counts["failed"]:
            raise SystemExit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
