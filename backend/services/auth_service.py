"""
Authentication Service
JWT token management, password hashing, user authentication
"""

import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from backend.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEMO_USER_ID, DEMO_USER_EMAIL, AUTH_ENABLED
)
from backend.models.log_models import UserResponse

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication and JWT service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    
    @staticmethod
    def create_access_token(user_id: str, email: str) -> str:
        """Create JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        
        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None
    
    @staticmethod
    def get_demo_user() -> UserResponse:
        """Get demo user for testing"""
        return UserResponse(
            id=DEMO_USER_ID,
            email=DEMO_USER_EMAIL,
            created_at=datetime.utcnow().isoformat()
        )
    
    @staticmethod
    def extract_user_from_token(authorization: Optional[str]) -> Optional[str]:
        """
        Extract user_id from Authorization header
        
        If AUTH_ENABLED = False, return demo user ID
        If AUTH_ENABLED = True, validate token and return user_id
        """
        if not AUTH_ENABLED:
            return DEMO_USER_ID
        
        if not authorization or not authorization.startswith("Bearer "):
            return None
        
        token = authorization.replace("Bearer ", "")
        payload = AuthService.verify_token(token)
        
        if payload:
            # Support both 'sub' (standard) and 'userId' (Express backend)
            return payload.get("sub") or payload.get("userId")
        
        return None


# Singleton instance
auth_service = AuthService()
