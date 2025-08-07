from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import uvicorn
from contextlib import asynccontextmanager

# Import database setup
from database import create_tables, engine
from db_models import Base

# Import routers
from routers import users, properties, amenities, saved_searches, views, ai, property_types, agent_discovery, property_interests, notifications, agent_profiles, neighbourhoods, schools, market_insights, crea_api
# Note: Removed legacy 'agents' router - now using enhanced agent_discovery and agent_profiles

# Import existing functionality
from parser import extract_filters
from embedder import generate_embedding
from connector_mock import search_properties
from matcher import rank_listings
from scheduler import schedule_user_task
from models import Prompt

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")
    yield
    # Shutdown
    print("Application shutting down...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="Real Estate AI Engine API",
    description="Comprehensive real estate management API with AI-powered search and recommendations",
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
            "ai_powered_search": "Advanced property search with NLP",
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
        embedding = generate_embedding(prompt.prompt)
        listings = search_properties(filters)
        ranked = rank_listings(listings, embedding)
        return {"filters": filters, "results": ranked[:10]}
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
