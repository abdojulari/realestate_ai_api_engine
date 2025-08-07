from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import Prompt
from auth import get_current_user_optional
from db_models import User

# Import AI functions
from parser import extract_filters
from embedder import generate_embedding
from connector_mock import search_properties
from matcher import rank_listings
from scheduler import schedule_user_task

router = APIRouter(prefix="/ai", tags=["AI & Natural Language Processing"])

@router.post("/parse")
async def parse_prompt(
    prompt: Prompt,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Parse natural language prompt into property filters and return ranked results.
    
    This endpoint uses AI to:
    1. Extract structured filters from natural language
    2. Generate semantic embeddings
    3. Search properties based on filters
    4. Rank results by relevance
    """
    try:
        # Extract filters from natural language prompt
        filters = extract_filters(prompt.prompt)
        
        # Generate embedding for semantic search
        embedding = generate_embedding(prompt.prompt)
        
        # Search properties using extracted filters
        listings = search_properties(filters)
        
        # Rank listings by semantic similarity
        ranked = rank_listings(listings, embedding)
        
        return {
            "query": prompt.prompt,
            "filters": filters,
            "results": ranked[:10],
            "total_results": len(ranked)
        }
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
    Generate AI-powered property descriptions from features.
    
    Takes property features and generates compelling marketing descriptions.
    """
    try:
        # This could be expanded with actual AI text generation
        # For now, we'll create a basic template-based description
        
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
            "confidence": 0.85
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
    Analyze market trends for a specific location and property type.
    
    This endpoint provides AI-powered market insights and trends.
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
            "ai_confidence": 0.78
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
    Get AI-powered property recommendations based on user preferences.
    
    Uses machine learning to suggest properties matching user criteria.
    """
    try:
        # Generate embedding for user preferences
        preference_text = " ".join([f"{k}: {v}" for k, v in user_preferences.items()])
        embedding = generate_embedding(preference_text)
        
        # Mock recommendation logic - in production this would use ML models
        recommendations = {
            "user_preferences": user_preferences,
            "recommended_properties": [
                {
                    "property_id": "mock-1",
                    "title": "Perfect Match Home",
                    "match_score": 0.92,
                    "reasons": ["Matches bedroom count", "Within price range", "Preferred neighborhood"]
                },
                {
                    "property_id": "mock-2", 
                    "title": "Great Alternative",
                    "match_score": 0.85,
                    "reasons": ["Similar features", "Good value", "Near desired amenities"]
                }
            ],
            "algorithm_confidence": 0.88
        }
        
        return recommendations
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating recommendations: {str(e)}")

# Legacy endpoints for backward compatibility
@router.post("/parse-legacy", include_in_schema=False)
async def parse_prompt_legacy(prompt: Prompt):
    """Legacy endpoint - use /ai/parse instead."""
    return await parse_prompt(prompt)

@router.post("/subscribe-legacy", include_in_schema=False)
async def subscribe_user_legacy(prompt: Prompt):
    """Legacy endpoint - use /ai/subscribe instead."""
    return await subscribe_user(prompt) 