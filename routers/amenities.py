from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas import AmenityCreate, AmenityResponse, Message
from auth import require_admin, require_agent_or_admin
from db_models import Amenity, User

router = APIRouter(prefix="/amenities", tags=["amenities"])

@router.get("/", response_model=List[AmenityResponse])
async def get_amenities(
    skip: int = 0,
    limit: int = 100,
    category: str = None,
    db: Session = Depends(get_db)
):
    """Get all amenities with optional category filter."""
    query = db.query(Amenity)
    
    if category:
        query = query.filter(Amenity.category == category)
    
    amenities = query.offset(skip).limit(limit).all()
    return amenities

@router.get("/categories", response_model=List[str])
async def get_amenity_categories(db: Session = Depends(get_db)):
    """Get all unique amenity categories."""
    categories = db.query(Amenity.category).distinct().all()
    return [category[0] for category in categories if category[0]]

@router.get("/{amenity_id}", response_model=AmenityResponse)
async def get_amenity(
    amenity_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific amenity by ID."""
    amenity = db.query(Amenity).filter(Amenity.amenity_id == amenity_id).first()
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    return amenity

@router.post("/", response_model=AmenityResponse, status_code=status.HTTP_201_CREATED)
async def create_amenity(
    amenity_data: AmenityCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new amenity (admin only)."""
    # Check if amenity name already exists
    existing_amenity = db.query(Amenity).filter(
        Amenity.amenity_name == amenity_data.amenity_name
    ).first()
    
    if existing_amenity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amenity with this name already exists"
        )
    
    amenity = Amenity(**amenity_data.dict())
    db.add(amenity)
    db.commit()
    db.refresh(amenity)
    
    return amenity

@router.put("/{amenity_id}", response_model=AmenityResponse)
async def update_amenity(
    amenity_id: int,
    amenity_data: AmenityCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update an amenity (admin only)."""
    amenity = db.query(Amenity).filter(Amenity.amenity_id == amenity_id).first()
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    # Check if new name conflicts with existing amenity
    if amenity_data.amenity_name != amenity.amenity_name:
        existing_amenity = db.query(Amenity).filter(
            Amenity.amenity_name == amenity_data.amenity_name
        ).first()
        
        if existing_amenity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amenity with this name already exists"
            )
    
    update_data = amenity_data.dict()
    for field, value in update_data.items():
        setattr(amenity, field, value)
    
    db.commit()
    db.refresh(amenity)
    
    return amenity

@router.delete("/{amenity_id}", response_model=Message)
async def delete_amenity(
    amenity_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete an amenity (admin only)."""
    amenity = db.query(Amenity).filter(Amenity.amenity_id == amenity_id).first()
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    db.delete(amenity)
    db.commit()
    
    return {"message": "Amenity deleted successfully"} 