from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional
from decimal import Decimal
import uuid
import asyncio
from datetime import datetime, timedelta
from functools import wraps

from database import get_db
import schemas
from schemas import (
    PropertyCreate, PropertyUpdate, PropertyResponse, PropertySearchFilters,
    Message, PaginatedResponse, CREAAgentProfileResponse, CREAOfficeResponse
)
from auth import (
    get_current_active_user, require_agent_or_admin, get_current_user_optional,
    require_customer_or_above
)
from db_models import Property, User, PropertyType, Amenity, View, PropertyViewHistory, PropertyImage, AgentProfile, Office

router = APIRouter(prefix="/properties", tags=["properties"])

# Cache to track last CREA sync time to prevent excessive API calls  
_last_crea_sync_cache = {}
CREA_SYNC_COOLDOWN_MINUTES = 60  # Only sync CREA every 60 minutes max

async def _ensure_fresh_crea_data(db: Session):
    """
    Ensure CREA property data is fresh, sync if needed (with cooldown)
    """
    try:
        now = datetime.now()
        cache_key = "crea_sync"
        
        # Check if we've synced recently (cooldown period)
        if cache_key in _last_crea_sync_cache:
            last_sync = _last_crea_sync_cache[cache_key]
            time_since_sync = (now - last_sync).total_seconds() / 60
            if time_since_sync < CREA_SYNC_COOLDOWN_MINUTES:
                return  # Skip sync, too recent
        
        # Check if we need to sync based on last_property_sync.json
        import os
        import json
        
        last_sync_file = "last_property_sync.json"
        needs_sync = True
        
        if os.path.exists(last_sync_file):
            try:
                with open(last_sync_file, 'r') as f:
                    data = json.load(f)
                    last_sync_str = data.get('last_sync')
                    if last_sync_str:
                        last_sync_time = datetime.fromisoformat(last_sync_str)
                        # Check if last sync was more than 24 hours ago
                        hours_since_sync = (now - last_sync_time).total_seconds() / 3600
                        needs_sync = hours_since_sync >= 24
            except Exception as e:
                print(f"⚠️ Could not read last sync file: {e}")
        
        # If sync needed, trigger background CREA sync
        if needs_sync:
            # Start sync in true background - don't await it!
            asyncio.create_task(_background_crea_sync())
            
            # Update cache immediately to prevent duplicate syncs
            _last_crea_sync_cache[cache_key] = now
            
    except Exception as e:
        print(f"⚠️ Auto CREA sync failed: {e}")
        # Don't fail the API call if sync fails


async def _background_crea_sync():
    """
    Background CREA property sync task
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_crea_sync)
        print(f"✅ Background CREA sync completed")
    except Exception as e:
        print(f"❌ Background CREA sync error: {e}")


def _run_crea_sync():
    """
    Run the CREA property sync (synchronous version for executor)
    """
    try:
        # Import the PropertyReplicationSyncer class
        import sys
        import os
        from datetime import datetime, timedelta
        
        # Import the syncer class
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # Import the PropertyReplicationSyncer from daily_property_replication_sync
        from daily_property_replication_sync import PropertyReplicationSyncer
        
        # Create syncer instance
        syncer = PropertyReplicationSyncer(dry_run=False)
        
        # Get the last sync timestamp or use yesterday as default
        since_date = syncer.get_last_sync_timestamp()
        
        # Run incremental sync
        stats = syncer.sync_properties(since_date, limit=None)
        
        print(f"📊 CREA Sync Results: {stats['new_properties']} new, {stats['updated_properties']} updated")
        
    except Exception as e:
        print(f"❌ CREA sync execution error: {e}")
        import traceback
        print(traceback.format_exc())


def populate_agent_office_data(property_obj: Property, db: Session) -> dict:
    """
    Populate agent and office data for a property response
    """
    property_dict = {
        # Convert SQLAlchemy object to dict
        **{c.name: getattr(property_obj, c.name) for c in property_obj.__table__.columns}
    }
    
    # Fetch agent data if listing_agent_id exists
    if property_obj.listing_agent_id:
        agent = db.query(AgentProfile).filter(
            AgentProfile.crea_agent_key == property_obj.listing_agent_id
        ).first()
        
        if agent:
            property_dict['listing_agent'] = {
                'profile_id': agent.profile_id,
                'crea_agent_key': agent.crea_agent_key,
                'first_name': agent.first_name,
                'last_name': agent.last_name,
                'middle_name': agent.middle_name,
                'agent_email': agent.agent_email,
                'agent_phone': agent.agent_phone,
                'agent_mobile': agent.agent_mobile,
                'agency_name': agent.agency_name,
                'license_number': agent.license_number,
                'member_designation': agent.member_designation,
                'member_status': agent.member_status,
                'languages': agent.languages,
                'specialization': agent.specialization,
                'experience': agent.experience,
                'bio': agent.bio,
                'rating': agent.rating,
                'city': agent.city,
                'province': agent.province,
            }
    
    # Fetch office data if listing_office_id exists
    if property_obj.listing_office_id:
        office = db.query(Office).filter(
            Office.crea_office_key == property_obj.listing_office_id
        ).first()
        
        if office:
            property_dict['listing_office'] = {
                'office_id': office.office_id,
                'crea_office_key': office.crea_office_key,
                'office_name': office.office_name,
                'office_phone': office.office_phone,
                'office_email': office.office_email,
                'office_website': office.office_website,
                'office_address': office.office_address,
                'office_city': office.office_city,
                'office_province': office.office_province,
                'office_postal_code': office.office_postal_code,
                'office_country': office.office_country,
                'office_type': office.office_type,
                'office_status': office.office_status,
            }
    
    return property_dict

@router.post("/", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
async def create_property(
    property_data: PropertyCreate,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Create a new property (agents and admins only)."""
    property_dict = property_data.dict()
    
    # Convert images list to JSONB format if provided
    if property_dict.get('images'):
        property_dict['images'] = property_dict['images']
    
    property_obj = Property(**property_dict)
    db.add(property_obj)
    db.commit()
    db.refresh(property_obj)
    
    return property_obj

@router.get("/", response_model=List[PropertyResponse])
async def get_properties(
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, description="Limit results (optional, use None for unlimited map view)"),
    city: Optional[str] = None,
    province: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    min_bedrooms: Optional[int] = None,
    max_bedrooms: Optional[int] = None,
    min_bathrooms: Optional[Decimal] = None,
    max_bathrooms: Optional[Decimal] = None,
    min_square_feet: Optional[int] = None,
    max_square_feet: Optional[int] = None,
    property_type_id: Optional[int] = None,
    has_garage: Optional[bool] = None,
    has_basement: Optional[bool] = None,
    status: Optional[str] = Query('available'),
    is_new: Optional[bool] = None,
    auto_sync: bool = Query(False, description="Automatically sync CREA data if stale"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Get properties with filtering options.
    Set auto_sync=true to trigger background CREA sync if needed.
    """
    # Simple auto-sync check (only if explicitly requested)
    if auto_sync:
        try:
            import subprocess
            print(f"🔄 Starting CREA sync in background...")
            subprocess.Popen([
                'python', 'daily_property_replication_sync.py'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"✅ CREA sync started")
        except Exception as e:
            print(f"⚠️ Could not start sync: {e}")
    
    query = db.query(Property).options(joinedload(Property.property_type))
    
    # Apply filters
    filters = []
    
    if city:
        filters.append(Property.city.ilike(f"%{city}%"))
    if province:
        filters.append(Property.province.ilike(f"%{province}%"))
    if min_price is not None:
        filters.append(Property.price >= min_price)
    if max_price is not None:
        filters.append(Property.price <= max_price)
    if min_bedrooms is not None:
        filters.append(Property.bedrooms >= min_bedrooms)
    if max_bedrooms is not None:
        filters.append(Property.bedrooms <= max_bedrooms)
    if min_bathrooms is not None:
        filters.append(Property.bathrooms >= min_bathrooms)
    if max_bathrooms is not None:
        filters.append(Property.bathrooms <= max_bathrooms)
    if min_square_feet is not None:
        filters.append(Property.square_feet >= min_square_feet)
    if max_square_feet is not None:
        filters.append(Property.square_feet <= max_square_feet)
    if property_type_id is not None:
        filters.append(Property.property_type_id == property_type_id)
    if has_garage is not None:
        filters.append(Property.has_garage == has_garage)
    if has_basement is not None:
        filters.append(Property.has_basement == has_basement)
    if status:
        filters.append(Property.status == status)
    if is_new is not None:
        filters.append(Property.is_new == is_new)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Order by newest first
    query = query.order_by(Property.created_at.desc())
    
    # Apply offset
    query = query.offset(skip)
    
    # Apply limit only if specified (for map views, allow unlimited)
    if limit is not None:
        query = query.limit(limit)
    
    properties = query.all()
    
    # Populate agent and office data for each property
    enriched_properties = []
    for prop in properties:
        enriched_prop_data = populate_agent_office_data(prop, db)
        enriched_properties.append(PropertyResponse(**enriched_prop_data))
    
    return enriched_properties

@router.get("/search", response_model=List[PropertyResponse])
async def search_properties(
    q: str = Query(..., min_length=2, description="Search query"),
    skip: int = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1, description="Limit results (optional, use None for unlimited map view)"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Search properties by text query."""
    query = db.query(Property).options(joinedload(Property.property_type))
    
    # Search in title, description, address, city
    search_filter = or_(
        Property.title.ilike(f"%{q}%"),
        Property.description.ilike(f"%{q}%"),
        Property.address.ilike(f"%{q}%"),
        Property.city.ilike(f"%{q}%"),
        Property.location_display.ilike(f"%{q}%")
    )
    
    query = query.filter(search_filter).filter(Property.status == 'available')
    query = query.order_by(Property.created_at.desc())
    
    # Apply offset
    query = query.offset(skip)
    
    # Apply limit only if specified (for map views, allow unlimited)
    if limit is not None:
        query = query.limit(limit)
    
    properties = query.all()
    
    # Populate agent and office data for each property
    enriched_properties = []
    for prop in properties:
        enriched_prop_data = populate_agent_office_data(prop, db)
        enriched_properties.append(PropertyResponse(**enriched_prop_data))
    
    return enriched_properties

@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """Get a specific property by ID."""
    property_obj = db.query(Property).options(
        joinedload(Property.property_type),
        joinedload(Property.amenities),
        joinedload(Property.views)
    ).filter(Property.property_id == property_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Track property view if user is authenticated
    if current_user:
        view_history = PropertyViewHistory(
            property_id=property_obj.property_id,
            user_id=current_user.user_id
        )
        db.add(view_history)
        db.commit()
    
    # Populate agent and office data
    enriched_prop_data = populate_agent_office_data(property_obj, db)
    return PropertyResponse(**enriched_prop_data)

@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: str,
    property_update: PropertyUpdate,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Update a property (agents and admins only)."""
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    update_data = property_update.dict(exclude_unset=True)
    
    # Convert images list to JSONB format if provided
    if 'images' in update_data and update_data['images']:
        update_data['images'] = update_data['images']
    
    for field, value in update_data.items():
        setattr(property_obj, field, value)
    
    db.commit()
    db.refresh(property_obj)
    
    return property_obj

@router.delete("/{property_id}", response_model=Message)
async def delete_property(
    property_id: str,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Delete a property (agents and admins only)."""
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    db.delete(property_obj)
    db.commit()
    
    return {"message": "Property deleted successfully"}

@router.post("/{property_id}/save", response_model=Message)
async def save_property(
    property_id: str,
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Save a property to user's favorites."""
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check if already saved
    if property_obj in current_user.saved_properties:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property already saved"
        )
    
    current_user.saved_properties.append(property_obj)
    db.commit()
    
    return {"message": "Property saved successfully"}

@router.delete("/{property_id}/save", response_model=Message)
async def unsave_property(
    property_id: str,
    current_user: User = Depends(require_customer_or_above),
    db: Session = Depends(get_db)
):
    """Remove a property from user's favorites."""
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    # Check if saved
    if property_obj not in current_user.saved_properties:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Property not in saved list"
        )
    
    current_user.saved_properties.remove(property_obj)
    db.commit()
    
    return {"message": "Property removed from saved list"}

@router.get("/{property_id}/amenities", response_model=List[dict])
async def get_property_amenities(
    property_id: str,
    db: Session = Depends(get_db)
):
    """Get amenities for a specific property."""
    property_obj = db.query(Property).options(
        joinedload(Property.amenities)
    ).filter(Property.property_id == property_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    return [
        {
            "amenity_id": amenity.amenity_id,
            "amenity_name": amenity.amenity_name,
            "category": amenity.category,
            "icon": amenity.icon
        }
        for amenity in property_obj.amenities
    ]

@router.post("/{property_id}/amenities/{amenity_id}", response_model=Message)
async def add_property_amenity(
    property_id: str,
    amenity_id: int,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Add an amenity to a property."""
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    amenity = db.query(Amenity).filter(Amenity.amenity_id == amenity_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    if amenity in property_obj.amenities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amenity already added to property"
        )
    
    property_obj.amenities.append(amenity)
    db.commit()
    
    return {"message": "Amenity added to property"}

@router.delete("/{property_id}/amenities/{amenity_id}", response_model=Message)
async def remove_property_amenity(
    property_id: str,
    amenity_id: int,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Remove an amenity from a property."""
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    amenity = db.query(Amenity).filter(Amenity.amenity_id == amenity_id).first()
    
    if not property_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Property not found"
        )
    
    if not amenity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    if amenity not in property_obj.amenities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Amenity not associated with property"
        )
    
    property_obj.amenities.remove(amenity)
    db.commit()
    
    return {"message": "Amenity removed from property"} 

# IMAGE MANAGEMENT ENDPOINTS

@router.post("/{property_id}/images", response_model=schemas.ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def add_property_image(
    property_id: uuid.UUID,
    image_data: schemas.PropertyImageCreate,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Add a single image to a property (agents and admins only)."""
    # Verify property exists and user has permission
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # If this is marked as primary, unset other primary images for this property
    if image_data.is_primary:
        db.query(PropertyImage).filter(
            PropertyImage.property_id == property_id,
            PropertyImage.is_primary == True
        ).update({"is_primary": False})
    
    # Create new image record
    db_image = PropertyImage(
        property_id=property_id,
        **image_data.dict()
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    # Update property's primary_image field if this is the primary image
    if image_data.is_primary:
        property_obj.primary_image = image_data.url
        db.commit()
    
    return schemas.ImageUploadResponse(
        message="Image added successfully",
        image_url=db_image.url,
        image_id=db_image.image_id
    )

@router.post("/{property_id}/images/bulk", response_model=List[schemas.ImageUploadResponse])
async def add_multiple_property_images(
    property_id: uuid.UUID,
    bulk_data: schemas.ImageBulkUploadRequest,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Add multiple images to a property (agents and admins only)."""
    # Verify property exists
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    
    results = []
    primary_image_url = None
    
    # Process each image
    for idx, image_data in enumerate(bulk_data.images):
        # Auto-set order if not provided
        if image_data.order_index is None:
            image_data.order_index = idx
        
        # Handle primary image logic
        if image_data.is_primary and not primary_image_url:
            primary_image_url = image_data.url
            # Unset other primary images
            db.query(PropertyImage).filter(
                PropertyImage.property_id == property_id,
                PropertyImage.is_primary == True
            ).update({"is_primary": False})
        elif image_data.is_primary and primary_image_url:
            # Only one primary image allowed
            image_data.is_primary = False
        
        # Create image record
        db_image = PropertyImage(
            property_id=property_id,
            **image_data.dict()
        )
        db.add(db_image)
        
        results.append(schemas.ImageUploadResponse(
            message="Image added successfully",
            image_url=image_data.url
        ))
    
    # Update property's primary image
    if primary_image_url:
        property_obj.primary_image = primary_image_url
    
    db.commit()
    return results

@router.get("/{property_id}/images", response_model=schemas.PropertyImagesResponse)
async def get_property_images(
    property_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get all images for a property."""
    # Verify property exists
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Get all images ordered by order_index
    images = db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id
    ).order_by(PropertyImage.order_index.asc(), PropertyImage.created_at.asc()).all()
    
    # Find primary image
    primary_image = next((img for img in images if img.is_primary), None)
    
    return schemas.PropertyImagesResponse(
        property_id=property_id,
        primary_image=primary_image,
        images=images,
        total_count=len(images)
    )

@router.put("/{property_id}/images/{image_id}", response_model=schemas.PropertyImageResponse)
async def update_property_image(
    property_id: uuid.UUID,
    image_id: int,
    image_data: schemas.PropertyImageUpdate,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Update a property image (agents and admins only)."""
    # Find the image
    db_image = db.query(PropertyImage).filter(
        PropertyImage.image_id == image_id,
        PropertyImage.property_id == property_id
    ).first()
    
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Handle primary image logic
    if image_data.is_primary is True:
        # Unset other primary images for this property
        db.query(PropertyImage).filter(
            PropertyImage.property_id == property_id,
            PropertyImage.is_primary == True,
            PropertyImage.image_id != image_id
        ).update({"is_primary": False})
        
        # Update property's primary_image field
        property_obj = db.query(Property).filter(Property.property_id == property_id).first()
        if property_obj and image_data.url:
            property_obj.primary_image = image_data.url
        elif property_obj and db_image.url:
            property_obj.primary_image = db_image.url
    
    # Update image fields
    update_data = image_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_image, field, value)
    
    db.commit()
    db.refresh(db_image)
    return db_image

@router.put("/{property_id}/images/reorder", response_model=schemas.Message)
async def reorder_property_images(
    property_id: uuid.UUID,
    reorder_data: schemas.ImageReorderRequest,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Reorder property images (agents and admins only)."""
    # Verify property exists
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_obj:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Update order for each image
    for order_update in reorder_data.image_orders:
        image_id = order_update.get("image_id")
        order_index = order_update.get("order_index")
        
        if image_id and order_index is not None:
            db.query(PropertyImage).filter(
                PropertyImage.image_id == image_id,
                PropertyImage.property_id == property_id
            ).update({"order_index": order_index})
    
    db.commit()
    return schemas.Message(message="Images reordered successfully")

@router.put("/{property_id}/images/{image_id}/set-primary", response_model=schemas.Message)
async def set_primary_image(
    property_id: uuid.UUID,
    image_id: int,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Set an image as the primary/thumbnail image (agents and admins only)."""
    # Find the image
    db_image = db.query(PropertyImage).filter(
        PropertyImage.image_id == image_id,
        PropertyImage.property_id == property_id
    ).first()
    
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Unset all other primary images for this property
    db.query(PropertyImage).filter(
        PropertyImage.property_id == property_id,
        PropertyImage.is_primary == True
    ).update({"is_primary": False})
    
    # Set this image as primary
    db_image.is_primary = True
    
    # Update property's primary_image field
    property_obj = db.query(Property).filter(Property.property_id == property_id).first()
    if property_obj:
        property_obj.primary_image = db_image.url
    
    db.commit()
    return schemas.Message(message="Primary image updated successfully")

@router.delete("/{property_id}/images/{image_id}", response_model=schemas.Message)
async def delete_property_image(
    property_id: uuid.UUID,
    image_id: int,
    current_user: User = Depends(require_agent_or_admin),
    db: Session = Depends(get_db)
):
    """Delete a property image (agents and admins only)."""
    # Find the image
    db_image = db.query(PropertyImage).filter(
        PropertyImage.image_id == image_id,
        PropertyImage.property_id == property_id
    ).first()
    
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")
    
    was_primary = db_image.is_primary
    
    # Delete the image
    db.delete(db_image)
    
    # If this was the primary image, set another image as primary or clear primary_image
    if was_primary:
        property_obj = db.query(Property).filter(Property.property_id == property_id).first()
        if property_obj:
            # Find another image to set as primary
            next_primary = db.query(PropertyImage).filter(
                PropertyImage.property_id == property_id
            ).order_by(PropertyImage.order_index.asc()).first()
            
            if next_primary:
                next_primary.is_primary = True
                property_obj.primary_image = next_primary.url
            else:
                property_obj.primary_image = None
    
    db.commit()
    return schemas.Message(message="Image deleted successfully")


@router.get("/sync-status")
async def get_crea_sync_status(db: Session = Depends(get_db)):
    """
    Get CREA sync status and data freshness information
    """
    try:
        import os
        import json
        
        now = datetime.now()
        cache_key = "crea_sync"
        
        # Check cache for last sync time
        last_sync_cached = _last_crea_sync_cache.get(cache_key)
        
        # Check last_property_sync.json file
        last_sync_file = "last_property_sync.json"
        last_sync_from_file = None
        
        if os.path.exists(last_sync_file):
            try:
                with open(last_sync_file, 'r') as f:
                    data = json.load(f)
                    last_sync_str = data.get('last_sync')
                    if last_sync_str:
                        last_sync_from_file = datetime.fromisoformat(last_sync_str)
            except Exception as e:
                print(f"Error reading sync file: {e}")
        
        # Calculate staleness
        is_stale = True
        hours_since_sync = None
        
        if last_sync_from_file:
            hours_since_sync = (now - last_sync_from_file).total_seconds() / 3600
            is_stale = hours_since_sync >= 24
        
        # Check cooldown status
        next_sync_available = True
        if last_sync_cached:
            minutes_since_sync = (now - last_sync_cached).total_seconds() / 60
            next_sync_available = minutes_since_sync >= CREA_SYNC_COOLDOWN_MINUTES
        
        # Count recent properties
        recent_cutoff = now - timedelta(days=7)
        recent_properties = db.query(Property).filter(
            Property.created_at >= recent_cutoff
        ).count()
        
        return {
            "sync_type": "CREA Property Replication",
            "is_data_stale": is_stale,
            "hours_since_last_sync": round(hours_since_sync, 2) if hours_since_sync else None,
            "last_sync_file": last_sync_from_file.isoformat() if last_sync_from_file else None,
            "last_sync_cached": last_sync_cached.isoformat() if last_sync_cached else None,
            "next_sync_available": next_sync_available,
            "sync_cooldown_minutes": CREA_SYNC_COOLDOWN_MINUTES,
            "recent_properties_count": recent_properties,
            "auto_sync_enabled": True,
            "sync_trigger": "Automatic on /api/v1/properties/ calls",
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking CREA sync status: {str(e)}")


@router.post("/sync")
async def manual_crea_sync(
    limit: Optional[int] = Query(None, description="Limit number of properties for testing"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_admin)
):
    """
    Manually trigger CREA property sync (agents and admins only)
    """
    try:
        # Force sync regardless of cooldown for manual triggers
        await _background_crea_sync()
        
        # Get updated count
        total_properties = db.query(Property).count()
        
        return {
            "status": "success",
            "message": "CREA property sync completed",
            "total_properties_in_db": total_properties,
            "sync_type": "Manual trigger",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running manual CREA sync: {str(e)}") 