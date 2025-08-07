from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas import ViewCreate, ViewResponse, Message
from auth import require_admin
from db_models import View, User

router = APIRouter(prefix="/views", tags=["views"])

@router.get("/", response_model=List[ViewResponse])
async def get_views(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all property views."""
    views = db.query(View).offset(skip).limit(limit).all()
    return views

@router.get("/{view_id}", response_model=ViewResponse)
async def get_view(
    view_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific view by ID."""
    view = db.query(View).filter(View.view_id == view_id).first()
    
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="View not found"
        )
    
    return view

@router.post("/", response_model=ViewResponse, status_code=status.HTTP_201_CREATED)
async def create_view(
    view_data: ViewCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Create a new view type (admin only)."""
    # Check if view type already exists
    existing_view = db.query(View).filter(
        View.view_type == view_data.view_type
    ).first()
    
    if existing_view:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="View type already exists"
        )
    
    view = View(**view_data.dict())
    db.add(view)
    db.commit()
    db.refresh(view)
    
    return view

@router.put("/{view_id}", response_model=ViewResponse)
async def update_view(
    view_id: int,
    view_data: ViewCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a view type (admin only)."""
    view = db.query(View).filter(View.view_id == view_id).first()
    
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="View not found"
        )
    
    # Check if new view type conflicts with existing view
    if view_data.view_type != view.view_type:
        existing_view = db.query(View).filter(
            View.view_type == view_data.view_type
        ).first()
        
        if existing_view:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="View type already exists"
            )
    
    update_data = view_data.dict()
    for field, value in update_data.items():
        setattr(view, field, value)
    
    db.commit()
    db.refresh(view)
    
    return view

@router.delete("/{view_id}", response_model=Message)
async def delete_view(
    view_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a view type (admin only)."""
    view = db.query(View).filter(View.view_id == view_id).first()
    
    if not view:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="View not found"
        )
    
    db.delete(view)
    db.commit()
    
    return {"message": "View deleted successfully"} 