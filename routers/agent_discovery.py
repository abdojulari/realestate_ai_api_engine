from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc
from typing import List, Optional
import uuid

from database import get_db
import schemas
from schemas import (
    EnhancedAgentResponseWithUserData, PropertyResponse,
    ClientAgentRelationshipResponse, AgentRepresentationRequest,
    ClientSummary, ClientAgentRelationshipUpdate
)
from auth import get_current_active_user, get_current_user_optional
from db_models import User, Property, ClientAgentRelationship, PropertyInterest, Listing, AgentProfile as AgentProfileModel
from notification_service import NotificationService

router = APIRouter(prefix="/agents", tags=["agent-discovery"])

@router.get("/", response_model=List[EnhancedAgentResponseWithUserData])
async def discover_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    city: Optional[str] = None,
    province: Optional[str] = None,
    specialization: Optional[str] = None,
    min_rating: Optional[float] = None,
    is_accepting_clients: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user),  # Require authentication
    db: Session = Depends(get_db)
):
    """Public endpoint to discover available agents with enhanced profiles."""
    
    # Simplified query to avoid complex joins for now
    query = db.query(User).options(
        joinedload(User.agent_profile)
    ).filter(
        User.role == "agent",
        User.is_active == True
    )
    
    # Apply filters only if we have agent profiles
    if any([city, province, specialization, min_rating, is_accepting_clients is not None]):
        query = query.join(AgentProfileModel, User.user_id == AgentProfileModel.user_id)
        
        if city:
            query = query.filter(AgentProfileModel.city.ilike(f"%{city}%"))
        if province:
            query = query.filter(AgentProfileModel.province.ilike(f"%{province}%"))
        if specialization:
            query = query.filter(AgentProfileModel.specialization.ilike(f"%{specialization}%"))
        if min_rating:
            query = query.filter(AgentProfileModel.rating >= min_rating)
        if is_accepting_clients is not None:
            query = query.filter(AgentProfileModel.is_accepting_clients == is_accepting_clients)
    
    agents = query.distinct().offset(skip).limit(limit).all()
    
    # Build enhanced agent responses (simplified)
    agent_responses = []
    for agent in agents:
        # Build response data
        response_data = {
            # User information
            "user_id": agent.user_id,
            "email": agent.email,
            "first_name": agent.first_name,
            "last_name": agent.last_name,
            "phone": agent.phone,
            "full_name": agent.full_name,
            "role": agent.role,
            "is_active": agent.is_active,
            "created_at": agent.created_at,
        }
        
        # Add agent profile data if exists
        if agent.agent_profile:
            profile = agent.agent_profile
            response_data.update({
                "profile_id": profile.profile_id,
                "aka": profile.aka,
                "specialization": profile.specialization,
                "experience": profile.experience,
                "agency_name": profile.agency_name,
                "rating": profile.rating,
                "total_sales": profile.total_sales,
                "active_listings": 0,  # Default for now
                "bio": profile.bio,
                "profile_image": profile.profile_image,
                "social_media": profile.social_media or {},
                "city": profile.city,
                "province": profile.province,
                "service_areas": profile.service_areas or [],
                "is_accepting_clients": profile.is_accepting_clients,
                "preferred_contact_method": profile.preferred_contact_method,
            })
        else:
            # Default values for agents without profiles
            response_data.update({
                "active_listings": 0,
                "social_media": {},
                "service_areas": [],
                "is_accepting_clients": True,
            })
        
        agent_responses.append(EnhancedAgentResponseWithUserData(**response_data))
    
    return agent_responses

@router.get("/{agent_id}", response_model=EnhancedAgentResponseWithUserData)
async def get_agent_profile(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),  # Require authentication
    db: Session = Depends(get_db)
):
    """Get detailed agent profile."""
    
    agent = db.query(User).filter(
        User.user_id == agent_id,
        User.role == "agent",
        User.is_active == True
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get agent statistics
    total_listings = db.query(Listing).filter(Listing.agent_id == agent.user_id).count()
    active_listings = db.query(Listing).join(Property).filter(
        Listing.agent_id == agent.user_id,
        Property.status == "available"
    ).count()
    total_clients = db.query(ClientAgentRelationship).filter(
        ClientAgentRelationship.agent_id == agent.user_id
    ).count()
    active_clients = db.query(ClientAgentRelationship).filter(
        ClientAgentRelationship.agent_id == agent.user_id,
        ClientAgentRelationship.status == "active"
    ).count()
    
    # Return using schemas.AgentProfile since this is a legacy endpoint
    return schemas.AgentProfile(
        user_id=agent.user_id,
        first_name=agent.first_name,
        last_name=agent.last_name,
        full_name=agent.full_name,
        email=agent.email,
        phone=agent.phone,
        role=agent.role,
        created_at=agent.created_at,
        is_active=agent.is_active,
        total_listings=total_listings,
        active_listings=active_listings,
        total_clients=total_clients,
        active_clients=active_clients
    )

@router.get("/{agent_id}/properties", response_model=List[PropertyResponse])
async def get_agent_properties(
    agent_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query("available"),
    db: Session = Depends(get_db)
):
    """Get properties listed by a specific agent."""
    
    # Verify agent exists
    agent = db.query(User).filter(
        User.user_id == agent_id,
        User.role == "agent"
    ).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get agent's properties through listings
    query = db.query(Property).join(Listing).filter(
        Listing.agent_id == agent_id
    )
    
    if status:
        query = query.filter(Property.status == status)
    
    properties = query.order_by(Property.created_at.desc()).offset(skip).limit(limit).all()
    
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