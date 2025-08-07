from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas import SavedSearchCreate, SavedSearchResponse, Message
from auth import require_customer_or_above
from db_models import SavedSearch, User

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])

@router.get("/", response_model=List[SavedSearchResponse])
async def get_user_saved_searches(
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Get all saved searches for the current user."""
    saved_searches = db.query(SavedSearch).filter(
        SavedSearch.user_id == current_user.user_id
    ).order_by(SavedSearch.created_at.desc()).all()
    
    return saved_searches

@router.get("/{search_id}", response_model=SavedSearchResponse)
async def get_saved_search(
    search_id: str,
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Get a specific saved search by ID."""
    saved_search = db.query(SavedSearch).filter(
        SavedSearch.search_id == search_id,
        SavedSearch.user_id == current_user.user_id
    ).first()
    
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    return saved_search

@router.post("/", response_model=SavedSearchResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_search(
    search_data: SavedSearchCreate,
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Create a new saved search."""
    saved_search = SavedSearch(
        **search_data.dict(),
        user_id=current_user.user_id
    )
    
    db.add(saved_search)
    db.commit()
    db.refresh(saved_search)
    
    return saved_search

@router.put("/{search_id}", response_model=SavedSearchResponse)
async def update_saved_search(
    search_id: str,
    search_data: SavedSearchCreate,
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Update a saved search."""
    saved_search = db.query(SavedSearch).filter(
        SavedSearch.search_id == search_id,
        SavedSearch.user_id == current_user.user_id
    ).first()
    
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    update_data = search_data.dict()
    for field, value in update_data.items():
        setattr(saved_search, field, value)
    
    db.commit()
    db.refresh(saved_search)
    
    return saved_search

@router.delete("/{search_id}", response_model=Message)
async def delete_saved_search(
    search_id: str,
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Delete a saved search."""
    saved_search = db.query(SavedSearch).filter(
        SavedSearch.search_id == search_id,
        SavedSearch.user_id == current_user.user_id
    ).first()
    
    if not saved_search:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved search not found"
        )
    
    db.delete(saved_search)
    db.commit()
    
    return {"message": "Saved search deleted successfully"} 