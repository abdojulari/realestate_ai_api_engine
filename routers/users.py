from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List

from database import get_db
from schemas import UserCreate, UserResponse, UserLogin, Token, UserUpdate, Message
from auth import AuthService, get_current_active_user, require_admin, get_current_user_optional
from db_models import User
from notification_service import NotificationService

router = APIRouter(prefix="/users", tags=["users"])

@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if user already exists
    existing_user = AuthService.get_user_by_email(db, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = AuthService.create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        role=user_data.role
    )
    
    # Send welcome notification based on role
    await send_welcome_notification(user, db)
    
    return user

async def send_welcome_notification(user: User, db: Session):
    """Send role-specific welcome notification to new user."""
    
    if user.role == "agent":
        # Send agent onboarding notification with profile setup link
        title = "Welcome to Real Estate AI Engine - Complete Your Agent Profile"
        message = f"""
        <html>
        <body>
            <h2>Welcome {user.first_name}!</h2>
            <p>Thank you for joining Real Estate AI Engine as an agent. To start receiving clients and managing properties, please complete your agent profile:</p>
            
            <div style="margin: 20px 0; padding: 20px; background-color: #f8f9fa; border-radius: 8px;">
                <h3>Next Steps:</h3>
                <ol>
                    <li><strong>Complete Your Profile:</strong> 
                        <a href="https://your-frontend-domain.com/agent/profile/setup" 
                           style="color: #007bff; text-decoration: none;">
                           Click here to complete your agent profile
                        </a>
                    </li>
                    <li><strong>Add Professional Information:</strong> Specialization, experience, bio</li>
                    <li><strong>Set Up Social Media Links:</strong> Connect your professional profiles</li>
                    <li><strong>Define Service Areas:</strong> Specify cities/areas you serve</li>
                </ol>
            </div>
            
            <p><strong>Your Account Details:</strong></p>
            <ul>
                <li><strong>Email:</strong> {user.email}</li>
                <li><strong>Role:</strong> Agent</li>
                <li><strong>User ID:</strong> {user.user_id}</li>
            </ul>
            
            <p>Once your profile is complete, you'll be visible to potential clients and can start managing properties.</p>
            
            <p>If you have any questions, please don't hesitate to contact our support team.</p>
            
            <p>Best regards,<br>Real Estate AI Engine Team</p>
        </body>
        </html>
        """
        
        await NotificationService.create_notification(
            db=db,
            user_id=str(user.user_id),
            notification_type="agent_onboarding",
            title=title,
            message=message,
            data={
                "action_required": True,
                "profile_setup_url": "https://your-frontend-domain.com/agent/profile/setup",
                "setup_deadline": "30_days"
            },
            send_email=True
        )
        
    elif user.role in ["customer", "client"]:
        # Send customer welcome notification
        title = f"Welcome to Real Estate AI Engine"
        message = f"""
        <html>
        <body>
            <h2>Welcome {user.first_name}!</h2>
            <p>Thank you for joining Real Estate AI Engine. You now have access to:</p>
            
            <div style="margin: 20px 0; padding: 20px; background-color: #f8f9fa; border-radius: 8px;">
                <h3>Available Features:</h3>
                <ul>
                    <li><strong>Property Search:</strong> Advanced filters and AI-powered search</li>
                    <li><strong>Agent Discovery:</strong> Find and connect with local real estate agents</li>
                    <li><strong>Saved Searches:</strong> Get notified about new matching properties</li>
                    <li><strong>Property Interests:</strong> Express interest and get agent assistance</li>
                </ul>
            </div>
            
            <p><strong>Get Started:</strong></p>
            <ul>
                <li><a href="https://your-frontend-domain.com/properties">Browse Properties</a></li>
                <li><a href="https://your-frontend-domain.com/agents">Find an Agent</a></li>
                <li><a href="https://your-frontend-domain.com/dashboard">View Your Dashboard</a></li>
            </ul>
            
            <p>Best regards,<br>Real Estate AI Engine Team</p>
        </body>
        </html>
        """
        
        await NotificationService.create_notification(
            db=db,
            user_id=str(user.user_id),
            notification_type="customer_welcome",
            title=title,
            message=message,
            data={
                "role": user.role,
                "welcome_tour": True
            },
            send_email=True
        )
        
    elif user.role == "admin":
        # Send admin welcome notification
        title = "Admin Access Granted - Real Estate AI Engine"
        message = f"""
        <html>
        <body>
            <h2>Admin Access Granted</h2>
            <p>Hello {user.first_name},</p>
            <p>You now have administrator access to Real Estate AI Engine with full system privileges.</p>
            
            <p><strong>Admin Features:</strong></p>
            <ul>
                <li>User Management</li>
                <li>Agent Approval and Management</li>
                <li>Property Type and Amenity Management</li>
                <li>System Analytics and Reports</li>
            </ul>
            
            <p><a href="https://your-frontend-domain.com/admin">Access Admin Dashboard</a></p>
            
            <p>Best regards,<br>Real Estate AI Engine Team</p>
        </body>
        </html>
        """
        
        await NotificationService.create_notification(
            db=db,
            user_id=str(user.user_id),
            notification_type="admin_welcome",
            title=title,
            message=message,
            data={"admin_level": "full"},
            send_email=True
        )

@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return access token."""
    user = AuthService.authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token_expires = timedelta(minutes=30)  # Use a constant here
    access_token = AuthService.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current user information."""
    update_data = user_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.delete("/me", response_model=Message)
async def delete_current_user(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Deactivate current user account."""
    current_user.is_active = False
    db.commit()
    
    return {"message": "Account deactivated successfully"}

# Admin endpoints
@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    skip: int = 0,
    limit: int = 100,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get user by ID (admin only)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user by ID (admin only)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user

@router.delete("/{user_id}", response_model=Message)
async def deactivate_user(
    user_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Deactivate user by ID (admin only)."""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    db.commit()
    
    return {"message": f"User {user.email} deactivated successfully"}

@router.put("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: str,
    role: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update user role (admin only)."""
    allowed_roles = ['customer', 'client', 'agent', 'admin']
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role must be one of: {allowed_roles}"
        )
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.role = role
    db.commit()
    db.refresh(user)
    
    return user 