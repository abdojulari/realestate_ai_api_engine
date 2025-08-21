from apscheduler.schedulers.background import BackgroundScheduler
from emailer import send_property_email
from enhanced_parser import EnhancedRealEstateParser
from recommendation_engine import UserPreferences
from model_manager import get_recommendation_engine
from database import SessionLocal
from db_models import Property
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

# Initialize enhanced AI components
environment = os.getenv('ENVIRONMENT', 'development')
enhanced_parser = EnhancedRealEstateParser()
recommendation_engine = get_recommendation_engine(environment)

def convert_requirements_to_preferences(requirements):
    """Convert enhanced parser requirements to UserPreferences for ML engine"""
    # Extract amenities from requirements
    amenities = []
    if requirements.garage_type or requirements.garage_spaces:
        amenities.append('garage')
    if requirements.basement_developed:
        amenities.append('finished_basement')
    if requirements.fireplace:
        amenities.append('fireplace')
    
    # Extract lifestyle keywords
    lifestyle_keywords = []
    if requirements.bonus_room:
        lifestyle_keywords.append('bonus_room')
    if requirements.spice_kitchen:
        lifestyle_keywords.append('spice_kitchen')
    if requirements.open_to_below or requirements.open_to_above:
        lifestyle_keywords.append('open_concept')
    if any([requirements.cities and 'edmonton' in ' '.join(requirements.cities).lower(),
            requirements.neighborhoods and any('edmonton' in n.lower() for n in requirements.neighborhoods)]):
        lifestyle_keywords.append('edmonton')
    if requirements.school_ratings == 'high':
        lifestyle_keywords.extend(['family', 'education', 'good_schools'])
    
    return UserPreferences(
        max_price=requirements.max_price,
        min_price=requirements.min_price,
        preferred_bedrooms=requirements.bedrooms_total,
        preferred_bathrooms=requirements.bathrooms_total or requirements.bathrooms_full,
        min_sqft=requirements.square_feet_min,
        max_sqft=requirements.square_feet_max,
        preferred_types=requirements.property_types if requirements.property_types else [],
        preferred_locations=(requirements.cities or []) + (requirements.neighborhoods or []),
        must_have_amenities=amenities,
        garage_required=requirements.garage_spaces is not None or requirements.garage_type is not None,
        lifestyle_keywords=lifestyle_keywords
    )

def get_properties_from_database():
    """Get properties from the real database instead of mock data"""
    try:
        db = SessionLocal()
        properties = db.query(Property).limit(1000).all()  # Get up to 1000 properties
        
        # Convert to format expected by recommendation engine
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

def enhanced_user_job(email, prompt, frequency):
    """Enhanced user job using AI components and real database"""
    try:
        logger.info(f"Running enhanced subscription job for {email}")
        
        # Step 1: Use enhanced parser to extract comprehensive requirements
        requirements = enhanced_parser.parse_comprehensive(prompt)
        logger.info(f"Enhanced parser extracted requirements for {email}")
        
        # Step 2: Convert to UserPreferences for ML engine
        user_prefs = convert_requirements_to_preferences(requirements)
        
        # Step 3: Load real properties from database
        property_data = get_properties_from_database()
        
        if not property_data:
            logger.warning(f"No properties found in database for subscription {email}")
            return
        
        # Step 4: Update recommendation engine with current property data
        recommendation_engine.load_properties(property_data)
        
        # Step 5: Get ML-powered recommendations
        recommendations = recommendation_engine.recommend_properties(
            user_prefs,
            user_id=None,  # No specific user ID for email subscriptions
            top_k=10,
            explain=True
        )
        
        # Step 6: Format properties for email
        email_properties = []
        for rec in recommendations[:5]:  # Top 5 for email
            # Handle RecommendationScore object
            if hasattr(rec, 'property_id'):
                # Find the property data from property_data
                prop_data = next((p for p in property_data if p['id'] == rec.property_id), {})
                email_properties.append({
                    'id': prop_data.get('id'),
                    'price': prop_data.get('price'),
                    'bedrooms': prop_data.get('bedrooms'),
                    'bathrooms': prop_data.get('bathrooms'),
                    'sqft': prop_data.get('sqft'),
                    'property_type': prop_data.get('property_type'),
                    'city': prop_data.get('city'),
                    'address': prop_data.get('address'),
                    'description': prop_data.get('description'),
                    'match_score': rec.overall_score,
                    'match_reasons': rec.explanation
                })
            else:
                # Handle dict format (if different)
                prop = rec.get('property', {})
                email_properties.append({
                    'id': prop.get('id'),
                    'price': prop.get('price'),
                    'bedrooms': prop.get('bedrooms'),
                    'bathrooms': prop.get('bathrooms'),
                    'sqft': prop.get('sqft'),
                    'property_type': prop.get('property_type'),
                    'city': prop.get('city'),
                    'address': prop.get('address'),
                    'description': prop.get('description'),
                    'match_score': rec.get('total_score', 0),
                    'match_reasons': rec.get('explanation', {})
                })
        
        # Step 7: Send enhanced email with ML recommendations
        send_enhanced_property_email(email, email_properties, requirements, user_prefs, frequency)
        
        logger.info(f"Enhanced subscription email sent to {email} with {len(email_properties)} properties")
        
    except Exception as e:
        logger.error(f"Error in enhanced user job for {email}: {e}")

def send_enhanced_property_email(email, properties, requirements, user_prefs, frequency):
    """Send enhanced email with ML recommendations and detailed matching"""
    try:
        # Create enhanced email content
        subject = "🏠 Your AI-Powered Property Recommendations"
        
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
        
        <h3>🏠 Top {len(properties)} AI-Recommended Properties</h3>
        """
        
        for i, prop in enumerate(properties, 1):
            match_score = prop.get('match_score', 0)
            email_body += f"""
            <div style="border: 1px solid #ddd; padding: 15px; margin: 10px 0; border-radius: 5px;">
                <h4>#{i} - {prop.get('address', 'Address not available')} ({match_score:.1%} match)</h4>
                <p><strong>Price:</strong> ${prop.get('price', 0):,}</p>
                <p><strong>Details:</strong> {prop.get('bedrooms', 0)} bed, {prop.get('bathrooms', 0)} bath, {prop.get('sqft', 0):,} sqft</p>
                <p><strong>Type:</strong> {prop.get('property_type', 'Unknown')} in {prop.get('city', 'Unknown city')}</p>
                {f"<p><strong>Description:</strong> {prop.get('description', '')[:200]}...</p>" if prop.get('description') else ""}
            </div>
            """
        
        email_body += f"""
        <hr>
        <p><em>🤖 These recommendations were generated using our advanced AI system that analyzed your specific requirements including architectural details, location preferences, and lifestyle needs.</em></p>
        <p><em>⏰ You'll receive updates every {frequency} hours. Reply to this email to modify your preferences.</em></p>
        """
        
        # Use existing email function or create enhanced version
        asyncio.run(send_property_email(email, properties, subject, email_body))
        
    except Exception as e:
        logger.error(f"Error sending enhanced email to {email}: {e}")
        # Fallback to basic email
        asyncio.run(send_property_email(email, properties[:5]))

def schedule_user_task(prompt):
    """Schedule enhanced user task with AI components"""
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
