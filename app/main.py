import logging
import json
import uuid
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from fastapi import Depends, Request, FastAPI
from fastapi import Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.models import Source, User
from app.schemas import UserCreate, UserRead
from app.users import auth_backend, fastapi_users, optional_user
import asyncio

from app.mailer import send_email

logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
SCHOLARSHIP_URL = (
    "https://erasmus-plus.ec.europa.eu/opportunities/individuals/"
    "students/erasmus-mundus-joint-masters"
)

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])


def validate_source_url(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Enter a valid source URL.") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "erasmus-plus.ec.europa.eu"
        or parsed.username
        or parsed.password
        or port not in (None, 443)
        or len(url) > 2000
    ):
        raise HTTPException(
            status_code=400,
            detail="Use an HTTPS Erasmus Mundus page on erasmus-plus.ec.europa.eu.",
        )
    return url.strip()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/test/check-source")
def test_check_source():
    project_root = Path(__file__).resolve().parent.parent
    try:
        process = subprocess.run(
            [
                "node",
                str(project_root / "app" / "check_source.mjs"),
                SCHOLARSHIP_URL,
            ],
            cwd=project_root,
            capture_output=True,
            check=False,
            encoding="utf-8",
            timeout=30,
        )
    except FileNotFoundError as error:
        logger.exception("Node.js is required to fetch scholarship pages.")
        raise HTTPException(status_code=503, detail="Node.js is not available on the server.") from error
    except subprocess.TimeoutExpired as error:
        logger.error("Scholarship page fetch timed out.")
        raise HTTPException(status_code=504, detail="Scholarship page fetch timed out.") from error

    if process.returncode:
        logger.error("Scholarship page fetch failed: %s", process.stderr.strip())
        raise HTTPException(status_code=502, detail="Could not fetch the scholarship page.")

    try:
        result = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        logger.exception("Scholarship fetcher returned invalid JSON.")
        raise HTTPException(status_code=502, detail="Scholarship fetcher returned invalid data.") from error

    safe_clean_text = result["clean_text"].encode("ascii", "backslashreplace").decode("ascii")
    print(f"Clean text from {result['url']}:\n{safe_clean_text}\nSHA-256: {result['hash']}")
    return result


@app.get("/")
async def home():
    return RedirectResponse("/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")


@app.get("/sources", response_class=HTMLResponse)
async def sources_page(
    request: Request,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_async_session),
):
    if user is None:
        return RedirectResponse("/login")
    sources = (
        await session.scalars(
            select(Source).where(Source.user_id == user.id).order_by(Source.created_at.desc())
        )
    ).all()
    return templates.TemplateResponse(
        request, "sources.html", {"user": user, "sources": sources}
    )


@app.post("/sources")
async def add_source(
    name: str = Form(...),
    url: str = Form(...),
    keywords: str = Form(""),
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_async_session),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    name = name.strip()
    keywords = keywords.strip()
    if not name or len(name) > 200:
        raise HTTPException(status_code=400, detail="Source name must be 1-200 characters.")
    if len(keywords) > 1000:
        raise HTTPException(status_code=400, detail="Keywords must be 1000 characters or fewer.")

    source = Source(
        user_id=user.id,
        name=name,
        url=validate_source_url(url),
        keywords=keywords,
    )
    session.add(source)
    await session.commit()
    return RedirectResponse("/sources", status_code=303)


@app.post("/sources/{source_id}/delete")
async def delete_source(
    source_id: uuid.UUID,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_async_session),
):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    source = await session.scalar(
        select(Source).where(Source.id == source_id, Source.user_id == user.id)
    )
    if source is not None:
        await session.delete(source)
        await session.commit()
    return RedirectResponse("/sources", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User | None = Depends(optional_user)):
    if user is None:
        return RedirectResponse("/login")
    email_status = request.query_params.get("email")
    return templates.TemplateResponse(
        request, "dashboard.html", {"user": user, "email_status": email_status}
    )


@app.post("/dashboard/test-email")
async def test_email(user: User | None = Depends(optional_user)):
    if user is None:
        return RedirectResponse("/login", status_code=303)
    try:
        # the Resend SDK is synchronous, so run it in a thread
        await asyncio.to_thread(
            send_email,
            user.email,
            "Test email from Topic Tracker",
            "<p>It works! Your alerts will arrive like this.</p>",
            "It works! Your alerts will arrive like this.",
        )
    except Exception:
        logger.exception("Test email to user %s failed", user.id)
        return RedirectResponse("/dashboard?email=failed", status_code=303)
    return RedirectResponse("/dashboard?email=sent", status_code=303)