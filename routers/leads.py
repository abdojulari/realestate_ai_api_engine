"""
Lead Management API Router

This module handles lead creation and management.
Automatically copies the agent key and office key from AgentProfile.

Endpoints:
- POST /api/v1/leads/ - Create a new lead
- GET /api/v1/leads/{lead_id} - Get lead details  
- PUT /api/v1/leads/{lead_id} - Update lead status and notes
- GET /api/v1/leads/agent/{agent_profile_id} - Get leads for specific agent
"""

import logging
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc

from database import get_db
from db_models import Lead, AgentProfile, Property
from schemas import LeadCreate, LeadResponse, LeadUpdate
from auth import get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/leads",
    tags=["Lead Management"],
    responses={404: {"description": "Not found"}},
)


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new lead.

    - **agent_profile_id**: Agent to assign the lead to
    - **listing_key**: Property listing key
    - **culture**: Language preference (en-CA or fr-CA, defaults to en-CA)
    - **sender_name**: Lead's full name
    - **sender_email_address**: Lead's email
    - **message**: Lead's message to the agent
    - **sender_phone_number**: Optional phone number
    - **preferred_method_contact**: email, phone, or text
    """
    
    try:
        # Get the assigned agent profile
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
                detail=f"Agent profile {lead_data.agent_profile_id} does not have an agent key"
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
        
        # Create the lead and copy the agent identifiers from the profile
        new_lead = Lead(
            # Auto-populated from AgentProfile
            agent_profile_id=lead_data.agent_profile_id,
            crea_agent_key=agent_profile.crea_agent_key,
            office_key=agent_profile.office_key,
            
            # Details supplied by the sender
            culture=lead_data.culture,
            listing_key=lead_data.listing_key,
            sender_name=lead_data.sender_name,
            sender_email_address=lead_data.sender_email_address,
            message=lead_data.message,
            
            # Optional contact details
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
        
        logger.info(f"Created lead {new_lead.lead_id} for agent {agent_profile.crea_agent_key} on property {lead_data.listing_key}")
        
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
    - **agent_key**: Filter by agent key
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
