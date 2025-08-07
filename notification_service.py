#!/usr/bin/env python3

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import SessionLocal
from db_models import Notification, User, Property, ClientAgentRelationship
from emailer import send_email  # Assuming this exists from the original code
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for managing notifications and email alerts."""
    
    @staticmethod
    async def create_notification(
        db: Session,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        send_email: bool = True
    ) -> Notification:
        """Create a new notification and optionally send email."""
        
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            data=data or {}
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        # Send email notification if requested
        if send_email:
            await NotificationService.send_email_notification(notification, db)
        
        return notification
    
    @staticmethod
    async def send_email_notification(notification: Notification, db: Session):
        """Send email for a notification."""
        try:
            user = db.query(User).filter(User.user_id == notification.user_id).first()
            if not user or not user.email:
                logger.warning(f"Cannot send email for notification {notification.notification_id}: User not found or no email")
                return
            
            # Send email using the existing emailer
            await send_email(
                to_email=user.email,
                subject=notification.title,
                body=notification.message,
                is_html=True
            )
            
            # Mark email as sent
            notification.is_email_sent = True
            notification.email_sent_at = func.now()
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    @staticmethod
    async def notify_agent_of_client_interest(
        db: Session,
        agent_id: str,
        client_id: str,
        property_id: Optional[str] = None,
        message: Optional[str] = None
    ):
        """Notify agent when a client shows interest in representation."""
        
        client = db.query(User).filter(User.user_id == client_id).first()
        property_obj = None
        if property_id:
            property_obj = db.query(Property).filter(Property.property_id == property_id).first()
        
        title = f"New Client Interest from {client.full_name if client else 'Unknown Client'}"
        
        notification_message = f"""
        <h3>New Client Representation Request</h3>
        <p><strong>Client:</strong> {client.full_name if client else 'Unknown'}</p>
        <p><strong>Email:</strong> {client.email if client else 'Unknown'}</p>
        <p><strong>Phone:</strong> {client.phone if client and client.phone else 'Not provided'}</p>
        """
        
        if property_obj:
            notification_message += f"""
            <p><strong>Property of Interest:</strong> {property_obj.title}</p>
            <p><strong>Address:</strong> {property_obj.address}, {property_obj.city}</p>
            <p><strong>Price:</strong> ${property_obj.price:,.2f}</p>
            """
        
        if message:
            notification_message += f"<p><strong>Client Message:</strong> {message}</p>"
        
        notification_message += """
        <p>Please log into your dashboard to respond to this client's request.</p>
        """
        
        data = {
            "client_id": client_id,
            "property_id": property_id,
            "client_message": message,
            "action_required": "respond_to_client_request"
        }
        
        await NotificationService.create_notification(
            db=db,
            user_id=agent_id,
            notification_type="client_request",
            title=title,
            message=notification_message,
            data=data,
            send_email=True
        )
    
    @staticmethod
    async def notify_client_of_agent_response(
        db: Session,
        client_id: str,
        agent_id: str,
        status: str,
        message: Optional[str] = None
    ):
        """Notify client when agent responds to representation request."""
        
        agent = db.query(User).filter(User.user_id == agent_id).first()
        
        if status == "active":
            title = f"Agent {agent.full_name} Accepted Your Request!"
            notification_message = f"""
            <h3>Great News! Your representation request has been accepted.</h3>
            <p><strong>Agent:</strong> {agent.full_name}</p>
            <p><strong>Email:</strong> {agent.email}</p>
            <p><strong>Phone:</strong> {agent.phone if agent.phone else 'Will be provided'}</p>
            """
        else:
            title = f"Update on Your Representation Request"
            notification_message = f"""
            <h3>Your representation request status has been updated.</h3>
            <p><strong>Agent:</strong> {agent.full_name}</p>
            <p><strong>Status:</strong> {status.title()}</p>
            """
        
        if message:
            notification_message += f"<p><strong>Agent's Message:</strong> {message}</p>"
        
        data = {
            "agent_id": agent_id,
            "relationship_status": status,
            "agent_message": message
        }
        
        await NotificationService.create_notification(
            db=db,
            user_id=client_id,
            notification_type="agent_response",
            title=title,
            message=notification_message,
            data=data,
            send_email=True
        )
    
    @staticmethod
    async def notify_property_interest(
        db: Session,
        agent_id: str,
        client_id: str,
        property_id: str,
        interest_level: str = "interested"
    ):
        """Notify agent when their client shows interest in a property."""
        
        client = db.query(User).filter(User.user_id == client_id).first()
        property_obj = db.query(Property).filter(Property.property_id == property_id).first()
        
        if not client or not property_obj:
            return
        
        title = f"Client Interest: {property_obj.title}"
        
        notification_message = f"""
        <h3>Your client {client.full_name} is interested in a property</h3>
        <p><strong>Property:</strong> {property_obj.title}</p>
        <p><strong>Address:</strong> {property_obj.address}, {property_obj.city}</p>
        <p><strong>Price:</strong> ${property_obj.price:,.2f}</p>
        <p><strong>Interest Level:</strong> {interest_level.title()}</p>
        <p><strong>Client:</strong> {client.full_name} ({client.email})</p>
        """
        
        data = {
            "client_id": client_id,
            "property_id": property_id,
            "interest_level": interest_level,
            "action_suggested": "contact_client_about_property"
        }
        
        await NotificationService.create_notification(
            db=db,
            user_id=agent_id,
            notification_type="property_interest",
            title=title,
            message=notification_message,
            data=data,
            send_email=True
        )
    
    @staticmethod
    def mark_notification_as_read(db: Session, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read."""
        notification = db.query(Notification).filter(
            Notification.notification_id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if notification:
            notification.is_read = True
            notification.read_at = func.now()
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_user_notifications(
        db: Session,
        user_id: str,
        unread_only: bool = False,
        limit: int = 50,
        skip: int = 0
    ) -> Dict[str, Any]:
        """Get notifications for a user."""
        query = db.query(Notification).filter(Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.is_read == False)
        
        total_count = query.count()
        unread_count = db.query(Notification).filter(
            Notification.user_id == user_id,
            Notification.is_read == False
        ).count()
        
        notifications = query.order_by(
            Notification.created_at.desc()
        ).offset(skip).limit(limit).all()
        
        return {
            "total_count": total_count,
            "unread_count": unread_count,
            "notifications": notifications
        }
    
    @staticmethod
    def get_notification_stats(db: Session, user_id: str) -> Dict[str, int]:
        """Get notification statistics for a user."""
        stats = db.query(
            Notification.type,
            func.count(Notification.notification_id).label('count'),
            func.count(func.nullif(Notification.is_read, True)).label('unread_count')
        ).filter(
            Notification.user_id == user_id
        ).group_by(Notification.type).all()
        
        return {
            stat.type: {
                "total": stat.count,
                "unread": stat.unread_count
            }
            for stat in stats
        } 