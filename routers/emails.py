from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel, EmailStr
import logging

from database import get_db
from auth import get_current_user_optional
from db_models import User
from emailer import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])

# Email Schemas
class EmailRequest(BaseModel):
    """Schema for sending a single email"""
    to_email: EmailStr
    subject: str
    body: str
    is_html: bool = True

class BulkEmailRequest(BaseModel):
    """Schema for sending bulk emails"""
    to_emails: List[EmailStr]
    subject: str
    body: str
    is_html: bool = True

class EmailResponse(BaseModel):
    """Response schema for email operations"""
    success: bool
    message: str
    sent_count: Optional[int] = None
    failed_count: Optional[int] = None
    failed_emails: Optional[List[str]] = None

@router.post("/send", response_model=EmailResponse)
async def send_single_email(
    email_request: EmailRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Send a single email server-side.
    
    This endpoint allows sending emails directly from the server for various purposes:
    - Notifications
    - Alerts
    - Marketing emails
    - System messages
    - etc.
    """
    try:
        logger.info(f"Sending email to {email_request.to_email} with subject: {email_request.subject}")
        
        # Send the email using the existing emailer
        await send_email(
            to_email=email_request.to_email,
            subject=email_request.subject,
            body=email_request.body,
            is_html=email_request.is_html
        )
        
        return EmailResponse(
            success=True,
            message=f"Email sent successfully to {email_request.to_email}",
            sent_count=1
        )
        
    except Exception as e:
        logger.error(f"Failed to send email to {email_request.to_email}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )

@router.post("/send-bulk", response_model=EmailResponse)
async def send_bulk_emails(
    bulk_email_request: BulkEmailRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Send bulk emails server-side.
    
    This endpoint allows sending the same email to multiple recipients:
    - Newsletters
    - Announcements
    - Marketing campaigns
    - System-wide notifications
    """
    try:
        logger.info(f"Sending bulk email to {len(bulk_email_request.to_emails)} recipients")
        
        sent_count = 0
        failed_count = 0
        failed_emails = []
        
        for email in bulk_email_request.to_emails:
            try:
                await send_email(
                    to_email=email,
                    subject=bulk_email_request.subject,
                    body=bulk_email_request.body,
                    is_html=bulk_email_request.is_html
                )
                sent_count += 1
                logger.debug(f"Email sent successfully to {email}")
                
            except Exception as e:
                failed_count += 1
                failed_emails.append(email)
                logger.error(f"Failed to send email to {email}: {str(e)}")
        
        return EmailResponse(
            success=sent_count > 0,
            message=f"Bulk email completed. Sent: {sent_count}, Failed: {failed_count}",
            sent_count=sent_count,
            failed_count=failed_count,
            failed_emails=failed_emails if failed_emails else None
        )
        
    except Exception as e:
        logger.error(f"Bulk email operation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Bulk email operation failed: {str(e)}"
        )

class TemplateEmailRequest(BaseModel):
    """Schema for template email requests"""
    to_email: EmailStr
    template_name: str
    template_data: dict
    subject: str

@router.post("/send-template", response_model=EmailResponse)
async def send_template_email(
    template_request: TemplateEmailRequest,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Send an email using a predefined template.
    
    Available templates:
    - welcome: Welcome new users
    - notification: General notifications
    - alert: Important alerts
    - marketing: Marketing content
    """
    try:
        logger.info(f"Sending template email '{template_request.template_name}' to {template_request.to_email}")
        
        # Define email templates
        templates = {
            "welcome": """
                <h2>Welcome to Real Estate AI! 🏠</h2>
                <p>Hi {name},</p>
                <p>Welcome to our platform! We're excited to help you find your perfect property.</p>
                <p>Get started by exploring our AI-powered property recommendations.</p>
                <p>Best regards,<br>The Real Estate AI Team</p>
            """,
            "notification": """
                <h2>Notification</h2>
                <p>Hi {name},</p>
                <p>{message}</p>
                <p>Best regards,<br>Real Estate AI Team</p>
            """,
            "alert": """
                <h2>🚨 Important Alert</h2>
                <p>Hi {name},</p>
                <p><strong>{alert_message}</strong></p>
                <p>Please take action as needed.</p>
                <p>Best regards,<br>Real Estate AI Team</p>
            """,
            "marketing": """
                <h2>{title}</h2>
                <p>Hi {name},</p>
                <p>{content}</p>
                <p>{call_to_action}</p>
                <p>Best regards,<br>Real Estate AI Team</p>
            """
        }
        
        if template_request.template_name not in templates:
            raise HTTPException(
                status_code=400,
                detail=f"Template '{template_request.template_name}' not found. Available templates: {list(templates.keys())}"
            )
        
        # Render template with data
        template = templates[template_request.template_name]
        try:
            email_body = template.format(**template_request.template_data)
        except KeyError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Missing template data: {str(e)}"
            )
        
        # Send the email
        await send_email(
            to_email=template_request.to_email,
            subject=template_request.subject,
            body=email_body,
            is_html=True
        )
        
        return EmailResponse(
            success=True,
            message=f"Template email '{template_request.template_name}' sent successfully to {template_request.to_email}",
            sent_count=1
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send template email to {template_request.to_email}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send template email: {str(e)}"
        )

@router.get("/test")
async def test_email_configuration():
    """
    Test the email configuration without sending an actual email.
    
    This endpoint checks if SMTP is properly configured.
    """
    import os
    
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_hostname = os.getenv("SMTP_HOSTNAME", "smtp.gmail.com")
    smtp_port = os.getenv("SMTP_PORT", "587")
    
    config_status = {
        "smtp_configured": bool(smtp_username and smtp_password),
        "smtp_hostname": smtp_hostname,
        "smtp_port": smtp_port,
        "smtp_username": smtp_username if smtp_username else "Not configured"
    }
    
    return {
        "message": "Email configuration status",
        "config": config_status,
        "ready_to_send": config_status["smtp_configured"]
    }
