from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import uvicorn
from contextlib import asynccontextmanager
import hashlib
import json
import time

# Import database setup
from database import engine
from db_models import Base

# Import routers
from routers import users, properties, amenities, saved_searches, views, ai, property_types, agent_discovery, property_interests, notifications, agent_profiles, neighbourhoods, schools, market_insights, crea_api, market_data, dailytips, leads, emails, agent_onboarding
# Note: Removed legacy 'agents' router - now using enhanced agent_discovery and agent_profiles

# Import existing functionality
from parser import extract_filters
from scheduler import schedule_user_task
from models import Prompt

# Simple mock function for legacy endpoint
def search_properties(filters):
    """Mock function for legacy endpoint compatibility."""
    return []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown

# Create FastAPI app with lifespan
app = FastAPI(
    title="Real Estate AI Engine API",
    description="Real estate management API with search, users, agents, and market data",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add ETag and caching middleware
@app.middleware("http")
async def add_etag_and_cache_headers(request: Request, call_next):
    """Add ETag and cache headers for better performance."""
    
    # Skip ETag for non-GET requests
    if request.method != "GET":
        response = await call_next(request)
        return response
    
    # Check if client sent If-None-Match header
    if_none_match = request.headers.get("if-none-match")
    
    # Process the request
    response = await call_next(request)
    
    # Only add ETag for successful JSON responses
    if (response.status_code == 200 and 
        response.headers.get("content-type", "").startswith("application/json")):
        
        # Get response body for ETag calculation
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Calculate ETag based on content
        etag = hashlib.md5(response_body).hexdigest()
        
        # Check if client has the same version
        if if_none_match and if_none_match.strip('"') == etag:
            return Response(status_code=304, headers={
                "ETag": f'"{etag}"',
                "Cache-Control": "public, max-age=300"  # 5 minutes
            })
        
        # Add ETag and cache headers to response
        response.headers["ETag"] = f'"{etag}"'
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
        
        # Recreate response with body
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.headers.get("content-type")
        )
    
    return response

# Include routers
app.include_router(users.router, prefix="/api/v1")
app.include_router(properties.router, prefix="/api/v1")
app.include_router(property_types.router, prefix="/api/v1")
app.include_router(amenities.router, prefix="/api/v1")
# Legacy agents router removed - using enhanced agent_discovery instead
app.include_router(saved_searches.router, prefix="/api/v1")
app.include_router(views.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")

# Enhanced role-based routers
app.include_router(agent_discovery.router, prefix="/api/v1")
app.include_router(property_interests.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(agent_profiles.router, prefix="/api/v1")

# Property-related data routers
app.include_router(neighbourhoods.router, prefix="/api/v1")
app.include_router(schools.router, prefix="/api/v1")
app.include_router(market_insights.router, prefix="/api/v1")

# CREA API testing router
app.include_router(crea_api.router, prefix="/api/v1")

# Market data router
app.include_router(market_data.router)

# Daily Tips (Admin only)
app.include_router(dailytips.router, prefix="/api/v1")

# Lead Management System
app.include_router(leads.router, prefix="/api/v1")

# Email Service API
app.include_router(emails.router, prefix="/api/v1")
app.include_router(agent_onboarding.router, prefix="/api/v1")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "message": "Real Estate AI Engine is running"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to Real Estate AI Engine API",
        "version": "3.0.0",
        "docs": "/docs",
        "health": "/health",
        "features": {
            "property_search": "Search listings with filters parsed from plain text",
            "role_based_access": "Admin, Agent, Customer, Client roles",
            "agent_discovery": "Find and connect with real estate agents",
            "client_management": "Agent-client relationship management",
            "notifications": "Real-time email and in-app notifications",
            "property_interests": "Track and manage property interests"
        },
        "ai_endpoints": {
            "parse": "/api/v1/ai/parse",
            "subscribe": "/api/v1/ai/subscribe",
            "recommendations": "/api/v1/ai/recommend-properties",
            "market_analysis": "/api/v1/ai/analyze-market",
            "generate_description": "/api/v1/ai/generate-description"
        },
        "public_endpoints": {
            "properties": "/api/v1/properties",
            "discover_agents": "/api/v1/agents",
            "agent_profiles": "/api/v1/agent-profiles",
            "agent_properties": "/api/v1/agents/{agent_id}/properties",
            "neighbourhoods": "/api/v1/neighbourhoods",
            "schools": "/api/v1/schools",
            "market_insights": "/api/v1/market-insights"
        },
        "authenticated_endpoints": {
            "users": "/api/v1/users",
            "my_interests": "/api/v1/property-interests/my-interests",
            "notifications": "/api/v1/notifications",
            "request_agent": "/api/v1/agents/request-representation"
        },
        "agent_endpoints": {
            "my_profile": "/api/v1/agent-profiles/my-profile",
            "my_clients": "/api/v1/agents/my-clients",
            "manage_properties": "/api/v1/properties",
            "client_interests": "/api/v1/property-interests/client/{client_id}"
        },
        "admin_endpoints": {
            "manage_users": "/api/v1/users",
            "manage_amenities": "/api/v1/amenities",
            "manage_property_types": "/api/v1/property-types"
        }
    }

# Legacy AI endpoints (keeping existing functionality for backward compatibility)
@app.post("/parse", tags=["Legacy Endpoints"])
def parse_prompt(prompt: Prompt):
    """Legacy endpoint - use /api/v1/ai/parse instead."""
    try:
        filters = extract_filters(prompt.prompt)
        listings = search_properties(filters)
        return {"filters": filters, "results": listings[:10]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing prompt: {str(e)}")

@app.post("/subscribe", tags=["Legacy Endpoints"])
def subscribe_user(prompt: Prompt):
    """Legacy endpoint - use /api/v1/ai/subscribe instead."""
    try:
        schedule_user_task(prompt)
        return {"status": "scheduled", "message": "User subscribed to property alerts"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error subscribing user: {str(e)}")

# Global exception handler
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc):
    """Handle SQLAlchemy database errors."""
    return JSONResponse(
        status_code=500,
        content={"detail": "Database error occurred. Please try again later."}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle unexpected errors."""
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
