from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google.oauth2 import id_token
from google.auth.transport import requests
from app.core.config import settings
from app.core.security import create_access_token, verify_token
from app.core.database import get_db
from app.models.models import User
from app.schemas.schemas import Token, TokenData, UserCreate, User as UserSchema
import logging

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check query params if not found in headers
    if not token:
        token = request.query_params.get("token")
        
    if not token:
        raise credentials_exception
        
    user_id = verify_token(token)
    if user_id is None:
        raise credentials_exception
    
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

@router.post("/guest", response_model=Token)
async def guest_auth(db: AsyncSession = Depends(get_db)):
    """
    Create or get a guest user (Bruce Wayne) and return an access token.
    """
    email = "bruce.wayne@waynecorp.com"
    full_name = "Bruce Wayne"
    avatar_url = "https://images.unsplash.com/photo-1531297484001-80022131f5a1?q=80&w=200&auto=format&fit=crop"

    try:
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

            # Prepopulate with Dark Knight Rises theme data
            from app.models.models import UserPersonality, ConversationSummary, ChatHistory
            
            personality = UserPersonality(
                user_id=user.id,
                traits={
                    "Vigilance Status": "EXTREME",
                    "Gotham Sector Lock": "SECTOR_04_TUNNELS",
                    "Threat Analysis": "BANE_CRITICAL",
                    "Combat Readiness": "98.4%",
                    "Tactical Plan": "OPERATION_RISE"
                },
                preferences={
                    "Batcomputer Node": "MAIN_CAVE_UPLINK",
                    "Signal Encryption": "MIL_SPEC_DEC_v9",
                    "Bane Wave Frequency": "144.8 MHz"
                }
            )
            db.add(personality)
            
            summary = ConversationSummary(
                user_id=user.id,
                summary="Bane has seized control of Gotham City, isolating it with explosives on the bridges. The city is held hostage by a decaying fusion reactor converted into a neutron bomb. Selina Kyle's tracking confirms Bane is operating from the sewers beneath Wayne Enterprises. Awaiting coordinated command inputs.",
                last_chat_id=2
            )
            db.add(summary)
            
            welcome_1 = ChatHistory(
                user_id=user.id,
                role="user",
                content="Batcomputer, status report on Bane's fusion core."
            )
            welcome_2 = ChatHistory(
                user_id=user.id,
                role="assistant",
                content="GOTH-OS // WARNING: FUSION REACTOR DECAY IN PROGRESS. The core is currently mounted on a mobile truck shifting routes through Gotham streets to avoid targeting. Core stabilization is impossible without Dr. Pavel. Remaining time: 48 hours. The Batwing is fully armed and positioned at the downtown hangar. Ready to launch."
            )
            db.add(welcome_1)
            db.add(welcome_2)
            
            await db.commit()
            await db.refresh(user)

        # Create access token
        access_token = create_access_token(subject=user.id)
        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        logging.error(f"Guest Auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Guest Authentication failed")

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

@router.get("/me", response_model=UserSchema)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
