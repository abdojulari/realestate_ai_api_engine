from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from database import get_db
from schemas import (
    MarketInsightCreate, MarketInsightUpdate, MarketInsightResponse, 
    MarketStats, EconomicIndicators, Message
)
from auth import get_current_active_user
from db_models import User, MarketInsight, Property

router = APIRouter(prefix="/market-insights", tags=["Market Insights"])


@router.get("/", response_model=List[MarketInsightResponse])
async def get_market_insights(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    property_id: Optional[uuid.UUID] = None,
    postal_code: Optional[str] = None,
    min_market_value: Optional[float] = Query(None, ge=0, description="Minimum market value"),
    max_market_value: Optional[float] = Query(None, ge=0, description="Maximum market value"),
    db: Session = Depends(get_db)
):
    """Get market insights with optional filtering."""
    query = db.query(MarketInsight)
    
    if property_id:
        query = query.filter(MarketInsight.property_id == property_id)
    
    if postal_code:
        query = query.filter(MarketInsight.postal_code.ilike(f"%{postal_code}%"))
    
    if min_market_value is not None:
        query = query.filter(MarketInsight.market_value >= min_market_value)
    
    if max_market_value is not None:
        query = query.filter(MarketInsight.market_value <= max_market_value)
    
    market_insights = query.order_by(MarketInsight.created_at.desc()).offset(skip).limit(limit).all()
    
    # Convert database model to response format
    response_data = []
    for insight in market_insights:
        # Parse JSONB fields
        market_stats = None
        if insight.market_stats:
            market_stats = MarketStats(**insight.market_stats)
        
        economic_indicators = None
        if insight.economic_indicators:
            economic_indicators = EconomicIndicators(**insight.economic_indicators)
        
        insight_data = MarketInsightResponse(
            id=insight.id,
            property_id=insight.property_id,
            postal_code=insight.postal_code,
            market_stats=market_stats,
            price_per_sqft=float(insight.price_per_sqft) if insight.price_per_sqft else None,
            style=insight.style,
            time_on_platform=insight.time_on_platform,
            market_value=float(insight.market_value) if insight.market_value else None,
            economic_indicators=economic_indicators,
            created_at=insight.created_at,
            updated_at=insight.updated_at
        )
        response_data.append(insight_data)
    
    return response_data


@router.get("/{insight_id}", response_model=MarketInsightResponse)
async def get_market_insight(
    insight_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific market insight by ID."""
    insight = db.query(MarketInsight).filter(MarketInsight.id == insight_id).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="Market insight not found")
    
    # Parse JSONB fields
    market_stats = None
    if insight.market_stats:
        market_stats = MarketStats(**insight.market_stats)
    
    economic_indicators = None
    if insight.economic_indicators:
        economic_indicators = EconomicIndicators(**insight.economic_indicators)
    
    return MarketInsightResponse(
        id=insight.id,
        property_id=insight.property_id,
        postal_code=insight.postal_code,
        market_stats=market_stats,
        price_per_sqft=float(insight.price_per_sqft) if insight.price_per_sqft else None,
        style=insight.style,
        time_on_platform=insight.time_on_platform,
        market_value=float(insight.market_value) if insight.market_value else None,
        economic_indicators=economic_indicators,
        created_at=insight.created_at,
        updated_at=insight.updated_at
    )


@router.get("/property/{property_id}", response_model=MarketInsightResponse)
async def get_market_insight_by_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get market insight for a specific property."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    insight = db.query(MarketInsight).filter(MarketInsight.property_id == property_id).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="Market insight not found for this property")
    
    # Parse JSONB fields
    market_stats = None
    if insight.market_stats:
        market_stats = MarketStats(**insight.market_stats)
    
    economic_indicators = None
    if insight.economic_indicators:
        economic_indicators = EconomicIndicators(**insight.economic_indicators)
    
    return MarketInsightResponse(
        id=insight.id,
        property_id=insight.property_id,
        postal_code=insight.postal_code,
        market_stats=market_stats,
        price_per_sqft=float(insight.price_per_sqft) if insight.price_per_sqft else None,
        style=insight.style,
        time_on_platform=insight.time_on_platform,
        market_value=float(insight.market_value) if insight.market_value else None,
        economic_indicators=economic_indicators,
        created_at=insight.created_at,
        updated_at=insight.updated_at
    )


@router.post("/", response_model=MarketInsightResponse)
async def create_market_insight(
    insight_data: MarketInsightCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new market insight entry."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == insight_data.property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Check if market insight already exists for this property
    existing_insight = db.query(MarketInsight).filter(MarketInsight.property_id == insight_data.property_id).first()
    if existing_insight:
        raise HTTPException(status_code=400, detail="Market insight already exists for this property")
    
    # Convert Pydantic models to dict for JSONB storage
    market_stats_dict = insight_data.market_stats.dict() if insight_data.market_stats else {}
    economic_indicators_dict = insight_data.economic_indicators.dict() if insight_data.economic_indicators else {}
    
    # Create market insight
    db_insight = MarketInsight(
        property_id=insight_data.property_id,
        postal_code=insight_data.postal_code,
        market_stats=market_stats_dict,
        price_per_sqft=insight_data.price_per_sqft,
        style=insight_data.style,
        time_on_platform=insight_data.time_on_platform,
        market_value=insight_data.market_value,
        economic_indicators=economic_indicators_dict
    )
    
    db.add(db_insight)
    db.commit()
    db.refresh(db_insight)
    
    # Parse back for response
    market_stats = None
    if db_insight.market_stats:
        market_stats = MarketStats(**db_insight.market_stats)
    
    economic_indicators = None
    if db_insight.economic_indicators:
        economic_indicators = EconomicIndicators(**db_insight.economic_indicators)
    
    return MarketInsightResponse(
        id=db_insight.id,
        property_id=db_insight.property_id,
        postal_code=db_insight.postal_code,
        market_stats=market_stats,
        price_per_sqft=float(db_insight.price_per_sqft) if db_insight.price_per_sqft else None,
        style=db_insight.style,
        time_on_platform=db_insight.time_on_platform,
        market_value=float(db_insight.market_value) if db_insight.market_value else None,
        economic_indicators=economic_indicators,
        created_at=db_insight.created_at,
        updated_at=db_insight.updated_at
    )


@router.put("/{insight_id}", response_model=MarketInsightResponse)
async def update_market_insight(
    insight_id: int,
    insight_data: MarketInsightUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a market insight entry."""
    insight = db.query(MarketInsight).filter(MarketInsight.id == insight_id).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="Market insight not found")
    
    # Update fields if provided
    update_data = insight_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "market_stats" and value:
            insight.market_stats = value.dict() if hasattr(value, 'dict') else value
        elif field == "economic_indicators" and value:
            insight.economic_indicators = value.dict() if hasattr(value, 'dict') else value
        else:
            setattr(insight, field, value)
    
    db.commit()
    db.refresh(insight)
    
    # Parse back for response
    market_stats = None
    if insight.market_stats:
        market_stats = MarketStats(**insight.market_stats)
    
    economic_indicators = None
    if insight.economic_indicators:
        economic_indicators = EconomicIndicators(**insight.economic_indicators)
    
    return MarketInsightResponse(
        id=insight.id,
        property_id=insight.property_id,
        postal_code=insight.postal_code,
        market_stats=market_stats,
        price_per_sqft=float(insight.price_per_sqft) if insight.price_per_sqft else None,
        style=insight.style,
        time_on_platform=insight.time_on_platform,
        market_value=float(insight.market_value) if insight.market_value else None,
        economic_indicators=economic_indicators,
        created_at=insight.created_at,
        updated_at=insight.updated_at
    )


@router.put("/property/{property_id}", response_model=MarketInsightResponse)
async def update_market_insight_by_property(
    property_id: uuid.UUID,
    insight_data: MarketInsightUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update market insight for a specific property."""
    # Verify property exists
    property_exists = db.query(Property).filter(Property.property_id == property_id).first()
    if not property_exists:
        raise HTTPException(status_code=404, detail="Property not found")
    
    insight = db.query(MarketInsight).filter(MarketInsight.property_id == property_id).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="Market insight not found for this property")
    
    # Update fields if provided
    update_data = insight_data.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "market_stats" and value:
            insight.market_stats = value.dict() if hasattr(value, 'dict') else value
        elif field == "economic_indicators" and value:
            insight.economic_indicators = value.dict() if hasattr(value, 'dict') else value
        else:
            setattr(insight, field, value)
    
    db.commit()
    db.refresh(insight)
    
    # Parse back for response
    market_stats = None
    if insight.market_stats:
        market_stats = MarketStats(**insight.market_stats)
    
    economic_indicators = None
    if insight.economic_indicators:
        economic_indicators = EconomicIndicators(**insight.economic_indicators)
    
    return MarketInsightResponse(
        id=insight.id,
        property_id=insight.property_id,
        postal_code=insight.postal_code,
        market_stats=market_stats,
        price_per_sqft=float(insight.price_per_sqft) if insight.price_per_sqft else None,
        style=insight.style,
        time_on_platform=insight.time_on_platform,
        market_value=float(insight.market_value) if insight.market_value else None,
        economic_indicators=economic_indicators,
        created_at=insight.created_at,
        updated_at=insight.updated_at
    )


@router.delete("/{insight_id}", response_model=Message)
async def delete_market_insight(
    insight_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Delete a market insight entry."""
    insight = db.query(MarketInsight).filter(MarketInsight.id == insight_id).first()
    
    if not insight:
        raise HTTPException(status_code=404, detail="Market insight not found")
    
    db.delete(insight)
    db.commit()
    
    return Message(message="Market insight deleted successfully")


@router.get("/postal-code/{postal_code}", response_model=List[MarketInsightResponse])
async def get_market_insights_by_postal_code(
    postal_code: str,
    db: Session = Depends(get_db)
):
    """Get market insights for a specific postal code."""
    insights = db.query(MarketInsight).filter(
        MarketInsight.postal_code.ilike(f"%{postal_code}%")
    ).order_by(MarketInsight.created_at.desc()).all()
    
    # Convert to response format
    response_data = []
    for insight in insights:
        # Parse JSONB fields
        market_stats = None
        if insight.market_stats:
            market_stats = MarketStats(**insight.market_stats)
        
        economic_indicators = None
        if insight.economic_indicators:
            economic_indicators = EconomicIndicators(**insight.economic_indicators)
        
        insight_data = MarketInsightResponse(
            id=insight.id,
            property_id=insight.property_id,
            postal_code=insight.postal_code,
            market_stats=market_stats,
            price_per_sqft=float(insight.price_per_sqft) if insight.price_per_sqft else None,
            style=insight.style,
            time_on_platform=insight.time_on_platform,
            market_value=float(insight.market_value) if insight.market_value else None,
            economic_indicators=economic_indicators,
            created_at=insight.created_at,
            updated_at=insight.updated_at
        )
        response_data.append(insight_data)
    
    return response_data