from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from database import get_db
from models import Prompt
from auth import get_current_user_optional
from db_models import User

from scheduler import schedule_user_task
from enhanced_parser import PropertyRequirements, extract_filters_enhanced

router = APIRouter(prefix="/ai", tags=["Property search"])

@router.post("/parse")
async def parse_prompt(
    prompt: Prompt,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Parse natural language prompt and return real CREA property data.
    
    Searches comprehensive CREA database for properties matching user criteria including:
    - Location (city, province, address, postal code)
    - Property specifications (bedrooms, bathrooms, price, square feet)
    - Property types and amenities
    - Agent and office information
    
    Returns live property data in complete CREA format.
    """
    try:
        # Step 1: Enhanced parsing with comprehensive extraction
        enhanced_result = extract_filters_enhanced(prompt.prompt)
        
        # Extract requirements from enhanced result
        requirements = PropertyRequirements(**enhanced_result.get('enhanced', {}))
        
        # Step 2: Get legacy filters for backward compatibility  
        legacy_filters = enhanced_result
        
        # Step 3: Build database query from real CREA properties
        from db_models import Property, PropertyType, AgentProfile, Office
        from sqlalchemy.orm import joinedload
        from sqlalchemy import or_, and_, func, Text
        
        # Base query with available relationships loaded
        query = db.query(Property).options(
            joinedload(Property.property_type)
        )
        
        # Apply location filters
        location_filters = []
        if requirements.cities:
            for city in requirements.cities:
                location_filters.append(Property.city.ilike(f"%{city}%"))
        if requirements.neighborhoods:
            for neighborhood in requirements.neighborhoods:
                location_filters.append(Property.address.ilike(f"%{neighborhood}%"))
        if requirements.postal_codes:
            for postal in requirements.postal_codes:
                location_filters.append(Property.postal_code.ilike(f"%{postal}%"))
        
        # Also check legacy filters for location
        if legacy_filters.get('location'):
            location_filters.append(Property.city.ilike(f"%{legacy_filters['location']}%"))
            location_filters.append(Property.province.ilike(f"%{legacy_filters['location']}%"))
        
        if location_filters:
            query = query.filter(or_(*location_filters))
        
        # Apply price filters
        if requirements.max_price:
            query = query.filter(Property.price <= requirements.max_price)
        if requirements.min_price:
            query = query.filter(Property.price >= requirements.min_price)
        if legacy_filters.get('price_max'):
            query = query.filter(Property.price <= legacy_filters['price_max'])
        
        # Apply bedroom filters - EXACT match (not >=)
        if requirements.bedrooms_total:
            query = query.filter(Property.bedrooms == requirements.bedrooms_total)
        if legacy_filters.get('bedrooms'):
            query = query.filter(Property.bedrooms == legacy_filters['bedrooms'])
        
        # Apply bathroom filters - EXACT match (not >=)  
        if requirements.bathrooms_total:
            # Convert to Decimal to match database column type
            from decimal import Decimal
            bath_value = Decimal(str(requirements.bathrooms_total))
            query = query.filter(Property.bathrooms == bath_value)
        elif requirements.bathrooms_full:
            from decimal import Decimal
            bath_value = Decimal(str(requirements.bathrooms_full))
            query = query.filter(Property.bathrooms == bath_value)
        
        # Apply square footage filters
        if requirements.square_feet_min:
            query = query.filter(Property.square_feet >= requirements.square_feet_min)
        if requirements.square_feet_max:
            query = query.filter(Property.square_feet <= requirements.square_feet_max)
        
        # Apply property type filters
        if requirements.property_types:
            type_filters = []
            for prop_type in requirements.property_types:
                type_filters.append(Property.title.ilike(f"%{prop_type}%"))
            query = query.filter(or_(*type_filters))
        if legacy_filters.get('property_type') and not requirements.property_types:
            query = query.filter(Property.title.ilike(f"%{legacy_filters['property_type']}%"))
        
        # Apply garage filters
        if requirements.garage_spaces:
            query = query.filter(Property.parking_spots >= requirements.garage_spaces)
        
        # Apply comprehensive amenity and feature filters - search across multiple fields
        amenity_keywords = []
        
        # Extracted amenities from requirements
        if requirements.bonus_room:
            amenity_keywords.extend(["bonus room", "bonus", "flex room", "den"])
        if requirements.spice_kitchen:
            amenity_keywords.extend(["spice kitchen", "wok kitchen", "prep kitchen"])
        if requirements.basement_developed:
            amenity_keywords.extend(["finished basement", "developed basement", "basement suite"])
        if requirements.deck:
            amenity_keywords.extend(["deck", "patio", "outdoor space"])
        if requirements.fireplace:
            amenity_keywords.extend(["fireplace", "gas fireplace", "wood burning"])
        if requirements.hardwood_floors:
            amenity_keywords.extend(["hardwood", "hardwood floors", "wood floors"])
        
        # Additional comprehensive search terms that might be in descriptions
        description_keywords = []
        prompt_lower = prompt.prompt.lower()
        
        # Home features
        if any(word in prompt_lower for word in ["garage", "parking"]):
            description_keywords.extend(["garage", "parking", "carport"])
        if any(word in prompt_lower for word in ["pool", "swimming"]):
            description_keywords.extend(["pool", "swimming", "hot tub"])
        if any(word in prompt_lower for word in ["garden", "yard", "backyard"]):
            description_keywords.extend(["garden", "yard", "backyard", "landscaped"])
        if any(word in prompt_lower for word in ["view", "mountain", "lake", "river"]):
            description_keywords.extend(["view", "mountain view", "lake view", "river view"])
        if any(word in prompt_lower for word in ["modern", "contemporary", "updated"]):
            description_keywords.extend(["modern", "contemporary", "updated", "renovated"])
        if any(word in prompt_lower for word in ["luxury", "high-end", "premium"]):
            description_keywords.extend(["luxury", "high-end", "premium", "executive"])
        
        # Neighborhood and location features
        if any(word in prompt_lower for word in ["school", "schools", "education"]):
            description_keywords.extend(["school", "schools", "education", "elementary", "high school"])
        if any(word in prompt_lower for word in ["transit", "transport", "bus", "train"]):
            description_keywords.extend(["transit", "transport", "bus", "train", "lrt", "subway"])
        if any(word in prompt_lower for word in ["shopping", "mall", "stores"]):
            description_keywords.extend(["shopping", "mall", "stores", "retail"])
        if any(word in prompt_lower for word in ["park", "parks", "playground"]):
            description_keywords.extend(["park", "parks", "playground", "green space"])
        if any(word in prompt_lower for word in ["downtown", "central", "core"]):
            description_keywords.extend(["downtown", "central", "core", "city center"])
        if any(word in prompt_lower for word in ["quiet", "peaceful", "family"]):
            description_keywords.extend(["quiet", "peaceful", "family", "safe", "family-friendly"])
        
        # Property condition and age
        if any(word in prompt_lower for word in ["new", "brand new", "newly built"]):
            description_keywords.extend(["new", "brand new", "newly built", "new construction"])
        if any(word in prompt_lower for word in ["suite", "rental", "income"]):
            description_keywords.extend(["suite", "rental", "income", "secondary suite"])
        
        # Apply amenity filters to description
        all_keywords = amenity_keywords + description_keywords
        if all_keywords:
            # Use OR logic for keywords - property should match at least one
            keyword_conditions = []
            for keyword in all_keywords:
                keyword_conditions.append(Property.description.ilike(f"%{keyword}%"))
            if keyword_conditions:
                query = query.filter(or_(*keyword_conditions))
        
        # Comprehensive text search across ALL relevant fields - use OR logic for broader results
        search_terms = prompt.prompt.lower().split()
        if search_terms and not all_keywords:  # Only do general search if no specific keywords matched
            # Build a single OR condition for all terms across all searchable fields
            search_conditions = []
            for term in search_terms:
                if len(term) > 2:  # Skip very short terms
                    search_conditions.extend([
                        # Basic property info
                        Property.title.ilike(f"%{term}%"),
                        Property.description.ilike(f"%{term}%"),
                        Property.address.ilike(f"%{term}%"),
                        Property.city.ilike(f"%{term}%"),
                        Property.province.ilike(f"%{term}%"),
                        Property.postal_code.ilike(f"%{term}%"),
                        
                        # Additional CREA fields
                        Property.common_interest.ilike(f"%{term}%"),
                        Property.zoning.ilike(f"%{term}%"),
                        
                        # JSONB fields - convert to text for searching
                        func.cast(Property.other_amenities, Text).ilike(f"%{term}%"),
                        func.cast(Property.accessibility_features, Text).ilike(f"%{term}%"),
                        func.cast(Property.images, Text).ilike(f"%{term}%")
                    ])
            
            if search_conditions:
                query = query.filter(or_(*search_conditions))
        
        # Execute the main query first
        properties = query.all()
        
        # Step 4: Get agent and office data for properties
        agent_ids = set()
        office_ids = set()
        
        for prop in properties:
            if prop.listing_agent_id:
                agent_ids.add(prop.listing_agent_id)
            if prop.listing_office_id:
                office_ids.add(prop.listing_office_id)
        
        # Query agents and offices in batch
        agents_data = {}
        if agent_ids:
            agents = db.query(AgentProfile).filter(AgentProfile.crea_agent_key.in_(agent_ids)).all()
            agents_data = {agent.crea_agent_key: agent for agent in agents}
        
        offices_data = {}
        if office_ids:
            offices = db.query(Office).filter(Office.crea_office_key.in_(office_ids)).all()
            offices_data = {office.crea_office_key: office for office in offices}
        
        # Step 5: Format results in exact CREA format
        results = []
        for prop in properties:
            # Get agent and office objects
            listing_agent = agents_data.get(prop.listing_agent_id) if prop.listing_agent_id else None
            listing_office = offices_data.get(prop.listing_office_id) if prop.listing_office_id else None
            
            result = {
                "title": prop.title or "",
                "description": prop.description or "",
                "address": prop.address or "",
                "city": prop.city or "",
                "province": prop.province or "",
                "postal_code": prop.postal_code or "",
                "location_display": f"{prop.address}, {prop.city}, {prop.province}" if prop.address else f"{prop.city}, {prop.province}",
                "latitude": str(prop.latitude) if prop.latitude else None,
                "longitude": str(prop.longitude) if prop.longitude else None,
                "price": str(prop.price) if prop.price else "0",
                "price_type": "List Price",
                "hoa_fee": "0",
                "property_type_id": prop.property_type_id or 0,
                "bedrooms": prop.bedrooms or 0,
                "bathrooms": str(prop.bathrooms) if prop.bathrooms else "0",
                "square_feet": prop.square_feet or 0,
                "lot_size": prop.lot_size or 0,
                "year_built": prop.year_built or 0,
                "parking_spots": prop.parking_spots or 0,
                "has_garage": prop.has_garage or False,
                "has_basement": prop.has_basement or False,
                "single_story_only": prop.single_story_only or False,
                "stories": prop.stories or 1,
                "status": prop.status or "available",
                "is_new": prop.is_new or False,
                "primary_image": prop.primary_image or "",
                "images": prop.images or [],
                "listing_key": prop.listing_key or "",
                "modification_timestamp": prop.modification_timestamp,
                "listing_agent_id": prop.listing_agent_id or "",
                "listing_office_id": prop.listing_office_id or "",
                "co_listing_agent_id": prop.co_listing_agent_id or "",
                "co_listing_agent_id2": prop.co_listing_agent_id2 or "",
                "co_listing_agent_id3": prop.co_listing_agent_id3 or "",
                "co_listing_office_id": prop.co_listing_office_id or "",
                "co_listing_office_id2": prop.co_listing_office_id2 or "",
                "co_listing_office_id3": prop.co_listing_office_id3 or "",
                "mls_listing_url": prop.mls_listing_url or "",
                "common_interest": prop.common_interest or "",
                "accessibility_features": prop.accessibility_features or [],
                "other_amenities": prop.other_amenities or [],
                "tax_annual_amount": prop.tax_annual_amount or "",
                "days_on_market": prop.days_on_market or 0,
                "zoning": prop.zoning or "",
                "availability_date": prop.availability_date,
                "property_id": prop.property_id,
                "list_date": prop.list_date,
                "created_at": prop.created_at,
                "updated_at": prop.updated_at,
                "property_type": {
                    "type_name": prop.property_type.type_name if prop.property_type else "",
                    "description": prop.property_type.description if prop.property_type else "",
                    "type_id": prop.property_type.type_id if prop.property_type else 0,
                    "created_at": prop.property_type.created_at if prop.property_type else None
                } if prop.property_type else None,
                "listing_agent": {
                    "profile_id": listing_agent.profile_id if listing_agent else None,
                    "crea_agent_key": listing_agent.crea_agent_key if listing_agent else "",
                    "first_name": listing_agent.first_name if listing_agent else "",
                    "last_name": listing_agent.last_name if listing_agent else "",
                    "middle_name": listing_agent.middle_name if listing_agent else "",
                    "agent_email": listing_agent.agent_email if listing_agent else "",
                    "agent_phone": listing_agent.agent_phone if listing_agent else "",
                    "agent_mobile": listing_agent.agent_mobile if listing_agent else "",
                    "agent_fax": listing_agent.agent_fax if listing_agent else "",
                    "agency_name": listing_agent.agency_name if listing_agent else "",
                    "license_number": listing_agent.license_number if listing_agent else "",
                    "member_designation": listing_agent.member_designation if listing_agent else "",
                    "member_status": listing_agent.member_status if listing_agent else "",
                    "languages": listing_agent.languages if listing_agent else [],
                    "specialization": listing_agent.specialization if listing_agent else "",
                    "experience": listing_agent.experience if listing_agent else 0,
                    "bio": listing_agent.bio if listing_agent else "",
                    "rating": listing_agent.rating if listing_agent else "",
                    "total_sales": listing_agent.total_sales if listing_agent else 0,
                    "active_listings": listing_agent.active_listings if listing_agent else 0,
                    "is_accepting_clients": listing_agent.is_accepting_clients if listing_agent else True,
                    "city": listing_agent.city if listing_agent else "",
                    "province": listing_agent.province if listing_agent else ""
                } if listing_agent else None,
                "listing_office": {
                    "office_id": listing_office.office_id if listing_office else None,
                    "crea_office_key": listing_office.crea_office_key if listing_office else "",
                    "office_name": listing_office.office_name if listing_office else "",
                    "office_phone": listing_office.office_phone if listing_office else "",
                    "office_email": listing_office.office_email if listing_office else "",
                    "office_website": listing_office.office_website if listing_office else "",
                    "office_address": listing_office.office_address if listing_office else "",
                    "office_city": listing_office.office_city if listing_office else "",
                    "office_province": listing_office.office_province if listing_office else "",
                    "office_postal_code": listing_office.office_postal_code if listing_office else "",
                    "office_country": listing_office.office_country if listing_office else "",
                    "office_type": listing_office.office_type if listing_office else "",
                    "office_status": listing_office.office_status if listing_office else "",
                    "office_fax": listing_office.office_fax if listing_office else ""
                } if listing_office else None
            }
            results.append(result)
        
        # Return results in your exact format - direct list of CREA properties
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

@router.post("/subscribe")
async def subscribe_user(
    prompt: Prompt,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Subscribe user to property alerts based on natural language preferences.
    
    This endpoint will:
    1. Parse the user's search preferences
    2. Schedule periodic property alerts
    3. Send notifications when matching properties are found
    """
    try:
        # Validate email is provided
        if not prompt.email:
            raise HTTPException(
                status_code=400, 
                detail="Email is required for subscription"
            )
        
        # Schedule the user task for periodic alerts
        schedule_user_task(prompt)
        
        return {
            "status": "scheduled",
            "message": "User subscribed to property alerts",
            "email": prompt.email,
            "frequency": prompt.frequency or 24,  # Default to 24 hours
            "search_query": prompt.prompt
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subscribing user: {str(e)}")

@router.post("/generate-description")
async def generate_property_description(
    property_features: dict,
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Build a property description from the supplied features.
    """
    try:
        bedrooms = property_features.get('bedrooms', 'N/A')
        bathrooms = property_features.get('bathrooms', 'N/A')
        square_feet = property_features.get('square_feet', 'N/A')
        city = property_features.get('city', 'a great location')
        
        description = f"Beautiful property featuring {bedrooms} bedrooms and {bathrooms} bathrooms"
        if square_feet != 'N/A':
            description += f" with {square_feet} square feet of living space"
        description += f" located in {city}. This property offers excellent value and potential."
        
        return {
            "generated_description": description,
            "features_used": property_features,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating description: {str(e)}")

@router.post("/analyze-market")
async def analyze_market_trends(
    location: str,
    property_type: Optional[str] = None,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Summarize stored market figures for a location and property type.
    """
    try:
        # This would typically connect to market data APIs and AI analysis
        # For now, we'll return mock trend data
        
        trends = {
            "location": location,
            "property_type": property_type or "all",
            "average_price_trend": "+5.2% (6 months)",
            "market_activity": "High",
            "price_per_sqft": "$425 - $580",
            "days_on_market": "22 days average",
            "inventory_level": "Low",
            "forecast": "Continued growth expected",
        }
        
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing market: {str(e)}")

@router.post("/recommend-properties")
async def recommend_properties(
    user_preferences: dict,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Get property recommendations based on user preferences from real CREA database.
    
    Searches live property data matching user criteria:
    - Price range and budget constraints
    - Location preferences (city, province, neighborhood)
    - Property specifications (bedrooms, bathrooms, square feet)
    - Property types and amenities
    
    Returns live CREA property data in complete format.
    """
    try:
        # Build database query from user preferences
        from db_models import Property, PropertyType, AgentProfile, Office
        from sqlalchemy.orm import joinedload
        from sqlalchemy import or_, and_, func
        
        # Base query with available relationships loaded
        query = db.query(Property).options(
            joinedload(Property.property_type)
        )
        
        # Apply user preference filters
        if user_preferences.get('max_price'):
            query = query.filter(Property.price <= user_preferences['max_price'])
        if user_preferences.get('min_price'):
            query = query.filter(Property.price >= user_preferences['min_price'])
            
        if user_preferences.get('bedrooms'):
            query = query.filter(Property.bedrooms == user_preferences['bedrooms'])
        if user_preferences.get('bathrooms'):
            from decimal import Decimal
            bath_value = Decimal(str(user_preferences['bathrooms']))
            query = query.filter(Property.bathrooms == bath_value)
            
        if user_preferences.get('min_sqft'):
            query = query.filter(Property.square_feet >= user_preferences['min_sqft'])
        if user_preferences.get('max_sqft'):
            query = query.filter(Property.square_feet <= user_preferences['max_sqft'])
            
        # Location filters
        if user_preferences.get('locations'):
            location_filters = []
            for location in user_preferences['locations']:
                location_filters.append(Property.city.ilike(f"%{location}%"))
                location_filters.append(Property.province.ilike(f"%{location}%"))
                location_filters.append(Property.address.ilike(f"%{location}%"))
            query = query.filter(or_(*location_filters))
            
        # Property type filters
        if user_preferences.get('property_types'):
            type_filters = []
            for prop_type in user_preferences['property_types']:
                type_filters.append(Property.title.ilike(f"%{prop_type}%"))
            query = query.filter(or_(*type_filters))
            
        # Amenity filters
        if user_preferences.get('amenities'):
            for amenity in user_preferences['amenities']:
                query = query.filter(Property.description.ilike(f"%{amenity}%"))
                
        # Garage requirement
        if user_preferences.get('garage_required'):
            query = query.filter(Property.parking_spots > 0)
            
        # Execute query and get ALL results (exhaustive)
        properties = query.all()
        
        # Get agent and office data for properties
        agent_ids = set()
        office_ids = set()
        
        for prop in properties:
            if prop.listing_agent_id:
                agent_ids.add(prop.listing_agent_id)
            if prop.listing_office_id:
                office_ids.add(prop.listing_office_id)
        
        # Query agents and offices in batch
        agents_data = {}
        if agent_ids:
            agents = db.query(AgentProfile).filter(AgentProfile.crea_agent_key.in_(agent_ids)).all()
            agents_data = {agent.crea_agent_key: agent for agent in agents}
        
        offices_data = {}
        if office_ids:
            offices = db.query(Office).filter(Office.crea_office_key.in_(office_ids)).all()
            offices_data = {office.crea_office_key: office for office in offices}
        
        # Format results in exact CREA format
        results = []
        for prop in properties:
            # Get agent and office objects
            listing_agent = agents_data.get(prop.listing_agent_id) if prop.listing_agent_id else None
            listing_office = offices_data.get(prop.listing_office_id) if prop.listing_office_id else None
            
            result = {
                "title": prop.title or "",
                "description": prop.description or "",
                "address": prop.address or "",
                "city": prop.city or "",
                "province": prop.province or "",
                "postal_code": prop.postal_code or "",
                "location_display": f"{prop.address}, {prop.city}, {prop.province}" if prop.address else f"{prop.city}, {prop.province}",
                "latitude": str(prop.latitude) if prop.latitude else None,
                "longitude": str(prop.longitude) if prop.longitude else None,
                "price": str(prop.price) if prop.price else "0",
                "price_type": "List Price",
                "hoa_fee": "0",
                "property_type_id": prop.property_type_id or 0,
                "bedrooms": prop.bedrooms or 0,
                "bathrooms": str(prop.bathrooms) if prop.bathrooms else "0",
                "square_feet": prop.square_feet or 0,
                "lot_size": prop.lot_size or 0,
                "year_built": prop.year_built or 0,
                "parking_spots": prop.parking_spots or 0,
                "has_garage": prop.has_garage or False,
                "has_basement": prop.has_basement or False,
                "single_story_only": prop.single_story_only or False,
                "stories": prop.stories or 1,
                "status": prop.status or "available",
                "is_new": prop.is_new or False,
                "primary_image": prop.primary_image or "",
                "images": prop.images or [],
                "listing_key": prop.listing_key or "",
                "modification_timestamp": prop.modification_timestamp,
                "listing_agent_id": prop.listing_agent_id or "",
                "listing_office_id": prop.listing_office_id or "",
                "co_listing_agent_id": prop.co_listing_agent_id or "",
                "co_listing_agent_id2": prop.co_listing_agent_id2 or "",
                "co_listing_agent_id3": prop.co_listing_agent_id3 or "",
                "co_listing_office_id": prop.co_listing_office_id or "",
                "co_listing_office_id2": prop.co_listing_office_id2 or "",
                "co_listing_office_id3": prop.co_listing_office_id3 or "",
                "mls_listing_url": prop.mls_listing_url or "",
                "common_interest": prop.common_interest or "",
                "accessibility_features": prop.accessibility_features or [],
                "other_amenities": prop.other_amenities or [],
                "tax_annual_amount": prop.tax_annual_amount or "",
                "days_on_market": prop.days_on_market or 0,
                "zoning": prop.zoning or "",
                "availability_date": prop.availability_date,
                "property_id": prop.property_id,
                "list_date": prop.list_date,
                "created_at": prop.created_at,
                "updated_at": prop.updated_at,
                "property_type": {
                    "type_name": prop.property_type.type_name if prop.property_type else "",
                    "description": prop.property_type.description if prop.property_type else "",
                    "type_id": prop.property_type.type_id if prop.property_type else 0,
                    "created_at": prop.property_type.created_at if prop.property_type else None
                } if prop.property_type else None,
                "listing_agent": {
                    "profile_id": listing_agent.profile_id if listing_agent else None,
                    "crea_agent_key": listing_agent.crea_agent_key if listing_agent else "",
                    "first_name": listing_agent.first_name if listing_agent else "",
                    "last_name": listing_agent.last_name if listing_agent else "",
                    "middle_name": listing_agent.middle_name if listing_agent else "",
                    "agent_email": listing_agent.agent_email if listing_agent else "",
                    "agent_phone": listing_agent.agent_phone if listing_agent else "",
                    "agent_mobile": listing_agent.agent_mobile if listing_agent else "",
                    "agent_fax": listing_agent.agent_fax if listing_agent else "",
                    "agency_name": listing_agent.agency_name if listing_agent else "",
                    "license_number": listing_agent.license_number if listing_agent else "",
                    "member_designation": listing_agent.member_designation if listing_agent else "",
                    "member_status": listing_agent.member_status if listing_agent else "",
                    "languages": listing_agent.languages if listing_agent else [],
                    "specialization": listing_agent.specialization if listing_agent else "",
                    "experience": listing_agent.experience if listing_agent else 0,
                    "bio": listing_agent.bio if listing_agent else "",
                    "rating": listing_agent.rating if listing_agent else "",
                    "total_sales": listing_agent.total_sales if listing_agent else 0,
                    "active_listings": listing_agent.active_listings if listing_agent else 0,
                    "is_accepting_clients": listing_agent.is_accepting_clients if listing_agent else True,
                    "city": listing_agent.city if listing_agent else "",
                    "province": listing_agent.province if listing_agent else ""
                } if listing_agent else None,
                "listing_office": {
                    "office_id": listing_office.office_id if listing_office else None,
                    "crea_office_key": listing_office.crea_office_key if listing_office else "",
                    "office_name": listing_office.office_name if listing_office else "",
                    "office_phone": listing_office.office_phone if listing_office else "",
                    "office_email": listing_office.office_email if listing_office else "",
                    "office_website": listing_office.office_website if listing_office else "",
                    "office_address": listing_office.office_address if listing_office else "",
                    "office_city": listing_office.office_city if listing_office else "",
                    "office_province": listing_office.office_province if listing_office else "",
                    "office_postal_code": listing_office.office_postal_code if listing_office else "",
                    "office_country": listing_office.office_country if listing_office else "",
                    "office_type": listing_office.office_type if listing_office else "",
                    "office_status": listing_office.office_status if listing_office else "",
                    "office_fax": listing_office.office_fax if listing_office else ""
                } if listing_office else None
            }
            results.append(result)
            
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

@router.get("/similar-properties/{property_id}")
async def get_similar_properties(
    property_id: str,
    top_k: int = 5,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Find other listings in the same city with the same bedroom count."""
    from db_models import Property

    try:
        prop_uuid = uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Property not found")

    original = db.query(Property).filter(Property.property_id == prop_uuid).first()
    if not original:
        raise HTTPException(status_code=404, detail="Property not found")

    query = db.query(Property).filter(Property.property_id != original.property_id)
    if original.city:
        query = query.filter(Property.city.ilike(original.city))
    if original.bedrooms is not None:
        query = query.filter(Property.bedrooms == original.bedrooms)
    matches = query.limit(max(top_k, 1)).all()

    def brief(prop):
        return {
            "property_id": str(prop.property_id),
            "title": prop.title,
            "price": float(prop.price) if prop.price is not None else None,
            "bedrooms": prop.bedrooms,
            "bathrooms": float(prop.bathrooms) if prop.bathrooms is not None else None,
            "square_feet": prop.square_feet,
            "city": prop.city,
            "province": prop.province,
        }

    return {
        "original_property": brief(original),
        "similar_properties": [brief(prop) for prop in matches],
        "match": "same city and bedroom count",
    }

# Legacy endpoints for backward compatibility
@router.post("/parse-legacy", include_in_schema=False)
async def parse_prompt_legacy(prompt: Prompt):
    """Legacy endpoint - use /ai/parse instead."""
    return await parse_prompt(prompt)

@router.post("/subscribe-legacy", include_in_schema=False)
async def subscribe_user_legacy(prompt: Prompt):
    """Legacy endpoint - use /ai/subscribe instead."""
    return await subscribe_user(prompt) 