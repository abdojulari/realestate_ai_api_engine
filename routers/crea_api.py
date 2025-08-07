"""
CREA API Testing Router

This router provides endpoints for testing CREA DDF API functionality,
including token management and property data retrieval.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
from datetime import datetime
import traceback

# Import CREA API components
from api_token_handler import crea_token_handler
from crea_api_client import crea_api
from data_transformer import CREADataTransformer

# Import database components
from database import get_db
from db_models import Property, User, AgentProfile, Listing
from sqlalchemy.orm import Session

# Response models
class TokenStatusResponse(BaseModel):
    """Response model for token status"""
    is_valid: bool
    expires_at: Optional[datetime] = None
    token_preview: Optional[str] = None
    status: str

class APIInfoResponse(BaseModel):
    """Response model for API information"""
    status: str
    metadata_available: Optional[bool] = None
    base_url: str
    error: Optional[str] = None

class PropertySearchRequest(BaseModel):
    """Request model for property search"""
    location: Optional[str] = Field(None, description="City or location to search in")
    min_price: Optional[float] = Field(None, ge=0, description="Minimum list price")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum list price")
    bedrooms: Optional[int] = Field(None, ge=0, description="Minimum number of bedrooms")
    property_type: Optional[str] = Field(None, description="Property subtype (e.g., 'Industrial', 'Office', 'Retail', 'Vacant Land', 'Single Family Detached', 'Condo')")
    top: Optional[int] = Field(10, ge=1, le=100, description="Maximum number of results")

# Create router
router = APIRouter(
    prefix="/crea",
    tags=["CREA API Testing"],
    responses={
        500: {"description": "Internal server error"},
        401: {"description": "Authentication failed"},
    }
)

@router.get(
    "/token/status",
    response_model=TokenStatusResponse,
    summary="Check CREA API Token Status",
    description="Check if the current CREA API token is valid and when it expires"
)
async def get_token_status():
    """
    Get the current status of the CREA API access token.
    
    Returns information about token validity, expiration time, and a preview of the token.
    """
    try:
        is_valid = crea_token_handler.is_token_valid()
        
        response_data = {
            "is_valid": is_valid,
            "status": "valid" if is_valid else "invalid/expired"
        }
        
        if crea_token_handler.token_expires_at:
            response_data["expires_at"] = crea_token_handler.token_expires_at
        
        if crea_token_handler.access_token:
            # Show first 10 and last 4 characters for security
            token = crea_token_handler.access_token
            response_data["token_preview"] = f"{token[:10]}...{token[-4:]}"
        
        return TokenStatusResponse(**response_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check token status: {str(e)}"
        )

@router.post(
    "/token/refresh",
    response_model=TokenStatusResponse,
    summary="Refresh CREA API Token",
    description="Force refresh the CREA API access token and return the new token status"
)
async def refresh_token():
    """
    Force a refresh of the CREA API access token.
    
    This will request a new token from the CREA API regardless of current token status.
    """
    try:
        # Force token refresh by clearing current token
        crea_token_handler.access_token = None
        crea_token_handler.token_expires_at = None
        
        # Get new token
        new_token = crea_token_handler.get_access_token()
        
        response_data = {
            "is_valid": True,
            "expires_at": crea_token_handler.token_expires_at,
            "token_preview": f"{new_token[:10]}...{new_token[-4:]}",
            "status": "refreshed"
        }
        
        return TokenStatusResponse(**response_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh token: {str(e)}"
        )

@router.get(
    "/api/info",
    response_model=APIInfoResponse,
    summary="Get CREA API Information",
    description="Get information about the CREA API connection and metadata availability"
)
async def get_api_info():
    """
    Get information about the CREA API connection.
    
    This endpoint tests the connection to the CREA API and returns metadata information.
    """
    try:
        api_info = crea_api.get_api_info()
        return APIInfoResponse(**api_info)
        
    except Exception as e:
        return APIInfoResponse(
            status="error",
            base_url=crea_api.base_url,
            error=str(e)
        )

@router.get(
    "/properties/search",
    summary="Search Properties",
    description="Search for properties using various filters"
)
async def search_properties(
    location: Optional[str] = Query(None, description="City or location to search in"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    bedrooms: Optional[int] = Query(None, ge=0, description="Minimum number of bedrooms"),
    property_type: Optional[str] = Query(None, description="Type of property"),
    top: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Search for properties using the CREA DDF API.
    
    This endpoint demonstrates the property search functionality and returns
    the raw API response from CREA.
    """
    try:
        # Use the search_properties method from the API client
        result = crea_api.search_properties(
            location=location,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            top=top
        )
        
        return {
            "success": True,
            "total_results": len(result.get("value", [])),
            "search_params": {
                "location": location,
                "min_price": min_price,
                "max_price": max_price,
                "bedrooms": bedrooms,
                "property_type": property_type,
                "top": top
            },
            "data": result
        }
        
    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "search_params": {
                "location": location,
                "min_price": min_price,
                "max_price": max_price,
                "bedrooms": bedrooms,
                "property_type": property_type,
                "top": top
            }
        }
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@router.post(
    "/properties/search",
    summary="Search Properties (POST)",
    description="Search for properties using a JSON request body"
)
async def search_properties_post(search_request: PropertySearchRequest):
    """
    Search for properties using a JSON request body.
    
    This endpoint provides the same functionality as the GET endpoint but
    accepts parameters via a JSON request body.
    """
    try:
        result = crea_api.search_properties(
            location=search_request.location,
            min_price=search_request.min_price,
            max_price=search_request.max_price,
            bedrooms=search_request.bedrooms,
            property_type=search_request.property_type,
            top=search_request.top
        )
        
        return {
            "success": True,
            "total_results": len(result.get("value", [])),
            "search_params": search_request.dict(),
            "data": result
        }
        
    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "search_params": search_request.dict()
        }
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@router.get(
    "/properties/{property_id}",
    summary="Get Property by ID",
    description="Get detailed information about a specific property"
)
async def get_property(property_id: str):
    """
    Get detailed information about a specific property by ID.
    
    Args:
        property_id: The unique identifier for the property
    """
    try:
        result = crea_api.get_properties(property_id=property_id)
        
        return {
            "success": True,
            "property_id": property_id,
            "data": result
        }
        
    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "property_id": property_id
        }
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@router.get(
    "/members",
    summary="Get Members",
    description="Get member information from CREA API"
)
async def get_members(
    member_id: Optional[str] = Query(None, description="Specific member ID to retrieve"),
    top: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Get member information from the CREA DDF API.
    
    This endpoint demonstrates the member data retrieval functionality.
    """
    try:
        filters = {"$top": top} if not member_id else None
        result = crea_api.get_members(member_id=member_id, filters=filters)
        
        return {
            "success": True,
            "member_id": member_id,
            "total_results": len(result.get("value", [])) if "value" in result else 1,
            "data": result
        }
        
    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "member_id": member_id
        }
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@router.get(
    "/openhouses",
    summary="Get Open Houses",
    description="Get open house information from CREA API"
)
async def get_open_houses(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    top: int = Query(10, ge=1, le=100, description="Maximum number of results")
):
    """
    Get open house information from the CREA DDF API.
    
    This endpoint demonstrates the open house data retrieval functionality.
    """
    try:
        if start_date:
            result = crea_api.get_open_houses_by_date(
                start_date=start_date,
                end_date=end_date
            )
        else:
            filters = {"$top": top}
            result = crea_api.get_open_houses(filters=filters)
        
        return {
            "success": True,
            "total_results": len(result.get("value", [])),
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "top": top
            },
            "data": result
        }
        
    except Exception as e:
        error_detail = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "filters": {
                "start_date": start_date,
                "end_date": end_date,
                "top": top
            }
        }
        
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )

@router.get(
    "/test/connection",
    summary="Test CREA API Connection",
    description="Comprehensive test of CREA API connection and functionality"
)
async def test_connection():
    """
    Perform a comprehensive test of the CREA API connection.
    
    This endpoint tests:
    1. Token generation and validation
    2. API connectivity
    3. Basic data retrieval
    """
    test_results = {
        "timestamp": datetime.now().isoformat(),
        "tests": {}
    }
    
    # Test 1: Token Generation
    try:
        token = crea_token_handler.get_access_token()
        test_results["tests"]["token_generation"] = {
            "status": "success",
            "message": "Token generated successfully",
            "token_preview": f"{token[:10]}...{token[-4:]}",
            "expires_at": crea_token_handler.token_expires_at.isoformat() if crea_token_handler.token_expires_at else None
        }
    except Exception as e:
        test_results["tests"]["token_generation"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Test 2: API Info
    try:
        api_info = crea_api.get_api_info()
        test_results["tests"]["api_connection"] = {
            "status": "success" if api_info["status"] == "connected" else "failed",
            "data": api_info
        }
    except Exception as e:
        test_results["tests"]["api_connection"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Test 3: Simple Property Query
    try:
        result = crea_api.get_properties(filters={"$top": 1})
        test_results["tests"]["property_query"] = {
            "status": "success",
            "message": f"Retrieved {len(result.get('value', []))} properties",
            "has_data": len(result.get('value', [])) > 0
        }
    except Exception as e:
        test_results["tests"]["property_query"] = {
            "status": "failed",
            "error": str(e)
        }
    
    # Overall status
    all_tests_passed = all(
        test["status"] == "success" 
        for test in test_results["tests"].values()
    )
    
    test_results["overall_status"] = "success" if all_tests_passed else "partial_failure"
    
    return test_results

# ============================================================================
# DATA TRANSFORMATION AND IMPORT ENDPOINTS
# ============================================================================

class PropertyImportRequest(BaseModel):
    """Request model for importing properties"""
    property_ids: Optional[List[str]] = Field(None, description="Specific CREA property IDs to import")
    search_filters: Optional[Dict] = Field(None, description="Search filters to find properties to import")
    max_properties: Optional[int] = Field(10, ge=1, le=100, description="Maximum number of properties to import")

class ImportedPropertyInfo(BaseModel):
    """Information about an imported property"""
    property_id: str
    agent_id: Optional[str] = None
    listing_id: Optional[str] = None
    mls_number: Optional[str] = None

class PropertyImportResponse(BaseModel):
    """Response model for property import"""
    success: bool
    imported_count: int
    failed_count: int
    imported_properties: List[ImportedPropertyInfo]
    errors: List[str]
    total_time_seconds: float

@router.post(
    "/properties/import",
    response_model=PropertyImportResponse,
    summary="Import CREA Properties to Local Database",
    description="Transform and import CREA properties into the local database with all relationships"
)
async def import_crea_properties(
    import_request: PropertyImportRequest,
    db: Session = Depends(get_db)
):
    """
    Import CREA properties into the local database.
    
    This endpoint:
    1. Fetches properties from CREA API (by ID or search)
    2. Transforms data to local schema format
    3. Creates properties with amenities, images, and relationships
    4. Returns summary of import results
    """
    start_time = datetime.now()
    
    try:
        # Initialize transformer
        transformer = CREADataTransformer(db)
        
        # Get CREA properties to import
        crea_properties = []
        
        if import_request.property_ids:
            # Import specific properties by ID
            for property_id in import_request.property_ids:
                try:
                    result = crea_api.get_properties(property_id=property_id)
                    if result.get('value'):
                        crea_properties.extend(result['value'])
                except Exception as e:
                    print(f"Error fetching property {property_id}: {e}")
                    continue
        
        elif import_request.search_filters:
            # Import properties from search
            try:
                # Use the search_properties method instead of get_properties
                search_params = import_request.search_filters
                result = crea_api.search_properties(
                    location=search_params.get('location'),
                    min_price=search_params.get('min_price'),
                    max_price=search_params.get('max_price'),
                    bedrooms=search_params.get('bedrooms'),
                    property_type=search_params.get('property_type'),
                    top=import_request.max_properties
                )
                if result.get('value'):
                    crea_properties = result['value'][:import_request.max_properties]
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error searching properties: {str(e)}"
                )
        
        else:
            # Default: get recent properties
            try:
                filters = {'$top': import_request.max_properties}
                result = crea_api.get_properties(filters=filters)
                if result.get('value'):
                    crea_properties = result['value'][:import_request.max_properties]
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error fetching properties: {str(e)}"
                )
        
        if not crea_properties:
            return PropertyImportResponse(
                success=True,
                imported_count=0,
                failed_count=0,
                imported_properties=[],
                errors=["No properties found to import"],
                total_time_seconds=0.0
            )
        
        # Transform and import properties
        imported_properties = []
        failed_imports = []
        errors = []
        
        for crea_property in crea_properties:
            try:
                # Check if property already exists (by ListingId or address)
                listing_id = crea_property.get('ListingId')
                address = crea_property.get('UnparsedAddress')
                city = crea_property.get('City')
                
                existing_property = db.query(Property).filter(
                    Property.address == address,
                    Property.city == city
                ).first()
                
                if existing_property:
                    errors.append(f"Property {listing_id} already exists at {address}")
                    failed_imports.append(listing_id)
                    continue
                
                # Transform and create property with agent relationships
                property_obj, agent, listing = transformer.transform_and_create_property_with_agent(crea_property)
                imported_properties.append({
                    "property_id": str(property_obj.property_id),
                    "agent_id": str(agent.user_id) if agent else None,
                    "listing_id": str(listing.listing_id) if listing else None,
                    "mls_number": crea_property.get('ListingId')
                })
                
            except Exception as e:
                error_msg = f"Failed to import property {crea_property.get('ListingId', 'Unknown')}: {str(e)}"
                errors.append(error_msg)
                failed_imports.append(crea_property.get('ListingId', 'Unknown'))
                continue
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        return PropertyImportResponse(
            success=True,
            imported_count=len(imported_properties),
            failed_count=len(failed_imports),
            imported_properties=imported_properties,
            errors=errors,
            total_time_seconds=total_time
        )
        
    except Exception as e:
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc(),
                "total_time_seconds": total_time
            }
        )

@router.post(
    "/properties/transform",
    summary="Transform CREA Property Data (Preview)",
    description="Transform CREA property data without saving to database - for preview/testing"
)
async def transform_crea_property_preview(
    crea_property: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """
    Preview how CREA property data would be transformed without saving to database.
    
    This is useful for testing the transformation logic and seeing what the
    final property data would look like.
    """
    try:
        transformer = CREADataTransformer(db)
        
        # Transform the property data
        property_data, amenity_names, images, room_data = transformer.transform_property(crea_property)
        
        return {
            "success": True,
            "transformed_property": property_data,
            "mapped_amenities": amenity_names,
            "extracted_images": images,
            "room_information": room_data,
            "transformation_summary": {
                "total_amenities": len(amenity_names),
                "total_images": len(images),
                "total_rooms": len(room_data),
                "has_primary_image": any(img.get('is_primary') for img in images),
                "price_formatted": f"${property_data.get('price', 0):,}" if property_data.get('price') else "No price"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )

@router.get(
    "/properties/import/search-and-import",
    response_model=PropertyImportResponse,
    summary="Search and Import Properties",
    description="Search for properties with filters and import them directly"
)
async def search_and_import_properties(
    location: Optional[str] = Query(None, description="City to search in"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    bedrooms: Optional[int] = Query(None, description="Minimum bedrooms"),
    property_type: Optional[str] = Query(None, description="Property type"),
    max_properties: int = Query(5, ge=1, le=50, description="Maximum properties to import"),
    db: Session = Depends(get_db)
):
    """
    Search for properties using filters and import them directly into the database.
    
    This combines the search and import functionality into a single endpoint.
    """
    try:
        # Build search filters
        search_filters = {}
        
        if location:
            search_filters['location'] = location
        if min_price:
            search_filters['min_price'] = min_price
        if max_price:
            search_filters['max_price'] = max_price
        if bedrooms:
            search_filters['bedrooms'] = bedrooms
        if property_type:
            search_filters['property_type'] = property_type
        
        # Create import request
        import_request = PropertyImportRequest(
            search_filters=search_filters,
            max_properties=max_properties
        )
        
        # Use the import endpoint
        return await import_crea_properties(import_request, db)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error in search and import: {str(e)}"
        )

# ============================================================================
# BULK DATA POPULATION ENDPOINTS  
# ============================================================================

@router.post(
    "/bulk/populate-database",
    response_model=PropertyImportResponse,
    summary="Bulk Populate Database with CREA Data",
    description="Import large amounts of CREA data to populate the local database for customer access"
)
async def bulk_populate_database(
    cities: List[str] = Query(..., description="List of cities to import properties from"),
    max_per_city: int = Query(50, ge=1, le=200, description="Maximum properties per city"),
    min_price: Optional[float] = Query(None, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, description="Maximum price filter"),
    property_types: Optional[List[str]] = Query(None, description="Property types to include"),
    db: Session = Depends(get_db)
):
    """
    Bulk populate the local database with CREA properties for customer access.
    
    This endpoint is designed for populating your local property database
    so customers can browse properties through your /api/v1/properties endpoints.
    
    Features:
    - Imports properties with full agent relationships
    - Creates agent profiles automatically
    - Links properties to agents via listings
    - Handles images, amenities, and all relationships
    """
    start_time = datetime.now()
    all_imported = []
    all_errors = []
    
    try:
        transformer = CREADataTransformer(db)
        
        for city in cities:
            try:
                print(f"🏙️  Importing properties from {city}...")
                
                # Search for properties in this city
                result = crea_api.search_properties(
                    location=city,
                    min_price=min_price,
                    max_price=max_price,
                    property_type=property_types[0] if property_types else None,
                    top=max_per_city
                )
                
                if not result.get('value'):
                    all_errors.append(f"No properties found in {city}")
                    continue
                
                city_properties = result['value']
                print(f"📊 Found {len(city_properties)} properties in {city}")
                
                # Import each property
                for crea_property in city_properties:
                    try:
                        # Check for duplicates
                        address = crea_property.get('UnparsedAddress')
                        existing = db.query(Property).filter(
                            Property.address == address,
                            Property.city == city
                        ).first()
                        
                        if existing:
                            continue  # Skip duplicates
                        
                        # Import with agent relationships
                        property_obj, agent, listing = transformer.transform_and_create_property_with_agent(crea_property)
                        
                        all_imported.append(ImportedPropertyInfo(
                            property_id=str(property_obj.property_id),
                            agent_id=str(agent.user_id) if agent else None,
                            listing_id=str(listing.listing_id) if listing else None,
                            mls_number=crea_property.get('ListingId')
                        ))
                        
                    except Exception as e:
                        error_msg = f"Failed to import {crea_property.get('ListingId', 'Unknown')} in {city}: {str(e)}"
                        all_errors.append(error_msg)
                        continue
                
                print(f"✅ Completed {city}: {len([p for p in all_imported if city in str(p.property_id)])} imported")
                
            except Exception as e:
                all_errors.append(f"Error processing city {city}: {str(e)}")
                continue
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        return PropertyImportResponse(
            success=True,
            imported_count=len(all_imported),
            failed_count=len(all_errors),
            imported_properties=all_imported,
            errors=all_errors,
            total_time_seconds=total_time
        )
        
    except Exception as e:
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc(),
                "total_time_seconds": total_time,
                "partial_results": {
                    "imported_count": len(all_imported),
                    "errors": all_errors
                }
            }
        )

@router.get(
    "/agents/import-status",
    summary="Get Agent Import Status",
    description="Get information about agents imported from CREA"
)
async def get_agent_import_status(db: Session = Depends(get_db)):
    """
    Get statistics about agents imported from CREA system.
    """
    try:
        # Count total agents
        total_agents = db.query(User).filter(User.role == 'agent').count()
        
        # Count CREA imported agents (those with specific email pattern)
        crea_agents = db.query(User).filter(
            User.role == 'agent',
            User.email.like('%@crea.imported')
        ).count()
        
        # Get agents with active listings
        agents_with_listings = db.query(User).join(AgentProfile).filter(
            User.role == 'agent',
            AgentProfile.active_listings > 0
        ).count()
        
        # Total active listings
        total_listings = db.query(Listing).count()
        
        return {
            "total_agents": total_agents,
            "crea_imported_agents": crea_agents,
            "agents_with_active_listings": agents_with_listings,
            "total_active_listings": total_listings,
            "import_success_rate": f"{(crea_agents/total_agents*100):.1f}%" if total_agents > 0 else "0%"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting agent status: {str(e)}"
        )

@router.get(
    "/agents/{agent_id}/properties",
    summary="Get Properties Listed by Agent",
    description="Get all properties listed by a specific agent"
)
async def get_agent_properties(
    agent_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all properties listed by a specific agent.
    
    This endpoint shows the agent-property relationships created during import.
    """
    try:
        # Verify agent exists
        agent = db.query(User).filter(
            User.user_id == agent_id,
            User.role == 'agent'
        ).first()
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Get agent's listings with property details
        listings = db.query(Listing).filter(
            Listing.agent_id == agent_id
        ).offset(skip).limit(limit).all()
        
        properties = []
        for listing in listings:
            property_data = {
                "property_id": str(listing.property.property_id),
                "title": listing.property.title,
                "address": listing.property.address,
                "city": listing.property.city,
                "price": float(listing.property.price) if listing.property.price else None,
                "bedrooms": listing.property.bedrooms,
                "bathrooms": float(listing.property.bathrooms) if listing.property.bathrooms else None,
                "square_feet": listing.property.square_feet,
                "mls_number": listing.mls_number,
                "list_date": listing.list_date,
                "status": listing.status_type.status_name if listing.status_type else "Unknown",
                "primary_image": listing.property.primary_image
            }
            properties.append(property_data)
        
        # Get agent information
        agent_info = {
            "agent_id": str(agent.user_id),
            "name": agent.full_name,
            "email": agent.email,
            "phone": agent.phone,
            "agency": agent.agent_profile.agency_name if agent.agent_profile else None,
            "total_listings": len(listings),
            "active_listings": agent.agent_profile.active_listings if agent.agent_profile else 0
        }
        
        return {
            "agent": agent_info,
            "properties": properties,
            "total_properties": len(properties)
        }
        
    except Exception as e:
        if "not found" in str(e):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error getting agent properties: {str(e)}"
        )

# ============================================================================
# DAILY SYNC AND PROVINCE MARKET DATA ENDPOINTS
# ============================================================================

@router.post(
    "/sync/province/{province}",
    summary="Daily Province Market Sync",
    description="Synchronize all property data for a province including status updates"
)
async def sync_province_daily(
    province: str,
    days_back: int = Query(1, ge=1, le=7, description="Days to look back for changes"),
    db: Session = Depends(get_db)
):
    """
    Daily synchronization for a specific province.
    
    This endpoint:
    - Gets all Active, Pending, and Sold properties from CREA
    - Updates existing properties with status changes
    - Creates new properties and agents
    - Tracks agent performance (sales counts)
    - Updates pricing information
    
    Perfect for daily business intelligence updates.
    """
    try:
        start_time = datetime.now()
        transformer = CREADataTransformer(db)
        
        # Run the province sync
        sync_results = transformer.sync_province_market_data(province, days_back)
        
        end_time = datetime.now()
        sync_results['total_time_seconds'] = (end_time - start_time).total_seconds()
        
        return {
            "success": True,
            "province": province,
            "sync_results": sync_results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error syncing {province}: {str(e)}",
                "traceback": traceback.format_exc(),
                "province": province
            }
        )

@router.get(
    "/market/province/{province}",
    summary="Province Market Summary",
    description="Get comprehensive market data for a province"
)
async def get_province_market_summary(
    province: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed market summary for a province including:
    - Property counts by status (Active, Pending, Sold)
    - Top performing agents
    - Agent performance metrics
    - Total market statistics
    """
    try:
        transformer = CREADataTransformer(db)
        
        # Get province summary from local database
        summary = transformer.get_province_summary(province)
        
        return {
            "success": True,
            "data": summary,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting market summary for {province}: {str(e)}"
        )

@router.post(
    "/sync/all-provinces",
    summary="Sync All Major Provinces",
    description="Run daily sync for all major Canadian provinces"
)
async def sync_all_provinces_daily(
    days_back: int = Query(1, ge=1, le=7, description="Days to look back for changes"),
    provinces: List[str] = Query(['AB', 'BC', 'ON'], description="Provinces to sync"),
    db: Session = Depends(get_db)
):
    """
    Run daily synchronization for multiple provinces.
    
    Default provinces: Alberta (AB), British Columbia (BC), Ontario (ON)
    
    Perfect for automated daily market updates across Canada.
    """
    try:
        start_time = datetime.now()
        transformer = CREADataTransformer(db)
        
        all_results = {}
        
        for province in provinces:
            try:
                print(f"🔄 Starting sync for {province}...")
                sync_results = transformer.sync_province_market_data(province, days_back)
                all_results[province] = sync_results
                print(f"✅ Completed {province}")
                
            except Exception as e:
                print(f"❌ Error syncing {province}: {e}")
                all_results[province] = {"error": str(e)}
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # Calculate totals
        total_new = sum([r.get('new_properties', 0) for r in all_results.values() if isinstance(r, dict)])
        total_updated = sum([r.get('updated_properties', 0) for r in all_results.values() if isinstance(r, dict)])
        total_status_changes = sum([r.get('status_changes', 0) for r in all_results.values() if isinstance(r, dict)])
        total_new_agents = sum([r.get('new_agents', 0) for r in all_results.values() if isinstance(r, dict)])
        
        return {
            "success": True,
            "provinces_synced": provinces,
            "results_by_province": all_results,
            "totals": {
                "new_properties": total_new,
                "updated_properties": total_updated,
                "status_changes": total_status_changes,
                "new_agents": total_new_agents
            },
            "total_time_seconds": total_time,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error in multi-province sync: {str(e)}",
                "traceback": traceback.format_exc()
            }
        )

@router.get(
    "/market/agent-performance/{agent_id}",
    summary="Agent Performance Metrics",
    description="Get detailed performance metrics for a specific agent"
)
async def get_agent_performance(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive agent performance data including:
    - Total sales count
    - Active listings
    - Recent activity
    - Performance trends
    """
    try:
        # Get agent with profile
        agent = db.query(User).filter(
            User.user_id == agent_id,
            User.role == 'agent'
        ).first()
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Get agent's listings with status breakdown
        listings = db.query(Listing).filter(
            Listing.agent_id == agent_id
        ).all()
        
        status_breakdown = {}
        for listing in listings:
            status = listing.status_type.status_name if listing.status_type else 'Unknown'
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        # Get recent activity (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        recent_listings = db.query(Listing).filter(
            Listing.agent_id == agent_id,
            Listing.created_at >= thirty_days_ago
        ).count()
        
        recent_sales = db.query(Listing).join(PropertyStatusType).filter(
            Listing.agent_id == agent_id,
            PropertyStatusType.status_name == 'Sold',
            Listing.updated_at >= thirty_days_ago
        ).count()
        
        performance_data = {
            "agent_info": {
                "agent_id": str(agent.user_id),
                "name": agent.full_name,
                "email": agent.email,
                "phone": agent.phone,
                "agency": agent.agent_profile.agency_name if agent.agent_profile else None,
                "license_number": agent.agent_profile.license_number if agent.agent_profile else None
            },
            "performance_metrics": {
                "total_sales": agent.agent_profile.total_sales if agent.agent_profile else 0,
                "active_listings": agent.agent_profile.active_listings if agent.agent_profile else 0,
                "rating": float(agent.agent_profile.rating) if agent.agent_profile and agent.agent_profile.rating else 0.0,
                "total_listings": len(listings)
            },
            "listing_status_breakdown": status_breakdown,
            "recent_activity_30_days": {
                "new_listings": recent_listings,
                "recent_sales": recent_sales
            }
        }
        
        return {
            "success": True,
            "data": performance_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        if "not found" in str(e):
            raise
        raise HTTPException(
            status_code=500,
            detail=f"Error getting agent performance: {str(e)}"
        )

@router.get(
    "/market/daily-report",
    summary="Daily Market Report",
    description="Get comprehensive daily market report across all provinces"
)
async def get_daily_market_report(db: Session = Depends(get_db)):
    """
    Generate a comprehensive daily market report showing:
    - Properties by province and status
    - Agent performance summary
    - Recent market activity
    - Key statistics
    """
    try:
        transformer = CREADataTransformer(db)
        
        # Get data for major provinces
        provinces = ['Alberta', 'British Columbia', 'Ontario']
        province_reports = {}
        
        for province in provinces:
            try:
                summary = transformer.get_province_summary(province)
                province_reports[province] = summary
            except Exception as e:
                province_reports[province] = {"error": str(e)}
        
        # Calculate overall totals
        total_properties = sum([
            r.get('total_properties', 0) 
            for r in province_reports.values() 
            if isinstance(r, dict) and 'total_properties' in r
        ])
        
        total_agents = sum([
            r.get('agent_count', 0) 
            for r in province_reports.values() 
            if isinstance(r, dict) and 'agent_count' in r
        ])
        
        total_active_listings = sum([
            r.get('total_active_listings', 0) 
            for r in province_reports.values() 
            if isinstance(r, dict) and 'total_active_listings' in r
        ])
        
        total_sales = sum([
            r.get('total_sales', 0) 
            for r in province_reports.values() 
            if isinstance(r, dict) and 'total_sales' in r
        ])
        
        return {
            "success": True,
            "report_date": datetime.now().strftime('%Y-%m-%d'),
            "summary": {
                "total_properties": total_properties,
                "total_agents": total_agents,
                "total_active_listings": total_active_listings,
                "total_sales": total_sales,
                "provinces_covered": len([p for p in province_reports.values() if isinstance(p, dict) and 'total_properties' in p])
            },
            "province_breakdown": province_reports,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating daily report: {str(e)}"
        )

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _import_property_batch(transformer, properties: List[Dict], db: Session) -> Tuple[List[Dict], List[str]]:
    """
    Utility function to import a batch of properties with consistent error handling
    
    Returns:
        Tuple of (imported_properties, errors)
    """
    imported_properties = []
    errors = []
    
    for i, crea_property in enumerate(properties, 1):
        try:
            if i % 100 == 0:
                print(f"📈 Progress: {i}/{len(properties)} properties processed...")
            
            # Check for duplicates
            listing_id = crea_property.get('ListingId')
            if not listing_id:
                continue
                
            existing = db.query(Property).join(Listing).filter(
                Listing.mls_number == listing_id
            ).first()
            
            if existing:
                continue  # Skip duplicates
            
            # Transform and create property with agent relationships
            property_obj, agent, listing = transformer.transform_and_create_property_with_agent(crea_property)
            
            imported_properties.append({
                "property_id": str(property_obj.property_id),
                "agent_id": str(agent.user_id) if agent else None,
                "listing_id": str(listing.listing_id) if listing else None,
                "mls_number": listing_id,
                "address": property_obj.address,
                "city": property_obj.city,
                "price": float(property_obj.price) if property_obj.price else None
            })
            
        except Exception as e:
            error_msg = f"Failed to import property {crea_property.get('ListingId', 'Unknown')}: {str(e)}"
            errors.append(error_msg)
            continue
    
    return imported_properties, errors

# ============================================================================
# PAGINATED SEARCH ENDPOINTS (FOR LARGE DATASETS)
# ============================================================================

@router.get(
    "/properties/search-all/{province}",
    summary="Get ALL Properties for Province (Production Ready)",
    description="Fetch ALL properties for a province using optimized @odata.nextLink pagination that works around CREA API limitations"
)
async def search_all_province_properties(
    province: str,
    status_filter: str = Query("Active", description="Property status (Active, Pending, Sold, etc.)"),
    max_results: Optional[int] = Query(None, description="Maximum results to fetch (None = all available)"),
    property_type: Optional[str] = Query(None, description="Filter by property type")
):
    """
    Fetch ALL properties for a province using CREA's @odata.nextLink pagination.
    
    This endpoint demonstrates how to get complete datasets (5000+ properties)
    by automatically following the @odata.nextLink in CREA responses.
    
    Examples:
    - Get ALL active Alberta properties: /properties/search-all/AB
    - Get first 1000 sold Ontario properties: /properties/search-all/ON?status_filter=Sold&max_results=1000
    """
    try:
        start_time = datetime.now()
        
        print(f"🔍 Starting paginated search for ALL {status_filter} properties in {province}...")
        
        # Use paginated search to get ALL properties
        result = crea_api.search_properties_paginated(
            province=province,
            status_filter=status_filter,
            max_results=max_results
        )
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        return {
            "success": True,
            "province": province,
            "status_filter": status_filter,
            "total_properties": result.get('total_results', 0),
            "requests_made": result.get('requests_made', 0),
            "pagination_complete": result.get('pagination_complete', True),
            "search_time_seconds": total_time,
            "sample_properties": result.get('value', [])[:5],  # Show first 5 as samples
            "timestamp": datetime.now().isoformat(),
            "note": f"Retrieved {result.get('total_results', 0)} properties using {result.get('requests_made', 0)} paginated requests"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error in paginated search for {province}: {str(e)}",
                "traceback": traceback.format_exc(),
                "province": province,
                "status_filter": status_filter
            }
        )

@router.post(
    "/bulk/import-all-province",
    summary="Import ALL Properties from Province",
    description="Import ALL properties from a province using paginated search"
)
async def import_all_province_properties(
    province: str,
    max_properties: Optional[int] = Query(None, description="Maximum properties to import (None = all)"),
    db: Session = Depends(get_db)
):
    """
    Import ALL properties from a province using the paginated search.
    
    This endpoint will:
    1. Fetch ALL active properties for the province using @odata.nextLink
    2. Transform and import each property with agent relationships
    3. Provide comprehensive import statistics
    
    Perfect for populating your database with complete provincial datasets.
    """
    try:
        start_time = datetime.now()
        transformer = CREADataTransformer(db)
        
        print(f"🚀 Starting complete province import for {province}...")
        
        # Get ALL properties using paginated search
        result = crea_api.search_properties_paginated(
            province=province,
            status_filter='Active',
            max_results=max_properties
        )
        
        if not result.get('value'):
            return {
                "success": False,
                "error": f"No properties found for {province}",
                "province": province
            }
        
        properties = result['value']
        print(f"📊 Found {len(properties)} properties to import for {province}")
        
        # Import properties using utility function
        imported_properties, errors = _import_property_batch(transformer, properties, db)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        return {
            "success": True,
            "province": province,
            "total_found": len(properties),
            "total_imported": len(imported_properties),
            "total_errors": len(errors),
            "requests_made": result.get('requests_made', 0),
            "import_time_seconds": total_time,
            "imported_properties": imported_properties[:10],  # Show first 10
            "errors": errors[:5],  # Show first 5 errors
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": f"Error importing all properties for {province}: {str(e)}",
                "traceback": traceback.format_exc(),
                "province": province,
                "total_time_seconds": total_time
            }
        )