# auth_utils2.py - Fixed JWT validation
import jwt
from fastapi import HTTPException
import os

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
ALGORITHM = "HS256"

def get_user_id_from_token(token: str) -> str:
    """Decode and verify JWT token, return user_id"""
    
    if not SUPABASE_JWT_SECRET:
        raise ValueError("SUPABASE_JWT_SECRET not configured")
    
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": False,  # <-- DISABLE audience validation
                "require": ["sub", "exp"]
            }
        )
        
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token missing 'sub' claim")
        
        return user_id

    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")

    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {str(e)}")

