"""
Daily Tips API Router
Admin-only endpoint for managing daily tips with images
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import uuid
import os
import shutil
from datetime import datetime

from database import get_db
from schemas import (
    DailyTipCreate, DailyTipUpdate, DailyTipResponse, DailyTipWithCreator, Message
)
from auth import require_admin, get_current_active_user
from db_models import DailyTip, User

router = APIRouter(prefix="/dailytips", tags=["daily-tips"])

# Directory for storing uploaded images
UPLOAD_DIR = "uploads/dailytips"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def require_admin_user(current_user: User = Depends(get_current_active_user)) -> User:
    """Ensure the current user is an admin"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin users can manage daily tips"
        )
    return current_user


@router.post("/", response_model=DailyTipResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_tip(
    tip_data: DailyTipCreate,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """Create a new daily tip (Admin only)"""
    try:
        # Create new daily tip
        daily_tip = DailyTip(
            title=tip_data.title,
            tip=tip_data.tip,
            images=tip_data.images or [],
            is_active=tip_data.is_active,
            display_order=tip_data.display_order,
            created_by=current_user.user_id
        )
        
        db.add(daily_tip)
        db.commit()
        db.refresh(daily_tip)
        
        # Convert to response format
        response_data = DailyTipResponse(
            tip_id=daily_tip.tip_id,
            title=daily_tip.title,
            tip=daily_tip.tip,
            images=daily_tip.images or [],
            is_active=daily_tip.is_active,
            display_order=daily_tip.display_order,
            created_by=str(daily_tip.created_by),
            created_at=daily_tip.created_at,
            updated_at=daily_tip.updated_at
        )
        
        return response_data
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating daily tip: {str(e)}"
        )


@router.get("/", response_model=List[DailyTipWithCreator])
async def get_daily_tips(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    active_only: bool = Query(True, description="Show only active tips"),
    include_creator: bool = Query(True, description="Include creator information"),
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """Get all daily tips (Admin only)"""
    try:
        query = db.query(DailyTip)
        
        if include_creator:
            query = query.options(joinedload(DailyTip.creator))
        
        if active_only:
            query = query.filter(DailyTip.is_active == True)
        
        # Order by display_order, then by created_at desc
        query = query.order_by(DailyTip.display_order.asc(), DailyTip.created_at.desc())
        
        tips = query.offset(skip).limit(limit).all()
        
        # Enrich with creator information if requested
        enriched_tips = []
        for tip in tips:
            tip_dict = {
                "tip_id": tip.tip_id,
                "title": tip.title,
                "tip": tip.tip,
                "images": tip.images or [],
                "is_active": tip.is_active,
                "display_order": tip.display_order,
                "created_by": str(tip.created_by),
                "created_at": tip.created_at,
                "updated_at": tip.updated_at,
            }
            
            if include_creator and tip.creator:
                tip_dict["creator"] = {
                    "user_id": str(tip.creator.user_id),
                    "first_name": tip.creator.first_name,
                    "last_name": tip.creator.last_name,
                    "email": tip.creator.email
                }
            
            enriched_tips.append(DailyTipWithCreator(**tip_dict))
        
        return enriched_tips
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching daily tips: {str(e)}"
        )


@router.get("/public", response_model=List[DailyTipResponse])
async def get_public_daily_tips(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get active daily tips for public consumption (No auth required)"""
    try:
        query = db.query(DailyTip).filter(
            DailyTip.is_active == True
        ).order_by(
            DailyTip.display_order.asc(), 
            DailyTip.created_at.desc()
        )
        
        tips = query.offset(skip).limit(limit).all()
        
        # Convert to response format
        response_tips = []
        for tip in tips:
            response_data = DailyTipResponse(
                tip_id=tip.tip_id,
                title=tip.title,
                tip=tip.tip,
                images=tip.images or [],
                is_active=tip.is_active,
                display_order=tip.display_order,
                created_by=str(tip.created_by),
                created_at=tip.created_at,
                updated_at=tip.updated_at
            )
            response_tips.append(response_data)
        
        return response_tips
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching public daily tips: {str(e)}"
        )


@router.get("/{tip_id}", response_model=DailyTipWithCreator)
async def get_daily_tip(
    tip_id: str,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """Get a specific daily tip by ID (Admin only)"""
    try:
        tip = db.query(DailyTip).options(
            joinedload(DailyTip.creator)
        ).filter(DailyTip.tip_id == tip_id).first()
        
        if not tip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily tip not found"
            )
        
        # Enrich with creator information
        tip_dict = {
            "tip_id": tip.tip_id,
            "title": tip.title,
            "tip": tip.tip,
            "images": tip.images or [],
            "is_active": tip.is_active,
            "display_order": tip.display_order,
            "created_by": str(tip.created_by),
            "created_at": tip.created_at,
            "updated_at": tip.updated_at,
        }
        
        if tip.creator:
            tip_dict["creator"] = {
                "user_id": str(tip.creator.user_id),
                "first_name": tip.creator.first_name,
                "last_name": tip.creator.last_name,
                "email": tip.creator.email
            }
        
        return DailyTipWithCreator(**tip_dict)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching daily tip: {str(e)}"
        )


@router.put("/{tip_id}", response_model=DailyTipResponse)
async def update_daily_tip(
    tip_id: str,
    tip_data: DailyTipUpdate,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """Update a daily tip (Admin only)"""
    try:
        tip = db.query(DailyTip).filter(DailyTip.tip_id == tip_id).first()
        
        if not tip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily tip not found"
            )
        
        # Update only provided fields
        update_data = tip_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(tip, field, value)
        
        tip.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(tip)
        
        # Convert to response format
        response_data = DailyTipResponse(
            tip_id=tip.tip_id,
            title=tip.title,
            tip=tip.tip,
            images=tip.images or [],
            is_active=tip.is_active,
            display_order=tip.display_order,
            created_by=str(tip.created_by),
            created_at=tip.created_at,
            updated_at=tip.updated_at
        )
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating daily tip: {str(e)}"
        )


@router.delete("/{tip_id}", response_model=Message)
async def delete_daily_tip(
    tip_id: str,
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a daily tip (Admin only)"""
    try:
        tip = db.query(DailyTip).filter(DailyTip.tip_id == tip_id).first()
        
        if not tip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily tip not found"
            )
        
        # Clean up associated images
        if tip.images:
            for image_url in tip.images:
                # Extract filename and try to delete from uploads directory
                if image_url.startswith("/uploads/"):
                    image_path = image_url[1:]  # Remove leading slash
                    if os.path.exists(image_path):
                        try:
                            os.remove(image_path)
                        except Exception as e:
                            print(f"Warning: Could not delete image {image_path}: {e}")
        
        db.delete(tip)
        db.commit()
        
        return Message(message="Daily tip deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting daily tip: {str(e)}"
        )


@router.post("/upload-image")
async def upload_tip_image(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin_user)
):
    """Upload an image for daily tips (Admin only)"""
    try:
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed."
            )
        
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024  # 5MB in bytes
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large. Maximum size is 5MB."
            )
        
        # Generate unique filename
        file_extension = file.filename.split(".")[-1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
        
        # Return the URL path
        image_url = f"/uploads/dailytips/{unique_filename}"
        
        return {
            "message": "Image uploaded successfully",
            "image_url": image_url,
            "filename": unique_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading image: {str(e)}"
        )


@router.post("/reorder", response_model=Message)
async def reorder_daily_tips(
    tip_orders: List[dict],  # [{"tip_id": "...", "display_order": 1}, ...]
    current_user: User = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """Reorder daily tips by updating display_order (Admin only)"""
    try:
        for tip_order in tip_orders:
            tip_id = tip_order.get("tip_id")
            display_order = tip_order.get("display_order")
            
            if not tip_id or display_order is None:
                continue
                
            tip = db.query(DailyTip).filter(DailyTip.tip_id == tip_id).first()
            if tip:
                tip.display_order = display_order
                tip.updated_at = datetime.utcnow()
        
        db.commit()
        return Message(message="Daily tips reordered successfully")
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reordering daily tips: {str(e)}"
        )
