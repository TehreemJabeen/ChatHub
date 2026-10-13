# rest_api.py - Complete REST API Endpoints
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends, Header, Query
from sqlalchemy import select, desc, func
from typing import Optional
from pathlib import Path
import uuid
import mimetypes
import jwt
import datetime

from db.database import (
    AsyncSessionLocal, User, Chat, ChatMember,
    Message, MessageKey, JoinRequest
)
from auth_utils2 import get_user_id_from_token
from utils import logger, validate_file_content

# ============================================================
# CONFIGURATION
# ============================================================

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
MAX_FILE_SIZE = 50 * 1024 * 1024

# ============================================================
# AUTHENTICATION
# ============================================================

async def get_current_user(authorization: str = Header(None)) -> str:
    """Extract user_id from JWT Bearer token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        user_id = get_user_id_from_token(token)
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# ============================================================
# API ROUTER
# ============================================================

router = APIRouter(prefix="/api", tags=["api"])

# ============================================================
# USER ENDPOINTS
# ===========================================================

@router.get("/users/search")
async def search_users(
    query: str = Query(..., min_length=2),
    limit: int = Query(20, le=50),
    user_id: str = Depends(get_current_user)
):
    """Search users by username or full name"""
    logger.info(f"Search users: '{query}' by {user_id}")
    
    async with AsyncSessionLocal() as session:
        search_pattern = f"%{query}%"
        
        result = await session.execute(
            select(User.user_id, User.username, User.full_name, User.email)
            .where(
                (User.username.ilike(search_pattern)) |
                (User.full_name.ilike(search_pattern))
            )
            .where(User.user_id != user_id)
            .limit(limit)
        )
        users = result.all()
        
        logger.info(f"Found {len(users)} users")
        
        return {
            "users": [
                {
                    "user_id": str(u.user_id),
                    "username": u.username,
                    "full_name": u.full_name,
                    "email": u.email
                }
                for u in users
            ]
        }

# ============================================================
# CHAT ENDPOINTS
# ============================================================

@router.get("/chats")
async def get_user_chats(user_id: str = Depends(get_current_user)):
    """Get all chats user is member of"""
    logger.info(f"Get chats: {user_id}")
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                Chat.id, Chat.name, Chat.is_group,
                Chat.is_locked, Chat.created_by, Chat.created_at,
                ChatMember.is_admin
            )
            .join(ChatMember, Chat.id == ChatMember.chat_id)
            .where(ChatMember.user_id == user_id)
            .where(Chat.is_archived == False)
            .order_by(Chat.created_at.desc())
        )
        member_chats = result.all()
        
        member_chat_list = [
            {
                "chat_id": c.id,
                "name": c.name,
                "is_group": c.is_group,
                "is_locked": c.is_locked,
                "is_admin": c.is_admin,
                "created_by": str(c.created_by),
                "created_at": c.created_at.isoformat()
            }
            for c in member_chats
        ]
        
        member_chat_ids = [c.id for c in member_chats]
        
        query = select(
            Chat.id, Chat.name, Chat.is_locked,
            Chat.created_by, Chat.created_at
        ).where(
            Chat.is_group == True,
            Chat.is_archived == False
        )
        
        if member_chat_ids:
            query = query.where(Chat.id.notin_(member_chat_ids))
        
        result = await session.execute(query.order_by(Chat.created_at.desc()))
        available_chats = result.all()
        
        available_chat_list = [
            {
                "chat_id": c.id,
                "name": c.name,
                "is_locked": c.is_locked,
                "created_by": str(c.created_by),
                "created_at": c.created_at.isoformat()
            }
            for c in available_chats
        ]
        
        return {
            "member_chats": member_chat_list,
            "available_chats": available_chat_list
        }


# ============================================================
# FILE UPLOAD
# ============================================================

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """Upload file for message attachments"""
    logger.info(f"📤 Upload: {file.filename} by {user_id}")
    
    try:
        contents = await file.read()
        file_size = len(contents)
        
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        is_valid, detected_mime, error = validate_file_content(contents, file.filename)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        ext = Path(file.filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:12]
        safe_stem = "".join(
            c for c in Path(file.filename).stem
            if c.isalnum() or c in ('-', '_')
        )[:30]
        safe_filename = f"{unique_id}_{safe_stem}{ext}"
        
        file_path = UPLOAD_DIR / safe_filename
        
        with open(file_path, "wb") as f:
            f.write(contents)
        
        logger.info(f"✅ Saved: {safe_filename} ({file_size} bytes)")
        
        return {
            "file_url": f"/uploads/{safe_filename}",
            "file_name": file.filename,
            "file_size": file_size,
            "file_type": detected_mime,
            "success": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Upload failed: {file.filename}")
        raise HTTPException(status_code=500, detail="Upload failed")

# ============================================================
# REGISTRATION
# ============================================================
# ============================================================
# DIRECT MESSAGE ENDPOINT (Optional - HTTP Alternative)
# ============================================================

from pydantic import BaseModel

# Add this Pydantic model near the top of the file (after imports)
class CreateDMRequest(BaseModel):
    target_user_id: str

@router.post("/dm")
async def create_or_get_dm(
    request: CreateDMRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create or get existing DM via REST API.
    Stores both usernames in chat name, returns partner info.
    """
    target_user_id = request.target_user_id
    
    logger.info(f"REST: Create DM {user_id} -> {target_user_id}")
    
    if user_id == target_user_id:
        raise HTTPException(status_code=400, detail="Cannot DM yourself")
    
    async with AsyncSessionLocal() as session:
        try:
            from uuid import UUID
            target_uuid = UUID(target_user_id)
            user_uuid = UUID(user_id)
            
            # Get both users' info
            current_user_result = await session.execute(
                select(User.username).where(User.user_id == user_uuid)
            )
            current_user = current_user_result.first()
            
            target_result = await session.execute(
                select(User.user_id, User.username, User.full_name, User.public_key)
                .where(User.user_id == target_uuid)
            )
            target_user = target_result.first()
            
            if not target_user or not current_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Check for existing DM
            existing = await session.execute(
                select(Chat.id, Chat.created_at, Chat.name)
                .where(Chat.is_group == False)
                .where(Chat.is_archived == False)
                .where(
                    Chat.id.in_(
                        select(ChatMember.chat_id).where(ChatMember.user_id == user_uuid)
                    )
                )
                .where(
                    Chat.id.in_(
                        select(ChatMember.chat_id).where(ChatMember.user_id == target_uuid)
                    )
                )
                .limit(1)
            )
            existing_dm = existing.first()
            
            if existing_dm:
                logger.info(f"Existing DM found: {existing_dm.id}")
                return {
                    "chat_id": existing_dm.id,
                    "is_new": False,
                    "created_at": existing_dm.created_at.isoformat(),
                    "partner": {
                        "user_id": str(target_user.user_id),
                        "username": target_user.username,
                        "full_name": target_user.full_name,
                        "public_key": target_user.public_key
                    }
                }
            
            # Create new DM with both usernames stored
            # Sort alphabetically for consistency
            usernames_sorted = sorted([current_user.username, target_user.username])
            dm_name = f"{usernames_sorted[0]}|{usernames_sorted[1]}"
            
            new_dm = Chat(
                name=dm_name,  # Store both usernames
                is_group=False,
                is_locked=True,
                created_by=str(user_id),
                created_at=datetime.datetime.utcnow(),
                is_archived=False
            )
            session.add(new_dm)
            await session.flush()
            
            session.add_all([
                ChatMember(
                    chat_id=new_dm.id,
                    user_id=user_uuid,
                    is_admin=True,
                    is_blocked=False,
                    joined_at=datetime.datetime.utcnow()
                ),
                ChatMember(
                    chat_id=new_dm.id,
                    user_id=target_uuid,
                    is_admin=True,
                    is_blocked=False,
                    joined_at=datetime.datetime.utcnow()
                )
            ])
            
            await session.commit()
            
            logger.info(f"DM created via REST: {new_dm.id} with name: {dm_name}")
            
            return {
                "chat_id": new_dm.id,
                "is_new": True,
                "created_at": new_dm.created_at.isoformat(),
                "partner": {
                    "user_id": str(target_user.user_id),
                    "username": target_user.username,
                    "full_name": target_user.full_name,
                    "public_key": target_user.public_key
                }
            }
        except HTTPException:
            raise
        except ValueError as e:
            logger.error(f"Invalid UUID: {e}")
            raise HTTPException(status_code=400, detail="Invalid user ID format")
        except Exception as e:
            await session.rollback()
            logger.exception(f"DM creation failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to create DM")
        

from uuid import UUID   # <-- FIXED

import os
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

def generate_dev_supabase_jwt(user_id: str) -> str:
    """Generate a fake Supabase JWT token for development"""
    
    if not SUPABASE_JWT_SECRET:
        raise ValueError("SUPABASE_JWT_SECRET environment variable not set")
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    payload = {
        "sub": user_id,  # Subject - the user ID
        "role": "authenticated",
        "aud": "authenticated",
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(days=30)).timestamp()),
        "email": f"{user_id}@dev.local",
        "app_metadata": {
            "provider": "email",
            "providers": ["email"]
        },
        "user_metadata": {},
        "iss": "supabase",  # Issuer (optional but good practice)
    }
    
    token = jwt.encode(payload, SUPABASE_JWT_SECRET, algorithm="HS256")
    return token

#hi
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

@router.get("/dev-generate-token")
def dev_generate_token(user_id: str):
    """Development endpoint to generate JWT tokens"""
    
    if not DEV_MODE:
        raise HTTPException(status_code=403, detail="Only available in DEV mode")
    
    # Validate UUID format
    try:
        UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    
    try:
        jwt_token = generate_dev_supabase_jwt(user_id)
        return {"jwt": jwt_token, "user_id": user_id}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def register_rest_routes(app):
    """Register all REST API routes"""
    app.include_router(router)
    print("[DEBUG] REST routes registered!")  # Add this for debugging
    
    # Debug: Print all registered routes
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  Route: {route.path}")

