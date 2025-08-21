"""
Lead Management API Router

This module handles lead creation, management, and CREA API integration.
Automatically syncs crea_agent_key and office_key from AgentProfile.

Endpoints:
- POST /api/v1/leads/ - Create a new lead and submit to CREA
- GET /api/v1/leads/{lead_id} - Get lead details  
- PUT /api/v1/leads/{lead_id} - Update lead status and notes
- GET /api/v1/leads/agent/{agent_profile_id} - Get leads for specific agent
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from database import get_db
from db_models import Lead, AgentProfile, Property
from schemas import LeadCreate, LeadResponse, LeadUpdate, CREALeadSubmission
from auth import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/leads",
    tags=["Lead Management"],
    responses={404: {"description": "Not found"}},
)


def submit_lead_to_crea(lead: Lead, db: Session) -> bool:
    """
    Submit lead to CREA Lead API in background
    Updates lead.crea_submission_status when complete
    """
    try:
        from crea_api_client import crea_api
        
        # Prepare CREA API payload
        crea_payload = CREALeadSubmission(
            Culture=lead.culture,
            MemberKey=lead.crea_agent_key,
            ListingKey=lead.listing_key,
            SenderName=lead.sender_name,
            SenderEmailAddress=lead.sender_email_address,
            SenderPhoneNumber=int(lead.sender_phone_number) if lead.sender_phone_number else None,
            PreferredMethodContact=lead.preferred_method_contact,
            SenderPhoneExtension=lead.sender_phone_extension,
            Message=lead.message
        )
        
        logger.info(f"🚀 Submitting lead {lead.lead_id} to CREA for agent {lead.crea_agent_key}")
        
        # Submit to CREA API
        response = crea_api.create_lead(crea_payload.dict())
        
        if response:
            # Update lead with successful submission
            lead.crea_submission_status = 'submitted'
            lead.crea_lead_id = str(response.get('LeadId', ''))
            lead.crea_submitted_at = datetime.utcnow()
            lead.crea_submission_error = None
            
            logger.info(f"✅ Lead {lead.lead_id} successfully submitted to CREA. CREA Lead ID: {lead.crea_lead_id}")
        else:
            raise Exception("No response from CREA API")
            
    except Exception as e:
        # Update lead with failure status
        lead.crea_submission_status = 'failed'
        lead.crea_submission_error = str(e)
        
        logger.error(f"❌ Failed to submit lead {lead.lead_id} to CREA: {e}")
        
    finally:
        # Save the status update
        db.commit()
        
    return lead.crea_submission_status == 'submitted'


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new lead and automatically submit to CREA
    
    - **agent_profile_id**: Agent to assign lead to
    - **listing_key**: Property listing key from CREA
    - **culture**: Language preference (en-CA or fr-CA, defaults to en-CA)
    - **sender_name**: Lead's full name
    - **sender_email_address**: Lead's email
    - **message**: Lead's message to agent
    - **sender_phone_number**: Optional phone number
    - **preferred_method_contact**: email, phone, or text
    
    The system automatically:
    - Fetches crea_agent_key and office_key from AgentProfile
    - Submits lead to CREA API in background
    - Tracks submission status
    """
    
    try:
        # Get agent profile with CREA keys
        agent_profile = db.query(AgentProfile).filter(
            AgentProfile.profile_id == lead_data.agent_profile_id
        ).first()
        
        if not agent_profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent profile {lead_data.agent_profile_id} not found"
            )
        
        if not agent_profile.crea_agent_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent profile {lead_data.agent_profile_id} does not have a CREA agent key"
            )
        
        # Verify listing exists
        property_listing = db.query(Property).filter(
            Property.listing_key == lead_data.listing_key
        ).first()
        
        if not property_listing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property with listing_key {lead_data.listing_key} not found"
            )
        
        # Create lead with auto-populated CREA fields
        new_lead = Lead(
            # Auto-populated from AgentProfile
            agent_profile_id=lead_data.agent_profile_id,
            crea_agent_key=agent_profile.crea_agent_key,
            office_key=agent_profile.office_key,
            
            # Required CREA fields from user input
            culture=lead_data.culture,
            listing_key=lead_data.listing_key,
            sender_name=lead_data.sender_name,
            sender_email_address=lead_data.sender_email_address,
            message=lead_data.message,
            
            # Optional CREA fields
            sender_phone_number=lead_data.sender_phone_number,
            preferred_method_contact=lead_data.preferred_method_contact,
            sender_phone_extension=lead_data.sender_phone_extension,
            
            # Lead management fields
            lead_status='new',
            lead_source=lead_data.lead_source,
            lead_priority=lead_data.lead_priority,
            crea_submission_status='pending',
            
            # Lead qualification data
            budget_min=lead_data.budget_min,
            budget_max=lead_data.budget_max,
            desired_location=lead_data.desired_location,
            property_type_preference=lead_data.property_type_preference,
            timeline=lead_data.timeline,
            financing_pre_approved=lead_data.financing_pre_approved or False,
            notes=lead_data.notes,
            contact_attempts=0
        )
        
        db.add(new_lead)
        db.commit()
        db.refresh(new_lead)
        
        # Submit to CREA in background
        background_tasks.add_task(submit_lead_to_crea, new_lead, db)
        
        logger.info(f"✅ Created lead {new_lead.lead_id} for agent {agent_profile.crea_agent_key} on property {lead_data.listing_key}")
        
        return new_lead
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error creating lead: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create lead: {str(e)}"
        )


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get lead details by ID"""
    
    lead = db.query(Lead).options(
        joinedload(Lead.agent_profile)
    ).filter(Lead.lead_id == lead_id).first()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
    
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    lead_update: LeadUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update lead status, notes, and follow-up information"""
    
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead {lead_id} not found"
        )
    
    # Update fields that are provided
    update_data = lead_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(lead, field, value)
    
    # Increment contact attempts if status changes to contacted
    if lead_update.lead_status == 'contacted' and lead.lead_status != 'contacted':
        lead.contact_attempts += 1
        lead.last_contact_date = datetime.utcnow()
    
    db.commit()
    db.refresh(lead)
    
    logger.info(f"✅ Updated lead {lead_id}")
    return lead


@router.get("/agent/{agent_profile_id}", response_model=List[LeadResponse])
async def get_agent_leads(
    agent_profile_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all leads for a specific agent
    
    - **status**: Filter by lead status (new, contacted, qualified, converted, closed)
    - **priority**: Filter by priority (low, medium, high, urgent)
    - **limit**: Maximum number of leads to return
    - **offset**: Number of leads to skip
    """
    
    query = db.query(Lead).filter(Lead.agent_profile_id == agent_profile_id)
    
    if status:
        query = query.filter(Lead.lead_status == status)
    
    if priority:
        query = query.filter(Lead.lead_priority == priority)
    
    leads = query.order_by(desc(Lead.created_at)).offset(offset).limit(limit).all()
    
    return leads


@router.get("/", response_model=List[LeadResponse])
async def get_all_leads(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    agent_key: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all leads with optional filtering
    
    - **status**: Filter by lead status
    - **priority**: Filter by priority  
    - **agent_key**: Filter by CREA agent key
    - **limit**: Maximum number of leads to return
    - **offset**: Number of leads to skip
    """
    
    query = db.query(Lead)
    
    if status:
        query = query.filter(Lead.lead_status == status)
    
    if priority:
        query = query.filter(Lead.lead_priority == priority)
        
    if agent_key:
        query = query.filter(Lead.crea_agent_key == agent_key)
    
    leads = query.order_by(desc(Lead.created_at)).offset(offset).limit(limit).all()
    
    return leads
