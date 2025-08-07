from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from database import get_db
from schemas import (
    NeighbourhoodCreate, NeighbourhoodUpdate, NeighbourhoodResponse, 
    TransportTime, Message
)
from auth import get_current_active_user
from db_models import User, Neighbourhood, Property

router = APIRouter(prefix="/neighbourhoods", tags=["Neighbourhoods"])


@router.get("/", response_model=List[NeighbourhoodResponse])
async def get_neighbourhoods(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    property_id: Optional[uuid.UUID] = None,
    neighbourhood_type: Optional[str] = None,
    max_distance: Optional[float] = Query(None, ge=0, description="Maximum distance in km"),
    db: Session = Depends(get_db)
):
    """Get neighbourhoods with optional filtering."""
    query = db.query(Neighbourhood)
    
    if property_id:
        query = query.filter(Neighbourhood.property_id == property_id)
    
    if neighbourhood_type:
        query = query.filter(Neighbourhood.type == neighbourhood_type)
    
    if max_distance is not None:
        query = query.filter(Neighbourhood.distance <= max_distance)
    
    neighbourhoods = query.order_by(Neighbourhood.distance).offset(skip).limit(limit).all()
    
    # Convert database model to response format
    response_data = []
    for neighbourhood in neighbourhoods:
        transport_time = None
        if any([neighbourhood.walking_time, neighbourhood.biking_time, neighbourhood.car_time]):
            transport_time = TransportTime(
                walking=neighbourhood.walking_time,
                biking=neighbourhood.biking_time,
                car=neighbourhood.car_time
            )
        
        neighbourhood_data = NeighbourhoodResponse(
            id=neighbourhood.id,
            property_id=neighbourhood.property_id,
            name=neighbourhood.name,
            type=neighbourhood.type,
            address=neighbourhood.address,
            distance=float(neighbourhood.distance),
            transport_time=transport_time,
            lat=float(neighbourhood.lat),
            lng=float(neighbourhood.lng),
            icon=neighbourhood.icon,
            created_at=neighbourhood.created_at,
            updated_at=neighbourhood.updated_at
        )
        response_data.append(neighbourhood_data)
    
    return response_data


@router.get("/{neighbourhood_id}", response_model=NeighbourhoodResponse)
async def get_neighbourhood(
    neighbourhood_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific neighbourhood by ID."""
    neighbourhood = db.query(Neighbourhood).filter(Neighbourhood.id == neighbourhood_id).first()
    
    if not neighbourhood:
        raise HTTPException(status_code=404, detail="Neighbourhood not found")
    
    transport_time = None
    if any([neighbourhood.walking_time, neighbourhood.biking_time, neighbourhood.car_time]):
        transport_time = TransportTime(
            walking=neighbourhood.walking_time,
            biking=neighbourhood.biking_time,
            car=neighbourhood.car_time
        )
    
    return NeighbourhoodResponse(
        id=neighbourhood.id,
        property_id=neighbourhood.property_id,
        name=neighbourhood.name,
        type=neighbourhood.type,
        address=neighbourhood.address,
        distance=float(neighbourhood.distance),
        transport_time=transport_time,
        lat=float(neighbourhood.lat),
        lng=float(neighbourhood.lng),
        icon=neighbourhood.icon,
        created_at=neighbourhood.created_at,
        updated_at=neighbourhood.updated_at
    )


@router.post("/", response_model=NeighbourhoodResponse)
async def create_neighbourhood(
    neighbourhood_data: NeighbourhoodCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new neighbourhood entry."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == neighbourhood_data.property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Create neighbourhood
    db_neighbourhood = Neighbourhood(
        property_id=neighbourhood_data.property_id,
        name=neighbourhood_data.name,
        type=neighbourhood_data.type,
        address=neighbourhood_data.address,
        distance=neighbourhood_data.distance,
        walking_time=neighbourhood_data.transport_time.walking if neighbourhood_data.transport_time else None,
        biking_time=neighbourhood_data.transport_time.biking if neighbourhood_data.transport_time else None,
        car_time=neighbourhood_data.transport_time.car if neighbourhood_data.transport_time else None,
        lat=neighbourhood_data.lat,
        lng=neighbourhood_data.lng,
        icon=neighbourhood_data.icon
    )
    
    db.add(db_neighbourhood)
    db.commit()
    db.refresh(db_neighbourhood)
    
    transport_time = None
    if neighbourhood_data.transport_time:
        transport_time = neighbourhood_data.transport_time
    
    return NeighbourhoodResponse(
        id=db_neighbourhood.id,
        property_id=db_neighbourhood.property_id,
        name=db_neighbourhood.name,
        type=db_neighbourhood.type,
        address=db_neighbourhood.address,
        distance=float(db_neighbourhood.distance),
        transport_time=transport_time,
        lat=float(db_neighbourhood.lat),
        lng=float(db_neighbourhood.lng),
        icon=db_neighbourhood.icon,
        created_at=db_neighbourhood.created_at,
        updated_at=db_neighbourhood.updated_at
    )


@router.put("/{neighbourhood_id}", response_model=NeighbourhoodResponse)
async def update_neighbourhood(
    neighbourhood_id: int,
    neighbourhood_data: NeighbourhoodUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a neighbourhood entry."""
    neighbourhood = db.query(Neighbourhood).filter(Neighbourhood.id == neighbourhood_id).first()
    
    if not neighbourhood:
        raise HTTPException(status_code=404, detail="Neighbourhood not found")
    
    # Update fields if provided
    update_data = neighbourhood_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "transport_time" and value:
            neighbourhood.walking_time = value.get("walking")
            neighbourhood.biking_time = value.get("biking") 
            neighbourhood.car_time = value.get("car")
        else:
            setattr(neighbourhood, field, value)
    
    db.commit()
    db.refresh(neighbourhood)
    
    transport_time = None
    if any([neighbourhood.walking_time, neighbourhood.biking_time, neighbourhood.car_time]):
        transport_time = TransportTime(
            walking=neighbourhood.walking_time,
            biking=neighbourhood.biking_time,
            car=neighbourhood.car_time
        )
    
    return NeighbourhoodResponse(
        id=neighbourhood.id,
        property_id=neighbourhood.property_id,
        name=neighbourhood.name,
        type=neighbourhood.type,
        address=neighbourhood.address,
        distance=float(neighbourhood.distance),
        transport_time=transport_time,
        lat=float(neighbourhood.lat),
        lng=float(neighbourhood.lng),
        icon=neighbourhood.icon,
        created_at=neighbourhood.created_at,
        updated_at=neighbourhood.updated_at
    )


@router.delete("/{neighbourhood_id}", response_model=Message)
async def delete_neighbourhood(
    neighbourhood_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a neighbourhood entry."""
    neighbourhood = db.query(Neighbourhood).filter(Neighbourhood.id == neighbourhood_id).first()
    
    if not neighbourhood:
        raise HTTPException(status_code=404, detail="Neighbourhood not found")
    
    db.delete(neighbourhood)
    db.commit()
    
    return Message(message="Neighbourhood deleted successfully")


@router.get("/property/{property_id}", response_model=List[NeighbourhoodResponse])
async def get_neighbourhoods_by_property(
    property_id: uuid.UUID,
    neighbourhood_type: Optional[str] = None,
    max_distance: Optional[float] = Query(None, ge=0, description="Maximum distance in km"),
    db: Session = Depends(get_db)
):
    """Get all neighbourhoods for a specific property."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    query = db.query(Neighbourhood).filter(Neighbourhood.property_id == property_id)
    
    if neighbourhood_type:
        query = query.filter(Neighbourhood.type == neighbourhood_type)
    
    if max_distance is not None:
        query = query.filter(Neighbourhood.distance <= max_distance)
    
    neighbourhoods = query.order_by(Neighbourhood.distance).all()
    
    # Convert to response format
    response_data = []
    for neighbourhood in neighbourhoods:
        transport_time = None
        if any([neighbourhood.walking_time, neighbourhood.biking_time, neighbourhood.car_time]):
            transport_time = TransportTime(
                walking=neighbourhood.walking_time,
                biking=neighbourhood.biking_time,
                car=neighbourhood.car_time
            )
        
        neighbourhood_data = NeighbourhoodResponse(
            id=neighbourhood.id,
            property_id=neighbourhood.property_id,
            name=neighbourhood.name,
            type=neighbourhood.type,
            address=neighbourhood.address,
            distance=float(neighbourhood.distance),
            transport_time=transport_time,
            lat=float(neighbourhood.lat),
            lng=float(neighbourhood.lng),
            icon=neighbourhood.icon,
            created_at=neighbourhood.created_at,
            updated_at=neighbourhood.updated_at
        )
        response_data.append(neighbourhood_data)
    
    return response_data