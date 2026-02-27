"""Authentication API - Register, Login, Profile"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.database import get_db
from backend.schemas.schemas import UserCreate, UserLogin, UserResponse, Token
from backend.services.user_service import UserService
from backend.core.security import create_access_token, get_current_user
from backend.models.models import User

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    existing = await UserService.get_user_by_email(db, user_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    user = await UserService.create_user(db, user_data.name, user_data.email, user_data.password)
    token = create_access_token({"sub": str(user.user_id)})
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    user = await UserService.authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token({"sub": str(user.user_id)})
    return Token(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    """Get current authenticated user's profile."""
    return UserResponse.model_validate(current_user)

@router.get("/test")
async def test():
    from backend.core.security import get_password_hash
    try:
        h = get_password_hash("testpassword")
        return {"status": "ok", "hash": h}
    except Exception as e:
        return {"status": "error", "detail": str(e)}