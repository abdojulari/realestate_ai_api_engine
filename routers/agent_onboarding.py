from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import Optional
import uuid
from passlib.context import CryptContext

from database import get_db
from schemas import (
    AgentProfileUpdate, EnhancedAgentResponseWithUserData, 
    Message, AgentClaimRequest, AgentPasswordUpdate
)
import schemas
from auth import get_current_active_user, get_current_user_optional
from db_models import User, AgentProfile
from notification_service import NotificationService

router = APIRouter(prefix="/agent-onboarding", tags=["Agent Onboarding"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/claim-profile", response_model=EnhancedAgentResponseWithUserData)
async def claim_agent_profile(
    claim_request: AgentClaimRequest,
    db: Session = Depends(get_db)
):
    """
    Allow agents to claim their CREA profile by providing verification details.
    This links their temporary User account to their real identity.
    """
    
    # Verify agent exists with provided CREA information
    agent_profile = db.query(AgentProfile).filter(
        and_(
            AgentProfile.first_name.ilike(f"%{claim_request.first_name}%"),
            AgentProfile.last_name.ilike(f"%{claim_request.last_name}%"),
            or_(
                AgentProfile.crea_agent_key == claim_request.crea_agent_key,
                AgentProfile.member_mls_id == claim_request.member_mls_id,
                AgentProfile.agent_phone == claim_request.phone
            )
        )
    ).first()
    
    if not agent_profile:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found. Please verify your CREA information."
        )
    
    # Check if profile is already claimed by a different user
    if agent_profile.user and agent_profile.user.email != claim_request.email:
        # Profile already claimed by someone else
        raise HTTPException(
            status_code=409,
            detail="This profile has already been claimed by another agent."
        )
    
    # Check if user already exists with this email
    existing_user = db.query(User).filter(User.email == claim_request.email).first()
    
    if existing_user:
        if existing_user.role != "agent":
            raise HTTPException(
                status_code=400,
                detail="This email is registered with a different account type."
            )
        
        # Link existing agent user to this profile
        if not agent_profile.user_id:
            agent_profile.user_id = existing_user.user_id
            db.commit()
    
    else:
        # Create new user account
        hashed_password = pwd_context.hash(claim_request.password)
        
        new_user = User(
            email=claim_request.email,
            password_hash=hashed_password,
            first_name=agent_profile.first_name,
            last_name=agent_profile.last_name,
            phone=claim_request.phone,
            role="agent",
            is_active=True,
            preferences={}
        )
        
        db.add(new_user)
        db.flush()  # Get user ID
        
        # Link AgentProfile to new User
        agent_profile.user_id = new_user.user_id
        
        # Update agent contact info with verified details
        agent_profile.agent_email = claim_request.email
        agent_profile.agent_phone = claim_request.phone
        
        db.commit()
    
    # Return the updated agent profile
    agent_profile = db.query(AgentProfile).options(
        joinedload(AgentProfile.user),
        joinedload(AgentProfile.office)
    ).filter(AgentProfile.profile_id == agent_profile.profile_id).first()
    
    # Build response data
    response_data = {
        "user_id": agent_profile.user.user_id,
        "email": agent_profile.user.email,
        "first_name": agent_profile.first_name,
        "last_name": agent_profile.last_name,
        "phone": agent_profile.user.phone,
        "full_name": f"{agent_profile.first_name or ''} {agent_profile.last_name or ''}".strip(),
        "role": agent_profile.user.role,
        "is_active": agent_profile.user.is_active,
        "created_at": agent_profile.user.created_at,
        "profile_id": agent_profile.profile_id,
        "crea_agent_key": agent_profile.crea_agent_key,
        "member_mls_id": agent_profile.member_mls_id,
        "member_national_association_id": agent_profile.member_national_association_id,
        "member_aor": agent_profile.member_aor,
        "member_aor_key": agent_profile.member_aor_key,
        "member_country": agent_profile.member_country,
        "member_email_yn": agent_profile.member_email_yn,
        "member_name_prefix": agent_profile.member_name_prefix,
        "member_name_suffix": agent_profile.member_name_suffix,
        "member_office_phone_ext": agent_profile.member_office_phone_ext,
        "member_toll_free_phone": agent_profile.member_toll_free_phone,
        "member_type": agent_profile.member_type,
        "member_postal_code": agent_profile.member_postal_code,
        "office_key": agent_profile.office_key,
        "office_national_association_id": agent_profile.office_national_association_id,
        "job_title": agent_profile.job_title,
        "aka": agent_profile.aka,
        "specialization": agent_profile.specialization,
        "experience": agent_profile.experience,
        "agency_name": agent_profile.agency_name,
        "license_number": agent_profile.license_number,
        "rating": float(agent_profile.rating) if agent_profile.rating else 0.0,
        "total_sales": agent_profile.total_sales,
        "active_listings": agent_profile.active_listings,
        "bio": agent_profile.bio,
        "profile_image": agent_profile.profile_image,
        "member_designation": agent_profile.member_designation,
        "member_status": agent_profile.member_status,
        "languages": agent_profile.languages or [],
        "social_media": agent_profile.social_media or {},
        "city": agent_profile.city,
        "province": agent_profile.province,
        "service_areas": agent_profile.service_areas or [],
        "is_accepting_clients": agent_profile.is_accepting_clients,
        "preferred_contact_method": agent_profile.preferred_contact_method,
        "profile_updated_at": agent_profile.updated_at
    }
    
    return EnhancedAgentResponseWithUserData(**response_data)

@router.get("/search-profile", response_model=list[EnhancedAgentResponseWithUserData])
async def search_unclaimed_profiles(
    first_name: str,
    last_name: str,
    phone: Optional[str] = None,
    crea_agent_key: Optional[str] = None,
    member_mls_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Search for unclaimed agent profiles to help agents find their profile.
    """
    
    # Search for matching profiles
    query = db.query(AgentProfile).options(
        joinedload(AgentProfile.user),
        joinedload(AgentProfile.office)
    )
    
    # Apply name filters
    query = query.filter(
        and_(
            AgentProfile.first_name.ilike(f"%{first_name}%"),
            AgentProfile.last_name.ilike(f"%{last_name}%")
        )
    )
    
    # Additional verification filters
    if phone:
        query = query.filter(AgentProfile.agent_phone.ilike(f"%{phone}%"))
    
    if crea_agent_key:
        query = query.filter(AgentProfile.crea_agent_key == crea_agent_key)
    
    if member_mls_id:
        query = query.filter(AgentProfile.member_mls_id == member_mls_id)
    
    # Limit results for security
    profiles = query.limit(10).all()
    
    results = []
    for agent_profile in profiles:
        # Show limited info for unclaimed profiles
        response_data = {
            "user_id": agent_profile.user.user_id if agent_profile.user else None,
            "email": "***@***" if agent_profile.user else None,  # Hide email for security
            "first_name": agent_profile.first_name,
            "last_name": agent_profile.last_name,
            "phone": agent_profile.agent_phone[-4:] if agent_profile.agent_phone else None,  # Show last 4 digits
            "full_name": f"{agent_profile.first_name or ''} {agent_profile.last_name or ''}".strip(),
            "role": "agent",
            "is_active": True,
            "created_at": agent_profile.created_at,
            "profile_id": agent_profile.profile_id,
            "crea_agent_key": agent_profile.crea_agent_key,
            "member_mls_id": agent_profile.member_mls_id,
            "member_aor": agent_profile.member_aor,
            "member_country": agent_profile.member_country,
            "member_type": agent_profile.member_type,
            "job_title": agent_profile.job_title,
            "agency_name": agent_profile.agency_name,
            "city": agent_profile.city,
            "province": agent_profile.province,
            "member_status": agent_profile.member_status,
            "is_accepting_clients": agent_profile.is_accepting_clients,
            "profile_updated_at": agent_profile.updated_at,
            # Hide sensitive fields for search results
            "member_national_association_id": None,
            "member_aor_key": None,
            "member_name_prefix": None,
            "member_name_suffix": None,
            "member_office_phone_ext": None,
            "member_toll_free_phone": None,
            "member_postal_code": None,
            "office_key": None,
            "office_national_association_id": None,
            "aka": None,
            "specialization": None,
            "experience": None,
            "license_number": None,
            "rating": None,
            "total_sales": None,
            "active_listings": None,
            "bio": None,
            "profile_image": None,
            "member_designation": None,
            "languages": [],
            "social_media": {},
            "service_areas": [],
            "preferred_contact_method": None,
            "member_email_yn": None
        }
        
        results.append(EnhancedAgentResponseWithUserData(**response_data))
    
    return results

@router.put("/update-credentials", response_model=Message)
async def update_agent_credentials(
    password_update: AgentPasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Allow agents to update their email and password after claiming their profile.
    """
    
    if current_user.role != "agent":
        raise HTTPException(
            status_code=403,
            detail="Only agents can update agent credentials"
        )
    
    # Check if new email is already taken by another user
    if password_update.new_email and password_update.new_email != current_user.email:
        existing_user = db.query(User).filter(
            and_(
                User.email == password_update.new_email,
                User.user_id != current_user.user_id
            )
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=409,
                detail="Email address is already in use by another account."
            )
    
    # Verify current password if changing password
    if password_update.new_password:
        if not pwd_context.verify(password_update.current_password, current_user.password_hash):
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect"
            )
        
        # Update password
        current_user.password_hash = pwd_context.hash(password_update.new_password)
    
    # Update email if provided
    if password_update.new_email:
        current_user.email = password_update.new_email
        
        # Also update agent profile email
        if current_user.agent_profile:
            current_user.agent_profile.agent_email = password_update.new_email
    
    db.commit()
    
    return Message(message="Credentials updated successfully")

@router.put("/edit-profile", response_model=EnhancedAgentResponseWithUserData)
async def edit_agent_profile(
    profile_update: AgentProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Allow agents to edit their professional profile information.
    """
    
    if current_user.role != "agent":
        raise HTTPException(
            status_code=403,
            detail="Only agents can edit agent profiles"
        )
    
    if not current_user.agent_profile:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found"
        )
    
    agent_profile = current_user.agent_profile
    
    # Update editable fields (preserve CREA data)
    if profile_update.bio is not None:
        agent_profile.bio = profile_update.bio
    
    if profile_update.specialization is not None:
        agent_profile.specialization = profile_update.specialization
    
    if profile_update.experience is not None:
        agent_profile.experience = profile_update.experience
    
    if profile_update.is_accepting_clients is not None:
        agent_profile.is_accepting_clients = profile_update.is_accepting_clients
    
    if profile_update.preferred_contact_method is not None:
        agent_profile.preferred_contact_method = profile_update.preferred_contact_method
    
    if profile_update.social_media is not None:
        # Merge with existing social media, preserving CREA data
        existing_social = agent_profile.social_media or {}
        existing_social.update(profile_update.social_media.dict())
        agent_profile.social_media = existing_social
    
    if profile_update.service_areas is not None:
        agent_profile.service_areas = profile_update.service_areas
    
    # Update User table fields
    if profile_update.phone is not None:
        current_user.phone = profile_update.phone
        agent_profile.agent_phone = profile_update.phone
    
    db.commit()
    
    # Return updated profile
    agent_profile = db.query(AgentProfile).options(
        joinedload(AgentProfile.user),
        joinedload(AgentProfile.office)
    ).filter(AgentProfile.profile_id == agent_profile.profile_id).first()
    
    # Build response data
    response_data = {
        "user_id": agent_profile.user.user_id,
        "email": agent_profile.user.email,
        "first_name": agent_profile.first_name,
        "last_name": agent_profile.last_name,
        "phone": agent_profile.user.phone,
        "full_name": f"{agent_profile.first_name or ''} {agent_profile.last_name or ''}".strip(),
        "role": agent_profile.user.role,
        "is_active": agent_profile.user.is_active,
        "created_at": agent_profile.user.created_at,
        "profile_id": agent_profile.profile_id,
        "crea_agent_key": agent_profile.crea_agent_key,
        "member_mls_id": agent_profile.member_mls_id,
        "member_national_association_id": agent_profile.member_national_association_id,
        "member_aor": agent_profile.member_aor,
        "member_aor_key": agent_profile.member_aor_key,
        "member_country": agent_profile.member_country,
        "member_email_yn": agent_profile.member_email_yn,
        "member_name_prefix": agent_profile.member_name_prefix,
        "member_name_suffix": agent_profile.member_name_suffix,
        "member_office_phone_ext": agent_profile.member_office_phone_ext,
        "member_toll_free_phone": agent_profile.member_toll_free_phone,
        "member_type": agent_profile.member_type,
        "member_postal_code": agent_profile.member_postal_code,
        "office_key": agent_profile.office_key,
        "office_national_association_id": agent_profile.office_national_association_id,
        "job_title": agent_profile.job_title,
        "aka": agent_profile.aka,
        "specialization": agent_profile.specialization,
        "experience": agent_profile.experience,
        "agency_name": agent_profile.agency_name,
        "license_number": agent_profile.license_number,
        "rating": float(agent_profile.rating) if agent_profile.rating else 0.0,
        "total_sales": agent_profile.total_sales,
        "active_listings": agent_profile.active_listings,
        "bio": agent_profile.bio,
        "profile_image": agent_profile.profile_image,
        "member_designation": agent_profile.member_designation,
        "member_status": agent_profile.member_status,
        "languages": agent_profile.languages or [],
        "social_media": agent_profile.social_media or {},
        "city": agent_profile.city,
        "province": agent_profile.province,
        "service_areas": agent_profile.service_areas or [],
        "is_accepting_clients": agent_profile.is_accepting_clients,
        "preferred_contact_method": agent_profile.preferred_contact_method,
        "profile_updated_at": agent_profile.updated_at
    }
    
    return EnhancedAgentResponseWithUserData(**response_data)
