from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, text
import math
from typing import List, Optional
import uuid

from database import get_db
import schemas
from schemas import (
    EnhancedAgentResponseWithUserData, PropertyResponse,
    ClientAgentRelationshipResponse, AgentRepresentationRequest,
    ClientSummary, ClientAgentRelationshipUpdate, AdminAgentStatusUpdate, Message,
    AgentListFilters, PaginatedAgentResponse
)
from auth import get_current_active_user, get_current_user_optional, require_admin
from db_models import User, Property, ClientAgentRelationship, PropertyInterest, Listing, AgentProfile as AgentProfileModel
from notification_service import NotificationService

router = APIRouter(prefix="/agents", tags=["agent-discovery"])

@router.get("/", response_model=PaginatedAgentResponse)
async def discover_agents(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    pageSize: int = Query(20, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for name/email"),
    city: Optional[str] = Query(None, description="Filter by city"),
    specialization: Optional[str] = Query(None, description="Filter by specialization"),
    sort: Optional[str] = Query("created_at", description="Sort field (created_at, name, rating)"),
    current_user: Optional[User] = Depends(get_current_user_optional),  # Optional authentication
    db: Session = Depends(get_db)
):
    """Public endpoint to discover available agents with enhanced profiles and pagination."""
    
    # Calculate offset for pagination
    offset = (page - 1) * pageSize
    
    # Base query for all agent profiles (including CREA imports without user accounts)
    base_query = db.query(AgentProfileModel).options(
        joinedload(AgentProfileModel.user),
        joinedload(AgentProfileModel.office)
    )
    
    # Only show active agents (either with active user accounts or CREA imports)
    base_query = base_query.filter(
        or_(
            and_(AgentProfileModel.user_id.isnot(None), AgentProfileModel.user.has(User.is_active == True)),
            and_(AgentProfileModel.user_id.is_(None), AgentProfileModel.member_status == 'Active')
        )
    )
    
    # Apply filters
    if city:
        base_query = base_query.filter(func.lower(AgentProfileModel.city).like(f"%{city.lower()}%"))
    
    if specialization:
        base_query = base_query.filter(func.lower(AgentProfileModel.specialization).like(f"%{specialization.lower()}%"))
    
    # Text search on name and email
    if q:
        search_term = f"%{q.lower()}%"
        base_query = base_query.filter(
            or_(
                func.lower(AgentProfileModel.first_name).like(search_term),
                func.lower(AgentProfileModel.last_name).like(search_term),
                func.lower(AgentProfileModel.agent_email).like(search_term),
                # Also search user email if linked
                and_(
                    AgentProfileModel.user_id.isnot(None),
                    AgentProfileModel.user.has(func.lower(User.email).like(search_term))
                )
            )
        )
    
    # Apply sorting
    if sort == "name":
        base_query = base_query.order_by(AgentProfileModel.last_name.asc(), AgentProfileModel.first_name.asc())
    elif sort == "rating":
        base_query = base_query.order_by(desc(AgentProfileModel.rating), AgentProfileModel.created_at.desc())
    else:  # Default to created_at
        base_query = base_query.order_by(desc(AgentProfileModel.created_at))
    
    # Get total count for pagination (more efficient count)
    count_query = base_query.statement.with_only_columns(func.count()).order_by(None)
    total_count = db.execute(count_query).scalar()
    
    # Apply pagination
    agent_profiles = base_query.offset(offset).limit(pageSize).all()
    
    # Calculate total pages
    total_pages = math.ceil(total_count / pageSize) if total_count > 0 else 1
    
    # Build enhanced agent responses (simplified)
    agent_responses = []
    
    # Helper function to sanitize email
    def sanitize_email(email):
        if not email:
            return None
        # Fix double periods and other common email issues
        sanitized = email.replace('..', '.').strip()
        # Basic email validation - if still invalid, return None
        if '@' not in sanitized or sanitized.count('@') != 1:
            return None
        return sanitized
    
    for agent_profile in agent_profiles:
        # Handle both User-based agents and CREA imports
        if agent_profile.user:
            # User-based agent
            response_data = {
                # User information
                "user_id": agent_profile.user.user_id,
                "email": sanitize_email(agent_profile.user.email),
                "first_name": agent_profile.user.first_name,
                "last_name": agent_profile.user.last_name,
                "phone": agent_profile.user.phone,
                "full_name": agent_profile.user.full_name,
                "role": agent_profile.user.role,
                "is_active": agent_profile.user.is_active,
                "created_at": agent_profile.user.created_at,
            }
        else:
            # CREA-imported agent without user account
            response_data = {
                # Use agent profile data since no user exists
                "user_id": None,
                "email": sanitize_email(agent_profile.agent_email),
                "first_name": agent_profile.first_name,
                "last_name": agent_profile.last_name,
                "phone": agent_profile.agent_phone,
                "full_name": f"{agent_profile.first_name or ''} {agent_profile.last_name or ''}".strip() or "Unknown Agent",
                "role": "agent",
                "is_active": True,  # CREA agents are considered active if imported
                "created_at": agent_profile.created_at,
            }
        
        # Add agent profile data (always exists since we're querying AgentProfile directly)
        response_data.update({
            "profile_id": agent_profile.profile_id,
            "aka": agent_profile.aka,
            "specialization": agent_profile.specialization,
            "experience": agent_profile.experience,
            "agency_name": agent_profile.agency_name,
            "rating": float(agent_profile.rating) if agent_profile.rating else 0.0,
            "total_sales": agent_profile.total_sales,
            "active_listings": agent_profile.active_listings,
            "performance": agent_profile.performance,
            "platform_status": agent_profile.platform_status,
            "bio": agent_profile.bio,
            "profile_image": agent_profile.profile_image,
            "social_media": agent_profile.social_media or {},
            "city": agent_profile.city,
            "province": agent_profile.province,
            "service_areas": agent_profile.service_areas or [],
            "is_accepting_clients": agent_profile.is_accepting_clients,
            "preferred_contact_method": agent_profile.preferred_contact_method,
            "license_number": agent_profile.license_number,
            "member_designation": agent_profile.member_designation,
            "member_status": agent_profile.member_status,
            "languages": agent_profile.languages or [],
            "agent_email": agent_profile.agent_email,
            "agent_phone": agent_profile.agent_phone,
            "agent_mobile": agent_profile.agent_mobile,
            "agent_fax": agent_profile.agent_fax,
            "crea_agent_key": agent_profile.crea_agent_key,
        })
        
        agent_responses.append(EnhancedAgentResponseWithUserData(**response_data))
    
    return PaginatedAgentResponse(
        agents=agent_responses,
        total=total_count,
        page=page,
        pageSize=pageSize,
        totalPages=total_pages
    )

@router.get("/my-clients", response_model=List[ClientSummary])
async def get_my_clients(
    status: Optional[str] = Query(None, description="Filter by relationship status"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get clients for the current agent."""
    
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403, 
            detail="Only agents can access client lists"
        )
    
    query = db.query(ClientAgentRelationship).options(
        joinedload(ClientAgentRelationship.client)
    ).filter(ClientAgentRelationship.agent_id == current_user.user_id)
    
    if status:
        query = query.filter(ClientAgentRelationship.status == status)
    
    relationships = query.order_by(ClientAgentRelationship.created_at.desc()).all()
    
    client_summaries = []
    for rel in relationships:
        # Get client's property interests count
        interested_properties = db.query(PropertyInterest).filter(
            PropertyInterest.user_id == rel.client_id,
            PropertyInterest.status == "active"
        ).count()
        
        # Get last activity (last property view or interest)
        last_activity = db.query(PropertyInterest.updated_at).filter(
            PropertyInterest.user_id == rel.client_id
        ).order_by(PropertyInterest.updated_at.desc()).first()
        
        client_summary = ClientSummary(
            user_id=rel.client.user_id,
            email=rel.client.email,
            full_name=rel.client.full_name,
            role=rel.client.role,
            created_at=rel.client.created_at,
            relationship_status=rel.status,
            interested_properties=interested_properties,
            last_activity=last_activity[0] if last_activity else None
        )
        client_summaries.append(client_summary)
    
    return client_summaries

@router.get("/{agent_id}", response_model=EnhancedAgentResponseWithUserData)
async def get_agent_profile(
    agent_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_current_user_optional),  # Optional authentication
    db: Session = Depends(get_db)
):
    """Get detailed agent profile."""
    
    # Helper function to sanitize email
    def sanitize_email(email):
        if not email:
            return None
        # Fix double periods and other common email issues
        sanitized = email.replace('..', '.').strip()
        # Basic email validation - if still invalid, return None
        if '@' not in sanitized or sanitized.count('@') != 1:
            return None
        return sanitized
    
    # Query AgentProfile directly to include CREA-only agents
    agent_profile = db.query(AgentProfileModel).options(
        joinedload(AgentProfileModel.user),
        joinedload(AgentProfileModel.office)
    ).filter(AgentProfileModel.profile_id == agent_id).first()
    
    if not agent_profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Build response data similar to discover_agents
    response_data = {
        # Use User data if available, otherwise AgentProfile data
        "user_id": agent_profile.user.user_id if agent_profile.user else None,
        "email": sanitize_email(agent_profile.user.email if agent_profile.user else agent_profile.agent_email),
        "first_name": agent_profile.first_name,
        "last_name": agent_profile.last_name,
        "phone": agent_profile.user.phone if agent_profile.user else agent_profile.agent_phone,
        "full_name": f"{agent_profile.first_name or ''} {agent_profile.last_name or ''}".strip(),
        "role": agent_profile.user.role if agent_profile.user else "agent",
        "is_active": agent_profile.user.is_active if agent_profile.user else True,
        "created_at": agent_profile.user.created_at if agent_profile.user else agent_profile.created_at,
        
        # AgentProfile specific data
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
        "performance": agent_profile.performance,
        "platform_status": agent_profile.platform_status,
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

@router.get("/{agent_id}/properties", response_model=List[PropertyResponse])
async def get_agent_properties(
    agent_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    status: Optional[str] = Query("available"),
    db: Session = Depends(get_db)
):
    """Get properties listed by a specific agent."""
    
    # Verify agent exists (check AgentProfile first, then User)
    agent_profile = db.query(AgentProfileModel).filter(
        AgentProfileModel.profile_id == agent_id
    ).first()
    
    if not agent_profile:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # For CREA agents, use CREA agent key to find properties
    # For user agents, use user_id
    if agent_profile.user_id:
        # Agent has user account - use user_id
        query = db.query(Property).join(Listing).filter(
            Listing.agent_id == agent_profile.user_id
        )
    else:
        # CREA-only agent - use CREA agent key or listing_agent_id
        query = db.query(Property).filter(
            Property.listing_agent_id == agent_profile.crea_agent_key
        )
    
    if status:
        query = query.filter(Property.status == status)
    
    properties = query.order_by(Property.created_at.desc()).offset(skip).all()
    
    return properties

@router.post("/request-representation", response_model=ClientAgentRelationshipResponse)
async def request_agent_representation(
    request_data: AgentRepresentationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Request representation from an agent."""
    
    # Verify user is a customer or client
    if current_user.role not in ["customer", "client"]:
        raise HTTPException(
            status_code=403, 
            detail="Only customers and clients can request agent representation"
        )
    
    # Verify agent exists and is active
    agent = db.query(User).filter(
        User.user_id == request_data.agent_id,
        User.role == "agent",
        User.is_active == True
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or inactive")
    
    # Check if relationship already exists
    existing_relationship = db.query(ClientAgentRelationship).filter(
        ClientAgentRelationship.client_id == current_user.user_id,
        ClientAgentRelationship.agent_id == request_data.agent_id,
        ClientAgentRelationship.status.in_(["pending", "active"])
    ).first()
    
    if existing_relationship:
        raise HTTPException(
            status_code=400, 
            detail="Representation request already exists with this agent"
        )
    
    # Create new relationship
    relationship = ClientAgentRelationship(
        client_id=current_user.user_id,
        agent_id=request_data.agent_id,
        requested_by="client",
        property_id=request_data.property_id,
        notes=request_data.message,
        status="pending"
    )
    
    db.add(relationship)
    db.commit()
    db.refresh(relationship)
    
    # Send notification to agent
    await NotificationService.notify_agent_of_client_interest(
        db=db,
        agent_id=str(request_data.agent_id),
        client_id=str(current_user.user_id),
        property_id=str(request_data.property_id) if request_data.property_id else None,
        message=request_data.message
    )
    
    # Load relationship with related data for response
    relationship_with_data = db.query(ClientAgentRelationship).options(
        joinedload(ClientAgentRelationship.client),
        joinedload(ClientAgentRelationship.agent),
        joinedload(ClientAgentRelationship.property)
    ).filter(ClientAgentRelationship.relationship_id == relationship.relationship_id).first()
    
    return relationship_with_data



@router.put("/client-relationship/{relationship_id}", response_model=ClientAgentRelationshipResponse)
async def update_client_relationship(
    relationship_id: uuid.UUID,
    update_data: ClientAgentRelationshipUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update client relationship status (agents only)."""
    
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403, 
            detail="Only agents can update client relationships"
        )
    
    # Find the relationship
    relationship = db.query(ClientAgentRelationship).filter(
        ClientAgentRelationship.relationship_id == relationship_id
    ).first()
    
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")
    
    # Check permissions (agents can only update their own client relationships)
    if current_user.role == "agent" and relationship.agent_id != current_user.user_id:
        raise HTTPException(
            status_code=403, 
            detail="Can only update your own client relationships"
        )
    
    # Update relationship
    if update_data.status:
        relationship.status = update_data.status
        if update_data.status == "active":
            relationship.activated_at = func.now()
        elif update_data.status == "terminated":
            relationship.terminated_at = func.now()
    
    if update_data.notes:
        relationship.notes = update_data.notes
    
    db.commit()
    db.refresh(relationship)
    
    # Send notification to client about status change
    if update_data.status:
        await NotificationService.notify_client_of_agent_response(
            db=db,
            client_id=str(relationship.client_id),
            agent_id=str(relationship.agent_id),
            status=update_data.status,
            message=update_data.notes
        )
    
    # Load with related data for response
    relationship_with_data = db.query(ClientAgentRelationship).options(
        joinedload(ClientAgentRelationship.client),
        joinedload(ClientAgentRelationship.agent),
        joinedload(ClientAgentRelationship.property)
    ).filter(ClientAgentRelationship.relationship_id == relationship_id).first()
    
    return relationship_with_data

# Admin endpoints
@router.put("/{agent_id}/status", response_model=Message)
async def admin_update_agent_status(
    agent_id: uuid.UUID,
    status_update: AdminAgentStatusUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update agent platform status (Admin only) - Alternative endpoint."""
    
    # Find the agent profile
    agent_profile = db.query(AgentProfileModel).filter(
        AgentProfileModel.profile_id == agent_id
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