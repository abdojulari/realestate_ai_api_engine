from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from database import get_db
from schemas import (
    SchoolCreate, SchoolUpdate, SchoolResponse, Message
)
from auth import get_current_active_user
from db_models import User, School, Property

router = APIRouter(prefix="/schools", tags=["Schools"])


@router.get("/", response_model=List[SchoolResponse])
async def get_schools(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    property_id: Optional[uuid.UUID] = None,
    school_type: Optional[str] = None,
    max_distance: Optional[float] = Query(None, ge=0, description="Maximum distance in km"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="Minimum school score"),
    is_assigned: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get schools with optional filtering."""
    query = db.query(School)
    
    if property_id:
        query = query.filter(School.property_id == property_id)
    
    if school_type:
        query = query.filter(School.type == school_type)
    
    if max_distance is not None:
        query = query.filter(School.distance <= max_distance)
    
    if min_score is not None:
        query = query.filter(School.score >= min_score)
    
    if is_assigned is not None:
        query = query.filter(School.is_assigned == is_assigned)
    
    schools = query.order_by(School.distance).offset(skip).limit(limit).all()
    
    # Convert database model to response format
    response_data = []
    for school in schools:
        school_data = SchoolResponse(
            id=school.id,
            property_id=school.property_id,
            name=school.name,
            type=school.type,
            grades=school.grades,
            distance=float(school.distance),
            address=school.address,
            school_board=school.school_board,
            score=float(school.score) if school.score else None,
            is_assigned=school.is_assigned,
            postal_code=school.postal_code,
            lat=float(school.lat),
            lng=float(school.lng),
            created_at=school.created_at,
            updated_at=school.updated_at
        )
        response_data.append(school_data)
    
    return response_data


@router.get("/{school_id}", response_model=SchoolResponse)
async def get_school(
    school_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific school by ID."""
    school = db.query(School).filter(School.id == school_id).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    return SchoolResponse(
        id=school.id,
        property_id=school.property_id,
        name=school.name,
        type=school.type,
        grades=school.grades,
        distance=float(school.distance),
        address=school.address,
        school_board=school.school_board,
        score=float(school.score) if school.score else None,
        is_assigned=school.is_assigned,
        postal_code=school.postal_code,
        lat=float(school.lat),
        lng=float(school.lng),
        created_at=school.created_at,
        updated_at=school.updated_at
    )


@router.post("/", response_model=SchoolResponse)
async def create_school(
    school_data: SchoolCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new school entry."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == school_data.property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Create school
    db_school = School(
        property_id=school_data.property_id,
        name=school_data.name,
        type=school_data.type,
        grades=school_data.grades,
        distance=school_data.distance,
        address=school_data.address,
        school_board=school_data.school_board,
        score=school_data.score,
        is_assigned=school_data.is_assigned,
        postal_code=school_data.postal_code,
        lat=school_data.lat,
        lng=school_data.lng
    )
    
    db.add(db_school)
    db.commit()
    db.refresh(db_school)
    
    return SchoolResponse(
        id=db_school.id,
        property_id=db_school.property_id,
        name=db_school.name,
        type=db_school.type,
        grades=db_school.grades,
        distance=float(db_school.distance),
        address=db_school.address,
        school_board=db_school.school_board,
        score=float(db_school.score) if db_school.score else None,
        is_assigned=db_school.is_assigned,
        postal_code=db_school.postal_code,
        lat=float(db_school.lat),
        lng=float(db_school.lng),
        created_at=db_school.created_at,
        updated_at=db_school.updated_at
    )


@router.put("/{school_id}", response_model=SchoolResponse)
async def update_school(
    school_id: int,
    school_data: SchoolUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a school entry."""
    school = db.query(School).filter(School.id == school_id).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # Update fields if provided
    update_data = school_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(school, field, value)
    
    db.commit()
    db.refresh(school)
    
    return SchoolResponse(
        id=school.id,
        property_id=school.property_id,
        name=school.name,
        type=school.type,
        grades=school.grades,
        distance=float(school.distance),
        address=school.address,
        school_board=school.school_board,
        score=float(school.score) if school.score else None,
        is_assigned=school.is_assigned,
        postal_code=school.postal_code,
        lat=float(school.lat),
        lng=float(school.lng),
        created_at=school.created_at,
        updated_at=school.updated_at
    )


@router.delete("/{school_id}", response_model=Message)
async def delete_school(
    school_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a school entry."""
    school = db.query(School).filter(School.id == school_id).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    db.delete(school)
    db.commit()
    
    return Message(message="School deleted successfully")


@router.get("/property/{property_id}", response_model=List[SchoolResponse])
async def get_schools_by_property(
    property_id: uuid.UUID,
    school_type: Optional[str] = None,
    max_distance: Optional[float] = Query(None, ge=0, description="Maximum distance in km"),
    min_score: Optional[float] = Query(None, ge=0, le=10, description="Minimum school score"),
    is_assigned: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get all schools for a specific property."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    query = db.query(School).filter(School.property_id == property_id)
    
    if school_type:
        query = query.filter(School.type == school_type)
    
    if max_distance is not None:
        query = query.filter(School.distance <= max_distance)
    
    if min_score is not None:
        query = query.filter(School.score >= min_score)
    
    if is_assigned is not None:
        query = query.filter(School.is_assigned == is_assigned)
    
    schools = query.order_by(School.distance).all()
    
    # Convert to response format
    response_data = []
    for school in schools:
        school_data = SchoolResponse(
            id=school.id,
            property_id=school.property_id,
            name=school.name,
            type=school.type,
            grades=school.grades,
            distance=float(school.distance),
            address=school.address,
            school_board=school.school_board,
            score=float(school.score) if school.score else None,
            is_assigned=school.is_assigned,
            postal_code=school.postal_code,
            lat=float(school.lat),
            lng=float(school.lng),
            created_at=school.created_at,
            updated_at=school.updated_at
        )
        response_data.append(school_data)
    
    return response_data


@router.get("/property/{property_id}/assigned", response_model=List[SchoolResponse])
async def get_assigned_schools_by_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get assigned schools for a specific property."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    schools = db.query(School).filter(
        School.property_id == property_id,
        School.is_assigned == True
    ).order_by(School.type, School.distance).all()
    
    # Convert to response format
    response_data = []
    for school in schools:
        school_data = SchoolResponse(
            id=school.id,
            property_id=school.property_id,
            name=school.name,
            type=school.type,
            grades=school.grades,
            distance=float(school.distance),
            address=school.address,
            school_board=school.school_board,
            score=float(school.score) if school.score else None,
            is_assigned=school.is_assigned,
            postal_code=school.postal_code,
            lat=float(school.lat),
            lng=float(school.lng),
            created_at=school.created_at,
            updated_at=school.updated_at
        )
        response_data.append(school_data)
    
    return response_data