from apscheduler.schedulers.background import BackgroundScheduler
from emailer import send_property_email
from enhanced_parser import EnhancedRealEstateParser
from database import SessionLocal
from db_models import Property
import logging
import asyncio

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

enhanced_parser = EnhancedRealEstateParser()

def get_properties_from_database():
    """Get properties from the real database instead of mock data"""
    try:
        db = SessionLocal()
        properties = db.query(Property).limit(1000).all()  # Get up to 1000 properties
        
        property_data = []
        for prop in properties:
            property_dict = {
                'id': prop.property_id,
                'price': float(prop.price) if prop.price else 0,
                'bedrooms': prop.bedrooms or 0,
                'bathrooms': float(prop.bathrooms) if prop.bathrooms else 0,
                'sqft': prop.square_feet or 0,
                'property_type': prop.property_type or 'unknown',
                'city': prop.city or '',
                'province': prop.province or '',
                'description': prop.description or '',
                'address': prop.address or '',
                'listing_type': getattr(prop, 'listing_type', ''),
                'year_built': prop.year_built,
                'garage_spaces': 1 if getattr(prop, 'has_garage', False) else 0,
                'amenities': []  # Could be populated from related tables
            }
            property_data.append(property_dict)
        
        db.close()
        logger.info(f"Loaded {len(property_data)} properties from database for subscription alerts")
        return property_data
        
    except Exception as e:
        logger.error(f"Error loading properties from database: {e}")
        # Fallback to empty list or raise exception
        return []

def matches_requirements(prop, requirements):
    if requirements.max_price is not None and prop.get("price", 0) > requirements.max_price:
        return False
    if requirements.min_price is not None and prop.get("price", 0) < requirements.min_price:
        return False
    if requirements.bedrooms_total is not None and prop.get("bedrooms", 0) < requirements.bedrooms_total:
        return False
    bathrooms = requirements.bathrooms_total or requirements.bathrooms_full
    if bathrooms is not None and prop.get("bathrooms", 0) < bathrooms:
        return False
    if requirements.square_feet_min is not None and prop.get("sqft", 0) < requirements.square_feet_min:
        return False
    if requirements.square_feet_max is not None and prop.get("sqft", 0) > requirements.square_feet_max:
        return False
    places = [place.lower() for place in (requirements.cities or []) + (requirements.neighborhoods or [])]
    if places:
        city = (prop.get("city") or "").lower()
        address = (prop.get("address") or "").lower()
        if not any(place in city or place in address for place in places):
            return False
    if (requirements.garage_spaces or requirements.garage_type) and not prop.get("garage_spaces"):
        return False
    return True

def enhanced_user_job(email, prompt, frequency):
    """Send listings that match the subscriber's saved filters."""
    try:
        logger.info(f"Running subscription job for {email}")
        requirements = enhanced_parser.parse_comprehensive(prompt)
        property_data = get_properties_from_database()
        if not property_data:
            logger.warning(f"No properties found in database for subscription {email}")
            return

        email_properties = []
        for prop in property_data:
            if not matches_requirements(prop, requirements):
                continue
            email_properties.append({
                "id": prop.get("id"),
                "price": prop.get("price"),
                "bedrooms": prop.get("bedrooms"),
                "bathrooms": prop.get("bathrooms"),
                "sqft": prop.get("sqft"),
                "property_type": prop.get("property_type"),
                "city": prop.get("city"),
                "address": prop.get("address"),
                "description": prop.get("description"),
            })
            if len(email_properties) == 5:
                break

        send_enhanced_property_email(email, email_properties, requirements, frequency)
        
        logger.info(f"Enhanced subscription email sent to {email} with {len(email_properties)} properties")
        
    except Exception as e:
        logger.error(f"Error in enhanced user job for {email}: {e}")

def send_enhanced_property_email(email, properties, requirements, frequency):
    """Send an email listing properties that match the saved filters."""
    try:
        subject = "Property matches for your saved search"
        
        # Extract key requirements for email summary
        bedroom_details = f"{requirements.bedrooms_total or 'any'} bedrooms"
        if requirements.bedrooms_above_grade:
            bedroom_details += f" ({requirements.bedrooms_above_grade} above grade)"
        if requirements.bedrooms_main_floor:
            bedroom_details += f" ({requirements.bedrooms_main_floor} main floor)"
        
        bathroom_details = f"{requirements.bathrooms_total or requirements.bathrooms_full or 'any'} bathrooms"
        if requirements.bathrooms_main_floor:
            bathroom_details += f" (including main floor bath)"
        
        special_features = []
        if requirements.bonus_room:
            special_features.append("bonus room")
        if requirements.spice_kitchen:
            special_features.append("spice kitchen")
        if requirements.open_to_below:
            special_features.append("open to below")
        if requirements.open_to_above:
            special_features.append("open to above")
        if requirements.garage_type:
            special_features.append(f"{requirements.garage_type} garage")
        
        location_prefs = (requirements.cities or []) + (requirements.neighborhoods or [])
        
        email_body = f"""
        <h2>🎯 Your Personalized Property Recommendations</h2>
        
        <h3>📋 Your Search Criteria</h3>
        <ul>
            <li><strong>Bedrooms:</strong> {bedroom_details}</li>
            <li><strong>Bathrooms:</strong> {bathroom_details}</li>
            <li><strong>Budget:</strong> {f"Under ${requirements.max_price:,}" if requirements.max_price else "No limit"}</li>
            <li><strong>Location:</strong> {", ".join(location_prefs) if location_prefs else "Any location"}</li>
            {f"<li><strong>Special Features:</strong> {', '.join(special_features)}</li>" if special_features else ""}
        </ul>
        
        <h3>Top {len(properties)} matching properties</h3>
        """
        
        for i, prop in enumerate(properties, 1):
            email_body += f"""
            <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h4>#{i} - {prop.get('address', 'Address not available')}</h4>
                <p><strong>Price:</strong> ${prop.get('price', 0):,}</p>
                <p><strong>Details:</strong> {prop.get('bedrooms', 0)} bed, {prop.get('bathrooms', 0)} bath, {prop.get('sqft', 0):,} sqft</p>
                <p><strong>Type:</strong> {prop.get('property_type', 'Unknown')} in {prop.get('city', 'Unknown city')}</p>
                {f"<p><strong>Description:</strong> {prop.get('description', '')[:200]}...</p>" if prop.get('description') else ""}
            </div>
            """
        
        email_body += f"""
        <hr>
        <p><em>These listings match the filters from your saved search. You'll receive updates every {frequency} hours.</em></p>
        """
        
        # Use existing email function or create enhanced version
        asyncio.run(send_property_email(email, properties, subject, email_body))
        
    except Exception as e:
        logger.error(f"Error sending enhanced email to {email}: {e}")
        # Fallback to basic email
        asyncio.run(send_property_email(email, properties[:5]))

def schedule_user_task(prompt):
    """Schedule a saved-search alert."""
    email = prompt.email
    interval = prompt.frequency or 24  # Default to 24 hours instead of 12
    job_id = f"enhanced_job_{email}"
    
    # Replace existing job with enhanced version
    scheduler.add_job(
        enhanced_user_job, 
        'interval', 
        hours=interval, 
        id=job_id, 
        replace_existing=True, 
        args=[email, prompt.prompt, interval]
    )
    
    logger.info(f"Scheduled enhanced AI subscription for {email} every {interval} hours")
