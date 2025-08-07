from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from database import get_db
import schemas
from auth import get_current_active_user
from db_models import Notification
from notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])

@router.get("/", response_model=schemas.NotificationsSummary)
async def get_my_notifications(
    unread_only: Optional[bool] = Query(False, description="Get only unread notifications"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get notifications for the current user."""
    
    result = NotificationService.get_user_notifications(
        db=db,
        user_id=str(current_user.user_id),
        unread_only=unread_only,
        limit=limit,
        skip=skip
    )
    
    return schemas.NotificationsSummary(
        total_count=result["total_count"],
        unread_count=result["unread_count"],
        notifications=[schemas.NotificationResponse.from_orm(n) for n in result["notifications"]]
    )

@router.put("/{notification_id}/mark-read", response_model=schemas.Message)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark a specific notification as read."""
    
    success = NotificationService.mark_notification_as_read(
        db=db,
        notification_id=str(notification_id),
        user_id=str(current_user.user_id)
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return schemas.Message(message="Notification marked as read")

@router.put("/mark-all-read", response_model=schemas.Message)
async def mark_all_notifications_read(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read for the current user."""
    
    # Update all unread notifications for this user
    db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == False
    ).update({"is_read": True})
    
    db.commit()
    
    return schemas.Message(message="All notifications marked as read")

@router.get("/stats", response_model=dict)
async def get_notification_stats(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get notification statistics for the current user."""
    
    stats = NotificationService.get_notification_stats(
        db=db,
        user_id=str(current_user.user_id)
    )
    
    return stats

@router.delete("/{notification_id}", response_model=schemas.Message)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a specific notification."""
    
    notification = db.query(Notification).filter(
        Notification.notification_id == notification_id,
        Notification.user_id == current_user.user_id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    
    return schemas.Message(message="Notification deleted successfully")

@router.get("/unread-count", response_model=dict)
async def get_unread_count(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Get count of unread notifications for the current user."""
    
    unread_count = db.query(Notification).filter(
        Notification.user_id == current_user.user_id,
        Notification.is_read == False
    ).count()
    
    return {"unread_count": unread_count} 