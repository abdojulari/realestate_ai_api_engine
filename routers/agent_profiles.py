from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
import uuid

from database import get_db
from schemas import (
    AgentProfileCreate, AgentProfileUpdate, EnhancedAgentResponse, 
    SocialMediaLinks, Message, EnhancedAgentResponseWithUserData, AdminAgentStatusUpdate
)
import schemas
from auth import get_current_active_user, require_agent_or_admin, require_admin
from db_models import User, AgentProfile
from notification_service import NotificationService

router = APIRouter(prefix="/agent-profiles", tags=["Agent Profiles"])

@router.get("/my-profile", response_model=EnhancedAgentResponseWithUserData)
async def get_my_agent_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current agent's profile information with user data pre-populated."""
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only agents can access agent profiles"
        )
    
    # Load user with agent profile
    user_with_profile = db.query(User).options(
        joinedload(User.agent_profile)
    ).filter(User.user_id == current_user.user_id).first()
    
    # Build response with user data pre-populated (non-redundant approach)
    response_data = {
        # User information (automatically populated from signup)
        "user_id": user_with_profile.user_id,
        "email": user_with_profile.email,
        "first_name": user_with_profile.first_name,
        "last_name": user_with_profile.last_name,
        "phone": user_with_profile.phone,
        "full_name": user_with_profile.full_name,
        "role": user_with_profile.role,
        "is_active": user_with_profile.is_active,
        "created_at": user_with_profile.created_at,
    }
    
    # Add agent profile data if exists
    if user_with_profile.agent_profile:
        profile = user_with_profile.agent_profile
        response_data.update({
            "profile_id": profile.profile_id,
            "aka": profile.aka,
            "specialization": profile.specialization,
            "experience": profile.experience,
            "agency_name": profile.agency_name,
            "license_number": profile.license_number,
            "rating": profile.rating,
            "total_sales": profile.total_sales,
            "active_listings": profile.active_listings,
            "performance": profile.performance,
            "platform_status": profile.platform_status,
            "bio": profile.bio,
            "profile_image": profile.profile_image,
            "social_media": profile.social_media or {},
            "city": profile.city,
            "province": profile.province,
            "service_areas": profile.service_areas or [],
            "is_accepting_clients": profile.is_accepting_clients,
            "preferred_contact_method": profile.preferred_contact_method,
            "profile_updated_at": profile.updated_at
        })
    else:
        # If no profile exists yet, provide defaults for agent who hasn't completed onboarding
        response_data.update({
            "profile_id": None,
            "social_media": {},
            "service_areas": [],
            "is_accepting_clients": False,  # Don't accept clients until profile is complete
        })
    
    return EnhancedAgentResponseWithUserData(**response_data)

@router.post("/my-profile", response_model=EnhancedAgentResponseWithUserData)
async def create_my_agent_profile(
    profile_data: AgentProfileCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create agent profile for current user (completes onboarding)."""
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only agents can create agent profiles"
        )
    
    # Check if profile already exists
    existing_profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == current_user.user_id
    ).first()
    
    if existing_profile:
        raise HTTPException(
            status_code=400,
            detail="Agent profile already exists. Use PUT to update."
        )
    
    # Create new profile - only profile-specific data (no user data redundancy)
    profile_dict = profile_data.dict(exclude_unset=True)
    
    # Convert social_media to dict if provided
    if 'social_media' in profile_dict and profile_dict['social_media']:
        profile_dict['social_media'] = profile_dict['social_media'].dict(exclude_unset=True)
    
    new_profile = AgentProfile(
        user_id=current_user.user_id,
        **profile_dict
    )
    
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    
    # Send profile completion notification
    await NotificationService.create_notification(
        db=db,
        user_id=str(current_user.user_id),
        notification_type="agent_profile_completed",
        title="Agent Profile Completed Successfully!",
        message=f"""
        <h2>Welcome to Real Estate AI Engine!</h2>
        <p>Congratulations {current_user.first_name}! Your agent profile is now complete and active.</p>
        <p>You can now:</p>
        <ul>
            <li>Receive client requests and inquiries</li>
            <li>Manage property listings</li>
            <li>Be discovered by potential clients</li>
        </ul>
        <p>Your profile will be visible to users searching for agents in your service areas.</p>
        """,
        data={"profile_id": str(new_profile.profile_id), "onboarding_complete": True},
        send_email=True
    )
    
    # Return updated profile with user data
    return await get_my_agent_profile(current_user, db)

@router.put("/my-profile", response_model=EnhancedAgentResponse)
async def update_my_agent_profile(
    profile_update: AgentProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update current agent's profile."""
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only agents can update agent profiles"
        )
    
    # Get or create profile
    agent_profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == current_user.user_id
    ).first()
    
    if not agent_profile:
        # Create new profile if doesn't exist
        agent_profile = AgentProfile(user_id=current_user.user_id)
        db.add(agent_profile)
    
    # Update profile with provided data
    update_data = profile_update.dict(exclude_unset=True)
    
    # Handle social media update
    if 'social_media' in update_data and update_data['social_media']:
        # If social media exists, merge with existing
        existing_social = agent_profile.social_media or {}
        new_social = update_data['social_media'].dict(exclude_unset=True) if hasattr(update_data['social_media'], 'dict') else update_data['social_media']
        existing_social.update(new_social)
        update_data['social_media'] = existing_social
    
    # Apply updates
    for field, value in update_data.items():
        setattr(agent_profile, field, value)
    
    db.commit()
    db.refresh(agent_profile)
    
    # Return updated profile
    return await get_my_agent_profile(current_user, db)

@router.get("/{agent_id}", response_model=EnhancedAgentResponse)
async def get_agent_profile(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get public agent profile by agent user ID."""
    
    # Load user with agent profile
    user_with_profile = db.query(User).options(
        joinedload(User.agent_profile)
    ).filter(
        User.user_id == agent_id,
        User.role.in_(["agent", "admin"]),
        User.is_active == True
    ).first()
    
    if not user_with_profile:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )
    
    # Build response (public view)
    response_data = {
        # User information (public)
        "user_id": user_with_profile.user_id,
        "email": user_with_profile.email,
        "first_name": user_with_profile.first_name,
        "last_name": user_with_profile.last_name,
        "phone": user_with_profile.phone,
        "full_name": user_with_profile.full_name,
        "role": user_with_profile.role,
        "is_active": user_with_profile.is_active,
        "created_at": user_with_profile.created_at,
    }
    
    # Add agent profile data if exists
    if user_with_profile.agent_profile:
        profile = user_with_profile.agent_profile
        response_data.update({
            "profile_id": profile.profile_id,
            "aka": profile.aka,
            "specialization": profile.specialization,
            "experience": profile.experience,
            "agency_name": profile.agency_name,
            # Don't include license_number in public view
            "rating": profile.rating,
            "total_sales": profile.total_sales,
            "active_listings": profile.active_listings,
            "bio": profile.bio,
            "profile_image": profile.profile_image,
            "social_media": profile.social_media or {},
            "city": profile.city,
            "province": profile.province,
            "service_areas": profile.service_areas or [],
            "is_accepting_clients": profile.is_accepting_clients,
            "preferred_contact_method": profile.preferred_contact_method,
        })
    
    return EnhancedAgentResponse(**response_data)

@router.get("/", response_model=List[EnhancedAgentResponse])
async def get_all_agent_profiles(
    skip: int = 0,
    limit: int = 20,
    city: Optional[str] = None,
    province: Optional[str] = None,
    specialization: Optional[str] = None,
    min_rating: Optional[float] = None,
    is_accepting_clients: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get all agent profiles with optional filters."""
    
    # Start with base query
    query = db.query(User).options(
        joinedload(User.agent_profile)
    ).filter(
        User.role.in_(["agent"]),
        User.is_active == True
    )
    
    # Apply filters if agent profile exists
    if any([city, province, specialization, min_rating, is_accepting_clients is not None]):
        query = query.join(AgentProfile, User.user_id == AgentProfile.user_id)
        
        if city:
            query = query.filter(AgentProfile.city.ilike(f"%{city}%"))
        if province:
            query = query.filter(AgentProfile.province.ilike(f"%{province}%"))
        if specialization:
            query = query.filter(AgentProfile.specialization.ilike(f"%{specialization}%"))
        if min_rating:
            query = query.filter(AgentProfile.rating >= min_rating)
        if is_accepting_clients is not None:
            query = query.filter(AgentProfile.is_accepting_clients == is_accepting_clients)
    
    # Get results
    users_with_profiles = query.offset(skip).limit(limit).all()
    
    # Build response list
    agent_responses = []
    for user in users_with_profiles:
        response_data = {
            "user_id": user.user_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
        }
        
        if user.agent_profile:
            profile = user.agent_profile
            response_data.update({
                "profile_id": profile.profile_id,
                "aka": profile.aka,
                "specialization": profile.specialization,
                "experience": profile.experience,
                "agency_name": profile.agency_name,
                "rating": profile.rating,
                "total_sales": profile.total_sales,
                "active_listings": profile.active_listings,
                "bio": profile.bio,
                "profile_image": profile.profile_image,
                "social_media": profile.social_media or {},
                "city": profile.city,
                "province": profile.province,
                "service_areas": profile.service_areas or [],
                "is_accepting_clients": profile.is_accepting_clients,
                "preferred_contact_method": profile.preferred_contact_method,
            })
        
        agent_responses.append(EnhancedAgentResponse(**response_data))
    
    return agent_responses

@router.delete("/my-profile", response_model=Message)
async def delete_my_agent_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete current agent's profile (keeps user account)."""
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403,
            detail="Only agents can delete agent profiles"
        )
    
    agent_profile = db.query(AgentProfile).filter(
        AgentProfile.user_id == current_user.user_id
    ).first()
    
    if not agent_profile:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found"
        )
    
    db.delete(agent_profile)
    db.commit()
    
    return Message(message="Agent profile deleted successfully")

# Admin endpoints
@router.put("/{agent_id}/status", response_model=Message)
async def update_agent_platform_status(
    agent_id: uuid.UUID,
    status_update: AdminAgentStatusUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update agent platform status (Admin only)."""
    
    # Find the agent profile
    agent_profile = db.query(AgentProfile).filter(
        AgentProfile.profile_id == agent_id
    ).first()
    
    if not agent_profile:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found"
        )
    
    # Update platform status and performance
    agent_profile.platform_status = status_update.platform_status
    if status_update.performance:
        agent_profile.performance = status_update.performance
    
    db.commit()
    db.refresh(agent_profile)
    
    # Send notification to agent if they have a user account
    if agent_profile.user:
        await NotificationService.create_notification(
            db=db,
            user_id=str(agent_profile.user.user_id),
            notification_type="platform_status_update",
            title=f"Platform Status Updated: {status_update.platform_status}",
            message=f"""
            <html>
            <body>
                <h2>Platform Status Update</h2>
                <p>Your platform status has been updated by an administrator.</p>
                
                <div style="margin: 20px 0; padding: 20px; background-color: #f8f9fa; border-radius: 8px;">
                    <h3>Status Details:</h3>
                    <ul>
                        <li><strong>Platform Status:</strong> {status_update.platform_status}</li>
                        {f'<li><strong>Performance Level:</strong> {status_update.performance}</li>' if status_update.performance else ''}
                        {f'<li><strong>Admin Notes:</strong> {status_update.notes}</li>' if status_update.notes else ''}
                    </ul>
                </div>
                
                <p>If you have any questions about this status change, please contact support.</p>
                
                <p>Best regards,<br>Real Estate AI Engine Team</p>
            </body>
            </html>
            """,
            data={
                "platform_status": status_update.platform_status,
                "performance": status_update.performance,
                "admin_notes": status_update.notes,
                "admin_user_id": str(admin_user.user_id)
            },
            send_email=True
        )
    
    return Message(message=f"Agent platform status updated to '{status_update.platform_status}' successfully")