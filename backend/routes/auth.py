"""
Authentication Routes
User registration and login endpoints
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import uuid
import logging

from backend.models.log_models import UserCreate, UserLogin, TokenResponse, UserResponse
from backend.services.db_service import db_service
from backend.services.auth_service import auth_service
from backend.config import AUTH_ENABLED

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(user: UserCreate):
    """
    Register new user
    
    Creates user account with hashed password and returns JWT token
    """
    if not AUTH_ENABLED:
        raise HTTPException(
            status_code=400,
            detail="Registration disabled when AUTH_ENABLED=False. Use demo user."
        )
    
    try:
        # Check if user already exists
        existing_user = await db_service.get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password
        password_hash = auth_service.hash_password(user.password)
        
        # Create user document
        user_id = f"user-{uuid.uuid4().hex[:16]}"
        user_data = {
            "id": user_id,
            "email": user.email,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Save to database
        result = await db_service.create_user(user_data)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create user")
        
        # Generate JWT token
        access_token = auth_service.create_access_token(user_id, user.email)
        
        # Return token and user info
        user_response = UserResponse(
            id=user_id,
            email=user.email,
            created_at=user_data["created_at"]
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """
    Login existing user
    
    Validates credentials and returns JWT token
    """
    if not AUTH_ENABLED:
        # Return demo user token
        demo_user = auth_service.get_demo_user()
        demo_token = auth_service.create_access_token(demo_user.id, demo_user.email)
        
        return TokenResponse(
            access_token=demo_token,
            token_type="bearer",
            user=demo_user
        )
    
    try:
        # Get user by email
        user = await db_service.get_user_by_email(credentials.email)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Verify password
        if not auth_service.verify_password(credentials.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Generate JWT token
        access_token = auth_service.create_access_token(user["id"], user["email"])
        
        # Return token and user info
        user_response = UserResponse(
            id=user["id"],
            email=user["email"],
            created_at=user["created_at"]
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=user_response
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error logging in user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/profile", response_model=UserResponse)
async def update_profile(profile_data: dict):
    """
    Update user profile and notification settings
    """
    try:
        user_id = profile_data.get("id")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
            
        update_fields = {}
        if "name" in profile_data:
            update_fields["name"] = profile_data["name"]
        if "email" in profile_data:
            update_fields["email"] = profile_data["email"]
        if "notifications" in profile_data:
            update_fields["notifications"] = profile_data["notifications"]
            
        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")
            
        success = await db_service.update_user(user_id, update_fields)
        if not success:
            raise HTTPException(status_code=404, detail="User not found or update failed")
            
        # Get updated user
        updated_user = await db_service.get_user_by_id(user_id)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found after update")
            
        return UserResponse(
            id=updated_user["id"],
            email=updated_user["email"],
            created_at=updated_user["created_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))
