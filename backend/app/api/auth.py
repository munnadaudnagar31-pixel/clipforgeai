"""ClipForge AI â€” Auth API Routes (JWT + Email/Password)

Endpoints:
  POST /api/auth/register  â€” create account, return JWT
  POST /api/auth/login     â€” JSON email/password login, return JWT
  POST /api/auth/token     â€” OAuth2 form login (Swagger UI compatible)
  GET  /api/auth/me        â€” decode JWT â†’ return user profile
"""


from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from config import settings
from database import get_db
from models.models import User

router = APIRouter()

# â”€â”€ Crypto â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# â”€â”€ Schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """JSON body login â€” used by the frontend fetch() calls."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    plan: str
    clips_used_this_month: int
    avatar_url: Optional[str] = None
    created_at: str


# â”€â”€ JWT Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE)
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exc
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exc
    return user


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        plan=user.plan,
        clips_used_this_month=user.clips_used_this_month,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Email/password registration â€” hashes password with bcrypt, returns JWT."""
    # Check duplicate
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    if len(payload.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters.")

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
        plan="free",
        clips_used_this_month=0,
        is_active=True,
    )
    db.add(user)
    await db.flush()   # assign id before commit
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE)


@router.post("/login", response_model=TokenResponse)
async def login_json(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """JSON body email/password login â€” used by frontend fetch() calls."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not pwd_context.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled.")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE)


@router.post("/token", response_model=TokenResponse)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 form login â€” used by Swagger UI /api/docs."""
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not pwd_context.verify(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    """Decode JWT from Authorization header â†’ return authenticated user profile."""
    return _user_to_response(current_user)


@router.post("/logout")
async def logout():
    """
    JWT logout is stateless â€” the client drops the token from localStorage.
    This endpoint exists so the frontend can fire a semantic logout call.
    """
    return {"message": "Logged out successfully."}

