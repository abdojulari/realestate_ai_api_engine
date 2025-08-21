from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import List, Optional

from database import get_db
from schemas import UserCreate, UserResponse, UserLogin, Token, UserUpdate, Message, PasswordChangeRequest, PasswordResetRequest
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
    
    # For agents, check platform status before allowing login
    if user.role == "agent":
        from db_models import AgentProfile
        agent_profile = db.query(AgentProfile).filter(
            AgentProfile.user_id == user.user_id
        ).first()
        
        if agent_profile and agent_profile.platform_status:
            allowed_statuses = ["approved", "verified", "premium"]
            if agent_profile.platform_status not in allowed_statuses:
                status_messages = {
                    "pending": "Your agent profile is pending admin approval. You cannot access the platform until approved.",
                    "denied": "Your agent application has been denied. Please contact support for more information.",
                    "suspended": "Your agent account has been suspended. Please contact support to resolve this issue."
                }
                message = status_messages.get(
                    agent_profile.platform_status, 
                    f"Agent access restricted. Platform status: {agent_profile.platform_status}. Please contact support."
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=message
                )
    
    access_token_expires = timedelta(minutes=60)  # Use a constant here
    access_token = AuthService.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/logout", response_model=Message)
async def logout(current_user: User = Depends(get_current_active_user)):
    """Logout current user (invalidate token on client side)."""
    # Note: JWT tokens are stateless, so actual invalidation happens on the client side
    # This endpoint serves as confirmation that the user has logged out
    return {"message": f"User {current_user.email} logged out successfully"}

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
    """Update current user information (excluding password)."""
    update_data = user_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.post("/change-password", response_model=Message)
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Change user password with current password verification."""
    # Verify current password
    if not AuthService.verify_password(password_request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    new_hashed_password = AuthService.get_password_hash(password_request.new_password)
    
    # Update password
    current_user.password_hash = new_hashed_password
    db.commit()
    
    return {"message": "Password changed successfully"}

@router.post("/request-password-reset", response_model=Message)
async def request_password_reset(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """Request a password reset link. Works for users without passwords (new users) or forgotten passwords."""
    
    # Check if user exists
    user = db.query(User).filter(User.email == reset_request.email).first()
    if not user:
        # For security, don't reveal if email exists or not
        return {"message": "If the email exists in our system, a password reset link has been sent."}
    
    # Generate a secure reset token (you might want to store this in DB with expiration)
    import secrets
    import hashlib
    from datetime import datetime, timedelta
    
    # Create a reset token (in production, store this in database with expiration)
    reset_token = secrets.token_urlsafe(32)
    
    # Use FRONTEND_BASE_URL from environment, override only if explicitly provided
    import os
    frontend_base_url = os.getenv("FRONTEND_BASE_URL")
    app_base_url = reset_request.app_base_url or frontend_base_url
    reset_link = f"{app_base_url}/reset-password?token={reset_token}&email={reset_request.email}"
    
    # Send email with reset link
    try:
        from emailer import send_email
        import asyncio
        
        # Email subject and body
        subject = "Password Reset Request"
        
        # Check if user has no password (new user) or existing user
        has_existing_password = bool(user.password_hash and user.password_hash.strip())
        
        if has_existing_password:
            body = f"""
            Hello {user.first_name or user.email},
            
            You requested to reset your password. Click the link below to set a new password:
            
            {reset_link}
            
            This link will expire in 24 hours for security reasons.
            
            If you didn't request this password reset, please ignore this email.
            
            Best regards,
            Real Estate Platform Team
            """
        else:
            body = f"""
            Hello {user.first_name or user.email},
            
            Welcome! Your account has been created. Click the link below to set your password:
            
            {reset_link}
            
            This link will expire in 24 hours for security reasons.
            
            Best regards,
            Real Estate Platform Team
            """
        
        # Send the email asynchronously
        asyncio.create_task(send_email(
            to_email=user.email,
            subject=subject,
            body=body
        ))
        
        # Log the action (in production, you'd store the reset token in database)
        print(f"Password reset requested for: {user.email}")
        print(f"Reset link: {reset_link}")
        
    except Exception as e:
        print(f"Failed to send password reset email: {str(e)}")
        # Don't reveal email sending failures to prevent enumeration
    
    return {"message": "If the email exists in our system, a password reset link has been sent."}

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
    role: Optional[str] = Query(None, description="Filter by role (admin, agent, client, customer)"),
    email: Optional[str] = Query(None, description="Search by email (partial match)"),
    first_name: Optional[str] = Query(None, description="Search by first name (partial match)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get users with role-based access and search filters. Admin can view all, agents can view only clients."""
    
    # Check user permissions
    if current_user.role not in ["admin", "agent"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only admins and agents can view user lists."
        )
    
    # Build base query
    query = db.query(User)
    
    # Role-based filtering
    if current_user.role == "agent":
        # Agents can only see clients
        query = query.filter(User.role == "client")
    elif current_user.role == "admin" and role:
        # Admins can filter by any role
        query = query.filter(User.role == role)
    
    # Search filters
    if email:
        query = query.filter(User.email.ilike(f"%{email}%"))
    
    if first_name:
        query = query.filter(User.first_name.ilike(f"%{first_name}%"))
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    # Sanitize emails to prevent validation errors
    def sanitize_email(email):
        if not email:
            return None
        # Fix double periods and other common email issues
        sanitized = email.replace('..', '.').strip()
        # Basic email validation - if still invalid, return None
        if '@' not in sanitized or sanitized.count('@') != 1:
            return None
        return sanitized
    
    # Create sanitized user responses
    sanitized_users = []
    for user in users:
        # Create a copy of user data with sanitized email
        user_dict = {
            'user_id': user.user_id,
            'email': sanitize_email(user.email),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
            'role': user.role,
            'is_active': user.is_active,
            'full_name': user.full_name,
            'created_at': user.created_at,
            'updated_at': user.updated_at,
            'preferences': user.preferences
        }
        sanitized_users.append(user_dict)
    
    return sanitized_users

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
    
    # Sanitize email to prevent validation errors
    def sanitize_email(email):
        if not email:
            return None
        # Fix double periods and other common email issues
        sanitized = email.replace('..', '.').strip()
        # Basic email validation - if still invalid, return None
        if '@' not in sanitized or sanitized.count('@') != 1:
            return None
        return sanitized
    
    # Return sanitized user data
    return {
        'user_id': user.user_id,
        'email': sanitize_email(user.email),
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone': user.phone,
        'role': user.role,
        'is_active': user.is_active,
        'full_name': user.full_name,
        'created_at': user.created_at,
        'updated_at': user.updated_at,
        'preferences': user.preferences
    }

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