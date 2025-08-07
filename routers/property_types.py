from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas import PropertyTypeCreate, PropertyTypeResponse, Message
from auth import require_admin
from db_models import PropertyType, User

router = APIRouter(prefix="/property-types", tags=["property-types"])

@router.get("/", response_model=List[PropertyTypeResponse])
async def get_property_types(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all property types."""
    property_types = db.query(PropertyType).offset(skip).limit(limit).all()
    return property_types

@router.get("/{type_id}", response_model=PropertyTypeResponse)
async def get_property_type(
    type_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific property type by ID."""
    property_type = db.query(PropertyType).filter(PropertyType.type_id == type_id).first()
    
    if not property_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property type not found"
        )
    
    return property_type

@router.post("/", response_model=PropertyTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_property_type(
    property_type_data: PropertyTypeCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new property type (admin only)."""
    # Check if property type name already exists
    existing_type = db.query(PropertyType).filter(
        PropertyType.type_name == property_type_data.type_name
    ).first()
    
    if existing_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property type with this name already exists"
        )
    
    property_type = PropertyType(**property_type_data.dict())
    db.add(property_type)
    db.commit()
    db.refresh(property_type)
    
    return property_type

@router.put("/{type_id}", response_model=PropertyTypeResponse)
async def update_property_type(
    type_id: int,
    property_type_data: PropertyTypeCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a property type (admin only)."""
    property_type = db.query(PropertyType).filter(PropertyType.type_id == type_id).first()
    
    if not property_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property type not found"
        )
    
    # Check if new name conflicts with existing property type
    if property_type_data.type_name != property_type.type_name:
        existing_type = db.query(PropertyType).filter(
            PropertyType.type_name == property_type_data.type_name
        ).first()
        
        if existing_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Property type with this name already exists"
            )
    
    update_data = property_type_data.dict()
    for field, value in update_data.items():
        setattr(property_type, field, value)
    
    db.commit()
    db.refresh(property_type)
    
    return property_type

@router.delete("/{type_id}", response_model=Message)
async def delete_property_type(
    type_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a property type (admin only)."""
    property_type = db.query(PropertyType).filter(PropertyType.type_id == type_id).first()
    
    if not property_type:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property type not found"
        )
    
    db.delete(property_type)
    db.commit()
    
    return {"message": "Property type deleted successfully"} 