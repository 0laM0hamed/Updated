from fastapi import Depends, Request, FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.models import User
from app.schemas import UserCreate, UserRead
from app.users import auth_backend, fastapi_users, optional_user

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def home():
    return RedirectResponse("/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html")

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User | None = Depends(optional_user)):
    if user is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request, "dashboard.html", {"user": user})