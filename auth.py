from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from database import get_db
from db_models import User

# Load environment variables
load_dotenv()

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT security scheme
security = HTTPBearer()

class AuthService:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                return None
            return payload
        except JWTError:
            return None

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """Authenticate a user by email and password."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get a user by email."""
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def create_user(db: Session, email: str, password: str, **kwargs) -> User:
        """Create a new user."""
        hashed_password = AuthService.get_password_hash(password)
        user = User(
            email=email,
            password_hash=hashed_password,
            **kwargs
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

# Dependency to get current user
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = AuthService.verify_token(token)
    if payload is None:
        raise credentials_exception
    
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    
    user = AuthService.get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception
    
    return user

# Dependency to get current active user
async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Dependency to get current active user with platform status check for agents
async def get_current_active_user_with_platform_check(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """Get the current active user with platform status validation for agents."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # For agents, check platform status
    if current_user.role == "agent":
        from db_models import AgentProfile
        agent_profile = db.query(AgentProfile).filter(
            AgentProfile.user_id == current_user.user_id
        ).first()
        
        if agent_profile and agent_profile.platform_status:
            # Only allow approved, verified, or premium agents to access the platform
            allowed_statuses = ["approved", "verified", "premium"]
            if agent_profile.platform_status not in allowed_statuses:
                status_messages = {
                    "pending": "Your agent profile is pending admin approval",
                    "denied": "Your agent application has been denied. Please contact support",
                    "suspended": "Your agent account has been suspended. Please contact support"
                }
                message = status_messages.get(
                    agent_profile.platform_status, 
                    f"Agent access restricted. Platform status: {agent_profile.platform_status}"
                )
                raise HTTPException(
                    status_code=403, 
                    detail=message
                )
    
    return current_user

# Role-based authorization decorators
class RoleChecker:
    def __init__(self, allowed_roles: List[str], check_platform_status: bool = True):
        self.allowed_roles = allowed_roles
        self.check_platform_status = check_platform_status
    
    def __call__(self, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        
        # Check platform status for agents if enabled
        if self.check_platform_status and current_user.role == "agent":
            from db_models import AgentProfile
            agent_profile = db.query(AgentProfile).filter(
                AgentProfile.user_id == current_user.user_id
            ).first()
            
            if agent_profile and agent_profile.platform_status:
                allowed_statuses = ["approved", "verified", "premium"]
                if agent_profile.platform_status not in allowed_statuses:
                    status_messages = {
                        "pending": "Your agent profile is pending admin approval",
                        "denied": "Your agent application has been denied. Please contact support",
                        "suspended": "Your agent account has been suspended. Please contact support"
                    }
                    message = status_messages.get(
                        agent_profile.platform_status, 
                        f"Agent access restricted. Platform status: {agent_profile.platform_status}"
                    )
                    raise HTTPException(
                        status_code=403, 
                        detail=message
                    )
        
        return current_user

# Specific role dependencies
require_admin = RoleChecker(["admin"])
require_agent_or_admin = RoleChecker(["agent", "admin"])
require_customer_or_above = RoleChecker(["customer", "client", "agent", "admin"])
require_client_or_above = RoleChecker(["client", "agent", "admin"])

# Optional authentication (for public endpoints that can benefit from user context)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get the current user if authenticated, otherwise return None."""
    if credentials is None:
        return None
    
    try:
        token = credentials.credentials
        payload = AuthService.verify_token(token)
        if payload is None:
            return None
        
        email: str = payload.get("sub")
        if email is None:
            return None
        
        user = AuthService.get_user_by_email(db, email=email)
        return user
    except:
        return None

# Enhanced Authorization Functions

def can_manage_property(current_user: User, property_owner_id: Optional[str] = None) -> bool:
    """Check if user can manage a specific property."""
    if current_user.role == "admin":
        return True
    if current_user.role == "agent":
        # Agents can manage their own properties or client properties they represent
        return True
    return False

def can_manage_client(current_user: User, client_id: str = None) -> bool:
    """Check if user can manage a specific client."""
    if current_user.role == "admin":
        return True
    if current_user.role == "agent":
        # Agents can manage their represented clients
        return True
    return False

def can_access_listings(current_user: Optional[User] = None) -> bool:
    """Check if user can access property listings (public access allowed)."""
    return True  # Public access to listings

def requires_auth_for_action(action: str) -> bool:
    """Check if a specific action requires authentication."""
    auth_required_actions = [
        "save_property", "contact_agent", "request_representation", 
        "create_property", "manage_images", "manage_clients"
    ]
    return action in auth_required_actions

class PermissionChecker:
    """Enhanced permission checker for specific actions."""
    
    def __init__(self, required_permissions: List[str]):
        self.required_permissions = required_permissions
    
    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        user_permissions = self.get_user_permissions(current_user)
        
        for permission in self.required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required"
                )
        return current_user
    
    def get_user_permissions(self, user: User) -> List[str]:
        """Get all permissions for a user based on their role."""
        permissions = []
        
        if user.role == "admin":
            permissions = [
                "manage_all_properties", "manage_all_users", "manage_all_agents",
                "create_property", "update_property", "delete_property",
                "manage_images", "manage_clients", "manage_listings",
                "view_all_analytics", "manage_system_settings"
            ]
        elif user.role == "agent":
            permissions = [
                "create_property", "update_own_property", "manage_own_images",
                "manage_own_clients", "create_listings", "manage_own_listings",
                "contact_clients", "view_client_interests", "respond_to_requests"
            ]
        elif user.role in ["client", "customer"]:
            permissions = [
                "view_properties", "save_properties", "contact_agents",
                "request_representation", "view_own_interests", "manage_own_profile"
            ]
        
        return permissions

# Specific permission dependencies
require_property_management = PermissionChecker(["create_property", "update_property"])
require_client_management = PermissionChecker(["manage_own_clients"])
require_listing_management = PermissionChecker(["create_listings", "manage_own_listings"])

# Role-based checks for specific actions
def require_agent_for_property_action():
    """Decorator to require agent role for property-related actions."""
    def decorator(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in ["agent", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only agents and admins can perform this action"
            )
        return current_user
    return decorator

def require_auth_for_client_action():
    """Decorator to require authentication for client actions."""
    def decorator(current_user: User = Depends(get_current_active_user)):
        if current_user.role not in ["customer", "client", "agent", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Authentication required for this action"
            )
        return current_user
    return decorator

# Agent-specific authorization
class AgentPermissionChecker:
    """Check agent-specific permissions."""
    
    @staticmethod
    def can_manage_client_relationship(agent: User, client_id: str, db) -> bool:
        """Check if agent can manage a specific client relationship."""
        if agent.role == "admin":
            return True
        
        if agent.role != "agent":
            return False
        
        # Check if agent has active relationship with client
        from db_models import ClientAgentRelationship
        relationship = db.query(ClientAgentRelationship).filter(
            ClientAgentRelationship.agent_id == agent.user_id,
            ClientAgentRelationship.client_id == client_id,
            ClientAgentRelationship.status == "active"
        ).first()
        
        return relationship is not None
    
    @staticmethod
    def can_access_property_for_client(agent: User, property_id: str, client_id: str, db) -> bool:
        """Check if agent can access property information for a specific client."""
        if agent.role == "admin":
            return True
            
        if agent.role != "agent":
            return False
        
        # Agent can access if they represent the client
        return AgentPermissionChecker.can_manage_client_relationship(agent, client_id, db) 