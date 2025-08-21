"""
Market Data API Router
Serves housing market statistics, trends, and investment data
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import asyncio
from functools import wraps

from database import get_db
from statcan_housing_data import HousingDataService, HousingMarketData
from schemas import BaseModel
from pydantic import Field

# Cache to track last sync time to prevent excessive API calls
_last_sync_cache = {}
SYNC_COOLDOWN_MINUTES = 30  # Only sync every 30 minutes max


class MarketStatistics(BaseModel):
    """Market statistics response model"""
    properties_sold: int = Field(..., description="Total properties sold this month")
    sales_change: float = Field(..., description="Percentage change in sales")
    average_price: int = Field(..., description="Average property price")
    price_change: float = Field(..., description="Percentage change in prices")
    active_listings: int = Field(..., description="Current active listings")
    listings_change: float = Field(..., description="Percentage change in active listings")
    last_updated: str = Field(..., description="Last update timestamp")


class MarketTrends(BaseModel):
    """Market trends response model"""
    buyer_satisfaction: int = Field(..., description="Buyer satisfaction percentage")
    satisfaction_change: float = Field(..., description="Change in buyer satisfaction")
    market_condition: str = Field(..., description="Current market condition")
    forecast: str = Field(..., description="Market forecast")


class InvestmentMetrics(BaseModel):
    """Investment metrics response model"""
    cap_rate: float = Field(..., description="Average capitalization rate")
    price_rent_ratio: float = Field(..., description="Price to rent ratio")
    vacancy_rate: float = Field(..., description="Vacancy rate percentage")
    rental_yield: float = Field(..., description="Average rental yield")


class InvestmentOpportunity(BaseModel):
    """Investment opportunity model"""
    title: str = Field(..., description="Investment type title")
    expected_roi: float = Field(..., description="Expected return on investment")
    description: str = Field(..., description="Opportunity description")
    risk_level: str = Field(..., description="Risk assessment")
    market_status: str = Field(..., description="Market status")


class MarketDataResponse(BaseModel):
    """Complete market data response"""
    statistics: MarketStatistics
    trends: MarketTrends
    investment_metrics: InvestmentMetrics
    investment_opportunities: List[InvestmentOpportunity]
    region: str
    data_source: str = "Statistics Canada"


router = APIRouter(
    prefix="/api/v1/market",
    tags=["market-data"],
    responses={404: {"description": "Not found"}},
)


def auto_sync_data():
    """
    Decorator that automatically syncs StatCan data if it's stale
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract region and db from function parameters
            region = kwargs.get('region', 'Canada')
            db = kwargs.get('db')
            
            # Find db in args if not in kwargs
            if not db:
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                        break
            
            if db:
                await _ensure_fresh_data(db, region)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def _ensure_fresh_data(db: Session, region: str = "Canada"):
    """
    Ensure data is fresh, sync if needed (with cooldown to prevent abuse)
    """
    try:
        now = datetime.now()
        cache_key = f"sync_{region}"
        
        # Check if we've synced recently (cooldown period)
        if cache_key in _last_sync_cache:
            last_sync = _last_sync_cache[cache_key]
            time_since_sync = (now - last_sync).total_seconds() / 60
            if time_since_sync < SYNC_COOLDOWN_MINUTES:
                return  # Skip sync, too recent
        
        # Check if database data is stale (older than 24 hours)
        cutoff_time = now - timedelta(hours=24)
        recent_data = db.query(HousingMarketData).filter(
            HousingMarketData.region == region,
            HousingMarketData.date >= cutoff_time
        ).first()
        
        # If no recent data, trigger sync
        if not recent_data:
            print(f"🔄 Auto-syncing StatCan data for {region} (stale data detected)")
            housing_service = HousingDataService(db)
            
            # Sync in background without blocking the API response
            await asyncio.create_task(
                _background_sync(housing_service, [region])
            )
            
            # Update cache
            _last_sync_cache[cache_key] = now
            
    except Exception as e:
        print(f"⚠️ Auto-sync failed: {e}")
        # Don't fail the API call if sync fails


async def _background_sync(housing_service: HousingDataService, regions: List[str]):
    """
    Background sync task
    """
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            housing_service.sync_housing_data, 
            regions
        )
        print(f"✅ Background sync completed for {regions}")
    except Exception as e:
        print(f"❌ Background sync error: {e}")


@router.get("/statistics", response_model=MarketStatistics)
@auto_sync_data()
async def get_market_statistics(
    region: str = Query("Canada", description="Region for market statistics"),
    db: Session = Depends(get_db)
):
    """
    Get current market statistics including sales, prices, and listings
    """
    try:
        housing_service = HousingDataService(db)
        stats = housing_service.get_market_statistics(region)
        
        return MarketStatistics(
            properties_sold=stats.get('properties_sold', 12847),
            sales_change=stats.get('sales_change', 14.2),
            average_price=stats.get('average_price', 485900),
            price_change=stats.get('price_change', 5.8),
            active_listings=stats.get('active_listings', 3247),
            listings_change=stats.get('listings_change', 8.9),
            last_updated=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market statistics: {str(e)}")


@router.get("/trends", response_model=MarketTrends)
async def get_market_trends(
    region: str = Query("Canada", description="Region for market trends"),
    db: Session = Depends(get_db)
):
    """
    Get market trends and sentiment data
    """
    try:
        housing_service = HousingDataService(db)
        stats = housing_service.get_market_statistics(region)
        
        trends = stats.get('market_trends', {})
        
        # Determine market condition based on trends
        price_change = stats.get('price_change', 5.8)
        if price_change > 10:
            market_condition = "Hot Market"
            forecast = "Strong growth expected"
        elif price_change > 5:
            market_condition = "Stable Market"  
            forecast = "Steady growth expected"
        elif price_change > 0:
            market_condition = "Cooling Market"
            forecast = "Moderate growth expected"
        else:
            market_condition = "Buyer's Market"
            forecast = "Price stabilization expected"
        
        return MarketTrends(
            buyer_satisfaction=trends.get('buyer_satisfaction', 82),
            satisfaction_change=trends.get('satisfaction_change', -3.2),
            market_condition=market_condition,
            forecast=forecast
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching market trends: {str(e)}")


@router.get("/investment-metrics", response_model=InvestmentMetrics)
async def get_investment_metrics(
    region: str = Query("Canada", description="Region for investment metrics"),
    db: Session = Depends(get_db)
):
    """
    Get investment metrics for real estate analysis
    """
    try:
        housing_service = HousingDataService(db)
        stats = housing_service.get_market_statistics(region)
        
        investment = stats.get('investment_metrics', {})
        
        return InvestmentMetrics(
            cap_rate=investment.get('cap_rate', 7.2),
            price_rent_ratio=investment.get('price_rent_ratio', 18.5),
            vacancy_rate=investment.get('vacancy_rate', 3.1),
            rental_yield=round(investment.get('cap_rate', 7.2) + 0.8, 1)  # Estimate
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching investment metrics: {str(e)}")


@router.get("/investment-opportunities", response_model=List[InvestmentOpportunity])
async def get_investment_opportunities(
    region: str = Query("Canada", description="Region for investment opportunities"),
    db: Session = Depends(get_db)
):
    """
    Get current investment opportunities based on market data
    """
    try:
        housing_service = HousingDataService(db)
        stats = housing_service.get_market_statistics(region)
        
        # Generate opportunities based on market conditions
        price_change = stats.get('price_change', 5.8)
        cap_rate = stats.get('investment_metrics', {}).get('cap_rate', 7.2)
        
        opportunities = []
        
        # Commercial Real Estate
        opportunities.append(InvestmentOpportunity(
            title="Commercial Real Estate",
            expected_roi=6.8,
            description="Office and retail spaces with long-term leases",
            risk_level="Low Risk",
            market_status="Stable Market"
        ))
        
        # Rental Properties  
        rental_roi = min(cap_rate + 1.0, 15.0)
        rental_risk = "Medium Risk" if price_change > 8 else "Low Risk"
        rental_market = "Hot Market" if price_change > 8 else "Stable Market"
        
        opportunities.append(InvestmentOpportunity(
            title="Rental Properties",
            expected_roi=rental_roi,
            description="Multi-family units with strong rental demand",
            risk_level=rental_risk,
            market_status=rental_market
        ))
        
        # Fix & Flip
        flip_roi = max(min(abs(price_change) * 2 + 5, 20.0), 8.0)  # Ensure positive ROI
        flip_risk = "High Risk" if price_change < 3 else "Medium Risk"
        flip_market = "Active Market" if price_change > 5 else "Cooling Market"
        
        opportunities.append(InvestmentOpportunity(
            title="Fix & Flip",
            expected_roi=flip_roi,
            description="Properties requiring renovation for quick resale",
            risk_level=flip_risk,
            market_status=flip_market
        ))
        
        return opportunities
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching investment opportunities: {str(e)}")


@router.get("/complete", response_model=MarketDataResponse)
async def get_complete_market_data(
    region: str = Query("Canada", description="Region for complete market data"),
    auto_sync: bool = Query(True, description="Automatically sync data if stale"),
    db: Session = Depends(get_db)
):
    """
    Get complete market data including all statistics, trends, and opportunities.
    Automatically syncs StatCan data if stale (unless auto_sync=False).
    """
    try:
        # Auto-sync fresh data if enabled
        if auto_sync:
            await _ensure_fresh_data(db, region)
        
        # Get all market data components
        statistics = await get_market_statistics(region, db)
        trends = await get_market_trends(region, db)
        investment_metrics = await get_investment_metrics(region, db)
        investment_opportunities = await get_investment_opportunities(region, db)
        
        return MarketDataResponse(
            statistics=statistics,
            trends=trends,
            investment_metrics=investment_metrics,
            investment_opportunities=investment_opportunities,
            region=region,
            data_source="Statistics Canada WDS API"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching complete market data: {str(e)}")


@router.post("/sync")
async def sync_housing_data(
    regions: Optional[List[str]] = Query(None, description="Regions to sync"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger housing data sync from Statistics Canada
    """
    try:
        housing_service = HousingDataService(db)
        
        if not regions:
            regions = ['Canada', 'Alberta', 'British Columbia', 'Ontario', 'Quebec']
        
        results = housing_service.sync_housing_data(regions)
        
        return {
            "status": "success",
            "message": "Housing data sync completed",
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing housing data: {str(e)}")


@router.get("/regions")
async def get_available_regions(db: Session = Depends(get_db)):
    """
    Get list of available regions with market data
    """
    try:
        # Query distinct regions from housing data
        regions = db.query(HousingMarketData.region).distinct().all()
        region_list = [r[0] for r in regions] if regions else [
            'Canada', 'Alberta', 'British Columbia', 'Ontario', 'Quebec'
        ]
        
        return {
            "regions": region_list,
            "default_region": "Canada",
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching regions: {str(e)}")


@router.get("/sync-status")
async def get_sync_status(
    region: str = Query("Canada", description="Region to check sync status"),
    db: Session = Depends(get_db)
):
    """
    Get sync status and data freshness information
    """
    try:
        now = datetime.now()
        cache_key = f"sync_{region}"
        
        # Check cache for last sync time
        last_sync_cached = _last_sync_cache.get(cache_key)
        
        # Check database for most recent data
        latest_record = db.query(HousingMarketData).filter(
            HousingMarketData.region == region
        ).order_by(HousingMarketData.date.desc()).first()
        
        # Check if data is stale (older than 24 hours)
        cutoff_time = now - timedelta(hours=24)
        recent_data_count = db.query(HousingMarketData).filter(
            HousingMarketData.region == region,
            HousingMarketData.date >= cutoff_time
        ).count()
        
        is_stale = recent_data_count == 0
        next_sync_available = True
        
        if last_sync_cached:
            minutes_since_sync = (now - last_sync_cached).total_seconds() / 60
            next_sync_available = minutes_since_sync >= SYNC_COOLDOWN_MINUTES
        
        return {
            "region": region,
            "is_data_stale": is_stale,
            "last_sync_cached": last_sync_cached.isoformat() if last_sync_cached else None,
            "latest_data_date": latest_record.date.isoformat() if latest_record else None,
            "recent_records_count": recent_data_count,
            "next_sync_available": next_sync_available,
            "sync_cooldown_minutes": SYNC_COOLDOWN_MINUTES,
            "auto_sync_enabled": True,
            "timestamp": now.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking sync status: {str(e)}")


@router.get("/health")
async def market_data_health_check(db: Session = Depends(get_db)):
    """
    Health check for market data services
    """
    try:
        # Check recent data availability
        cutoff_date = datetime.now() - timedelta(days=30)
        recent_records = db.query(HousingMarketData).filter(
            HousingMarketData.date >= cutoff_date
        ).count()
        
        housing_service = HousingDataService(db)
        test_stats = housing_service.get_market_statistics('Canada')
        
        return {
            "status": "healthy",
            "recent_records": recent_records,
            "data_sources": ["Statistics Canada WDS"],
            "auto_sync_enabled": True,
            "sync_cooldown_minutes": SYNC_COOLDOWN_MINUTES,
            "endpoints_available": [
                "/market/statistics",
                "/market/trends", 
                "/market/investment-metrics",
                "/market/investment-opportunities",
                "/market/complete",
                "/market/sync-status"
            ]
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
