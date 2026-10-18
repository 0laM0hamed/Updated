import os
import uuid
from dotenv import load_dotenv
from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin, FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy
)
from app.db import get_user_db
from app.models import User

load_dotenv()
SECRET = os.environ["SECRET"]

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

cookie_transport = CookieTransport(
    cookie_name="tracker_auth", 
    cookie_max_age=3600*24*7,
    cookie_secure=False,
)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600*24*7)

auth_backend = AuthenticationBackend(
    name="cookie",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

optional_user = fastapi_users.current_user(active=True, optional=True)