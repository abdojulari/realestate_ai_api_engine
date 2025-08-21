from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from typing import List, Optional
import uuid

from database import get_db
import schemas
from auth import get_current_active_user, get_current_user_optional
from db_models import PropertyInterest, Property, User, ClientAgentRelationship
from notification_service import NotificationService

router = APIRouter(prefix="/property-interests", tags=["property-interests"])

@router.get("/", response_model=List[schemas.PropertyInterestResponse])
async def get_all_property_interests(
    status: Optional[str] = Query("active", description="Filter by interest status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500, description="Number of items per page (max 500)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get property interests with role-based access. Admin sees all, agents see their clients only, users redirected to my-interests."""
    
    if current_user.role == "admin":
        # Admins can see all property interests
        query = db.query(PropertyInterest).options(
            joinedload(PropertyInterest.property),
            joinedload(PropertyInterest.user),
            joinedload(PropertyInterest.agent)
        )
        
    elif current_user.role == "agent":
        # Agents can see interests from their represented clients
        client_ids_subquery = db.query(ClientAgentRelationship.client_id).filter(
            ClientAgentRelationship.agent_id == current_user.user_id,
            ClientAgentRelationship.status == "active"
        )
        
        query = db.query(PropertyInterest).options(
            joinedload(PropertyInterest.property),
            joinedload(PropertyInterest.user),
            joinedload(PropertyInterest.agent)
        ).filter(PropertyInterest.user_id.in_(client_ids_subquery))
        
    else:
        # Regular users should use /my-interests instead
        raise HTTPException(
            status_code=403,
            detail="Use /my-interests endpoint to view your own property interests"
        )
    
    # Apply filters
    if status:
        query = query.filter(PropertyInterest.status == status)
    
    # Apply pagination and ordering
    interests = query.order_by(PropertyInterest.created_at.desc()).offset(skip).limit(limit).all()
    
    return interests

@router.post("/", response_model=schemas.PropertyInterestResponse, status_code=status.HTTP_201_CREATED)
async def express_property_interest(
    interest_data: schemas.PropertyInterestCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Express interest in a property. Requires authentication."""
    
    # Verify property exists
    property_obj = db.query(Property).filter(Property.property_id == interest_data.property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check if user already has interest in this property
    existing_interest = db.query(PropertyInterest).filter(
        PropertyInterest.user_id == current_user.user_id,
        PropertyInterest.property_id == interest_data.property_id,
        PropertyInterest.status == "active"
    ).first()
    
    if existing_interest:
        raise HTTPException(
            status_code=400, 
            detail="You have already expressed interest in this property"
        )
    
    # Create property interest
    property_interest = PropertyInterest(
        user_id=current_user.user_id,
        property_id=interest_data.property_id,
        agent_id=interest_data.agent_id,
        interest_level=interest_data.interest_level,
        notes=interest_data.notes,
        status="active"
    )
    
    db.add(property_interest)
    db.commit()
    db.refresh(property_interest)
    
    # If user has an agent relationship, notify the agent
    if current_user.role in ["customer", "client"]:
        # Find user's active agent relationship
        agent_relationship = db.query(ClientAgentRelationship).filter(
            ClientAgentRelationship.client_id == current_user.user_id,
            ClientAgentRelationship.status == "active"
        ).first()
        
        if agent_relationship:
            await NotificationService.notify_property_interest(
                db=db,
                agent_id=str(agent_relationship.agent_id),
                client_id=str(current_user.user_id),
                property_id=str(interest_data.property_id),
                interest_level=interest_data.interest_level
            )
    
    # Load interest with related data for response
    interest_with_data = db.query(PropertyInterest).options(
        joinedload(PropertyInterest.property),
        joinedload(PropertyInterest.agent)
    ).filter(PropertyInterest.interest_id == property_interest.interest_id).first()
    
    return interest_with_data

@router.get("/my-interests", response_model=List[schemas.PropertyInterestResponse])
async def get_my_property_interests(
    status: Optional[str] = Query("active", description="Filter by interest status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get current user's property interests."""
    
    query = db.query(PropertyInterest).options(
        joinedload(PropertyInterest.property),
        joinedload(PropertyInterest.agent)
    ).filter(PropertyInterest.user_id == current_user.user_id)
    
    if status:
        query = query.filter(PropertyInterest.status == status)
    
    interests = query.order_by(PropertyInterest.created_at.desc()).offset(skip).limit(limit).all()
    
    return interests

@router.get("/client/{client_id}", response_model=List[schemas.PropertyInterestResponse])
async def get_client_property_interests(
    client_id: uuid.UUID,
    status: Optional[str] = Query("active", description="Filter by interest status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get property interests for a specific client (agents only)."""
    
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403, 
            detail="Only agents can view client property interests"
        )
    
    # For agents, verify they represent this client
    if current_user.role == "agent":
        relationship = db.query(ClientAgentRelationship).filter(
            ClientAgentRelationship.client_id == client_id,
            ClientAgentRelationship.agent_id == current_user.user_id,
            ClientAgentRelationship.status == "active"
        ).first()
        
        if not relationship:
            raise HTTPException(
                status_code=403, 
                detail="You do not represent this client"
            )
    
    query = db.query(PropertyInterest).options(
        joinedload(PropertyInterest.property),
        joinedload(PropertyInterest.agent)
    ).filter(PropertyInterest.user_id == client_id)
    
    if status:
        query = query.filter(PropertyInterest.status == status)
    
    interests = query.order_by(PropertyInterest.created_at.desc()).offset(skip).limit(limit).all()
    
    return interests

@router.put("/{interest_id}", response_model=schemas.PropertyInterestResponse)
async def update_property_interest(
    interest_id: uuid.UUID,
    update_data: schemas.PropertyInterestUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a property interest."""
    
    # Find the interest
    interest = db.query(PropertyInterest).filter(
        PropertyInterest.interest_id == interest_id
    ).first()
    
    if not interest:
        raise HTTPException(status_code=404, detail="Property interest not found")
    
    # Check permissions
    if current_user.role in ["customer", "client"]:
        # Users can only update their own interests
        if interest.user_id != current_user.user_id:
            raise HTTPException(
                status_code=403, 
                detail="Can only update your own property interests"
            )
    elif current_user.role == "agent":
        # Agents can update interests of their represented clients
        relationship = db.query(ClientAgentRelationship).filter(
            ClientAgentRelationship.client_id == interest.user_id,
            ClientAgentRelationship.agent_id == current_user.user_id,
            ClientAgentRelationship.status == "active"
        ).first()
        
        if not relationship:
            raise HTTPException(
                status_code=403, 
                detail="Can only update interests of your represented clients"
            )
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Update interest
    update_fields = update_data.dict(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(interest, field, value)
    
    db.commit()
    db.refresh(interest)
    
    # Load with related data for response
    interest_with_data = db.query(PropertyInterest).options(
        joinedload(PropertyInterest.property),
        joinedload(PropertyInterest.agent)
    ).filter(PropertyInterest.interest_id == interest_id).first()
    
    return interest_with_data

@router.delete("/{interest_id}", response_model=schemas.Message)
async def remove_property_interest(
    interest_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove/deactivate a property interest."""
    
    # Find the interest
    interest = db.query(PropertyInterest).filter(
        PropertyInterest.interest_id == interest_id
    ).first()
    
    if not interest:
        raise HTTPException(status_code=404, detail="Property interest not found")
    
    # Check permissions (same as update)
    if current_user.role in ["customer", "client"]:
        if interest.user_id != current_user.user_id:
            raise HTTPException(
                status_code=403, 
                detail="Can only remove your own property interests"
            )
    elif current_user.role == "agent":
        relationship = db.query(ClientAgentRelationship).filter(
            ClientAgentRelationship.client_id == interest.user_id,
            ClientAgentRelationship.agent_id == current_user.user_id,
            ClientAgentRelationship.status == "active"
        ).first()
        
        if not relationship:
            raise HTTPException(
                status_code=403, 
                detail="Can only remove interests of your represented clients"
            )
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Mark as inactive rather than deleting
    interest.status = "inactive"
    db.commit()
    
    return schemas.Message(message="Property interest removed successfully")

@router.get("/property/{property_id}/interests", response_model=List[schemas.PropertyInterestResponse])
async def get_property_interests(
    property_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get all interests for a specific property (agents/admins only)."""
    
    if current_user.role not in ["agent", "admin"]:
        raise HTTPException(
            status_code=403, 
            detail="Only agents and admins can view property interests"
        )
    
    # Verify property exists
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Get interests for this property
    interests = db.query(PropertyInterest).options(
        joinedload(PropertyInterest.user),
        joinedload(PropertyInterest.agent)
    ).filter(
        PropertyInterest.property_id == property_id,
        PropertyInterest.status == "active"
    ).order_by(PropertyInterest.created_at.desc()).all()
    
    return interests

@router.get("/analytics/my-interests", response_model=dict)
async def get_my_interest_analytics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get analytics for current user's property interests."""
    
    # Get interest statistics
    total_interests = db.query(PropertyInterest).filter(
        PropertyInterest.user_id == current_user.user_id
    ).count()
    
    active_interests = db.query(PropertyInterest).filter(
        PropertyInterest.user_id == current_user.user_id,
        PropertyInterest.status == "active"
    ).count()
    
    # Interest by level
    interest_levels = db.query(
        PropertyInterest.interest_level,
        func.count(PropertyInterest.interest_id).label('count')
    ).filter(
        PropertyInterest.user_id == current_user.user_id,
        PropertyInterest.status == "active"
    ).group_by(PropertyInterest.interest_level).all()
    
    # Interest by city
    city_interests = db.query(
        Property.city,
        func.count(PropertyInterest.interest_id).label('count')
    ).join(PropertyInterest, Property.property_id == PropertyInterest.property_id).filter(
        PropertyInterest.user_id == current_user.user_id,
        PropertyInterest.status == "active"
    ).group_by(Property.city).order_by(func.count(PropertyInterest.interest_id).desc()).limit(10).all()
    
    return {
        "total_interests": total_interests,
        "active_interests": active_interests,
        "by_interest_level": [{"level": level, "count": count} for level, count in interest_levels],
        "by_city": [{"city": city, "count": count} for city, count in city_interests]
    } 