from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings
from app.core.security import create_access_token, verify_token
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import Token, TokenData, UserCreate
import logging

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user_id = verify_token(token)
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/google", response_model=Token)
async def google_auth(token_data: dict, db: AsyncSession = Depends(get_db)):
    """
    Verify Google ID Token and return an Axolot access token.
    """
    token = token_data.get("credential")
    if not token:
        raise HTTPException(status_code=400, detail="Missing Google credential")

    try:
        # Verify the ID token
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        email = idinfo.get("email")
        full_name = idinfo.get("name")
        avatar_url = idinfo.get("picture")

        # Check if user exists
        result = await db.execute(select(User).filter(User.email == email))
        user = result.scalars().first()

        if not user:
            # Create new user
            user = User(
                email=email,
                full_name=full_name,
                avatar_url=avatar_url
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        # Create access token
        access_token = create_access_token(subject=user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    except ValueError:
        # Invalid token
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        logging.error(f"Auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")
