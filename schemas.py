from pydantic import BaseModel, EmailStr, validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
import uuid

# User schemas
class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = 'customer'
    
    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['customer', 'client', 'agent', 'admin']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {allowed_roles}')
        return v

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None

class UserResponse(UserBase):
    user_id: uuid.UUID
    role: str
    is_active: bool
    full_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Property Type schemas
class PropertyTypeBase(BaseModel):
    type_name: str
    description: Optional[str] = None

class PropertyTypeCreate(PropertyTypeBase):
    pass

class PropertyTypeResponse(PropertyTypeBase):
    type_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Property schemas
class PropertyBase(BaseModel):
    title: str
    description: Optional[str] = None
    address: str
    city: str
    province: str
    postal_code: Optional[str] = None
    location_display: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    price: Optional[Decimal] = None
    price_type: Optional[str] = 'List Price'
    hoa_fee: Optional[Decimal] = 0
    property_type_id: Optional[int] = None
    bedrooms: Optional[int] = 0
    bathrooms: Optional[Decimal] = 0
    square_feet: Optional[int] = None
    lot_size: Optional[int] = None
    year_built: Optional[int] = None
    parking_spots: Optional[int] = 0
    has_garage: Optional[bool] = False
    has_basement: Optional[bool] = False
    single_story_only: Optional[bool] = False
    stories: Optional[int] = 1
    status: Optional[str] = 'available'
    is_new: Optional[bool] = False
    primary_image: Optional[str] = None
    images: Optional[List[str]] = None

# Image Management Schemas
class PropertyImageBase(BaseModel):
    url: str
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    is_primary: Optional[bool] = False
    order_index: Optional[int] = 0

class PropertyImageCreate(PropertyImageBase):
    pass

class PropertyImageUpdate(BaseModel):
    url: Optional[str] = None
    caption: Optional[str] = None
    alt_text: Optional[str] = None
    is_primary: Optional[bool] = None
    order_index: Optional[int] = None

class PropertyImageResponse(PropertyImageBase):
    image_id: int
    property_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class PropertyImagesResponse(BaseModel):
    property_id: uuid.UUID
    primary_image: Optional[PropertyImageResponse] = None
    images: List[PropertyImageResponse] = []
    total_count: int = 0

class ImageUploadResponse(BaseModel):
    message: str
    image_url: str
    image_id: Optional[int] = None

class ImageBulkUploadRequest(BaseModel):
    images: List[PropertyImageCreate]

class ImageReorderRequest(BaseModel):
    image_orders: List[Dict[str, int]]  # [{"image_id": 1, "order_index": 0}, ...]

# Enhanced Property Schemas with better image support
class PropertyWithImagesResponse(PropertyBase):
    property_id: uuid.UUID
    list_date: datetime
    created_at: datetime
    updated_at: datetime
    property_type: Optional[PropertyTypeResponse] = None
    image_details: Optional[PropertyImagesResponse] = None
    
    class Config:
        from_attributes = True

# Client-Agent Relationship Schemas
class ClientAgentRelationshipBase(BaseModel):
    status: Optional[str] = 'pending'
    requested_by: Optional[str] = None
    property_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None

class ClientAgentRelationshipCreate(ClientAgentRelationshipBase):
    agent_id: uuid.UUID
    requested_by: str = 'client'  # 'client' or 'agent'

class ClientAgentRelationshipUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class ClientAgentRelationshipResponse(ClientAgentRelationshipBase):
    relationship_id: uuid.UUID
    client_id: uuid.UUID
    agent_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    activated_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    client: Optional["UserResponse"] = None
    agent: Optional["UserResponse"] = None
    property: Optional["PropertyResponse"] = None
    
    class Config:
        from_attributes = True

# Notification Schemas
class NotificationBase(BaseModel):
    type: str
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None

class NotificationCreate(NotificationBase):
    user_id: uuid.UUID

class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None

class NotificationResponse(NotificationBase):
    notification_id: uuid.UUID
    user_id: uuid.UUID
    is_read: bool = False
    is_email_sent: bool = False
    email_sent_at: Optional[datetime] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class NotificationsSummary(BaseModel):
    total_count: int
    unread_count: int
    notifications: List[NotificationResponse]

# Property Interest Schemas
class PropertyInterestBase(BaseModel):
    property_id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    interest_level: Optional[str] = 'interested'
    notes: Optional[str] = None

class PropertyInterestCreate(PropertyInterestBase):
    pass

class PropertyInterestUpdate(BaseModel):
    agent_id: Optional[uuid.UUID] = None
    interest_level: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class PropertyInterestResponse(PropertyInterestBase):
    interest_id: uuid.UUID
    user_id: uuid.UUID
    status: str = 'active'
    created_at: datetime
    updated_at: datetime
    property: Optional["PropertyResponse"] = None
    agent: Optional["UserResponse"] = None
    
    class Config:
        from_attributes = True

# Agent Discovery Schemas
class AgentProfile(BaseModel):
    user_id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    email: str
    phone: Optional[str] = None
    role: str
    created_at: datetime
    is_active: bool = True
    
    # Agent-specific stats
    total_listings: int = 0
    active_listings: int = 0
    total_clients: int = 0
    active_clients: int = 0
    
    class Config:
        from_attributes = True

class AgentSearchFilters(BaseModel):
    city: Optional[str] = None
    province: Optional[str] = None
    min_listings: Optional[int] = None
    has_active_listings: Optional[bool] = None
    accepts_new_clients: Optional[bool] = True

# Client Management Schemas
class ClientSummary(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    created_at: datetime
    relationship_status: str
    interested_properties: int = 0
    last_activity: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Request Agent Representation
class AgentRepresentationRequest(BaseModel):
    agent_id: uuid.UUID
    property_id: Optional[uuid.UUID] = None
    message: Optional[str] = None
    interest_level: Optional[str] = 'interested'

class PropertyCreate(PropertyBase):
    pass

class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    location_display: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    price: Optional[Decimal] = None
    price_type: Optional[str] = None
    hoa_fee: Optional[Decimal] = None
    property_type_id: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    square_feet: Optional[int] = None
    lot_size: Optional[int] = None
    year_built: Optional[int] = None
    parking_spots: Optional[int] = None
    has_garage: Optional[bool] = None
    has_basement: Optional[bool] = None
    single_story_only: Optional[bool] = None
    stories: Optional[int] = None
    status: Optional[str] = None
    is_new: Optional[bool] = None
    primary_image: Optional[str] = None
    images: Optional[List[str]] = None

class PropertyResponse(PropertyBase):
    property_id: uuid.UUID
    list_date: datetime
    created_at: datetime
    updated_at: datetime
    property_type: Optional[PropertyTypeResponse] = None
    
    class Config:
        from_attributes = True

# Amenity schemas
class AmenityBase(BaseModel):
    amenity_name: str
    category: Optional[str] = 'basic'
    icon: Optional[str] = None

class AmenityCreate(AmenityBase):
    pass

class AmenityResponse(AmenityBase):
    amenity_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# View schemas
class ViewBase(BaseModel):
    view_type: str
    description: Optional[str] = None

class ViewCreate(ViewBase):
    pass

class ViewResponse(ViewBase):
    view_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Social Media Links Schema
class SocialMediaLinks(BaseModel):
    whatsapp: Optional[str] = None
    facebook: Optional[str] = None
    instagram: Optional[str] = None
    tiktok: Optional[str] = None
    twitter: Optional[str] = None
    youtube: Optional[str] = None
    linkedin: Optional[str] = None

# Enhanced Agent Profile schemas
class AgentProfileBase(BaseModel):
    aka: Optional[str] = None
    specialization: Optional[str] = None
    experience: Optional[int] = None
    agency_name: Optional[str] = None
    license_number: Optional[str] = None
    rating: Optional[Decimal] = Field(None, ge=0, le=5)
    total_sales: Optional[int] = Field(None, ge=0)
    active_listings: Optional[int] = Field(None, ge=0)
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    social_media: Optional[SocialMediaLinks] = None
    city: Optional[str] = None
    province: Optional[str] = None
    service_areas: Optional[List[str]] = []
    is_accepting_clients: Optional[bool] = True
    preferred_contact_method: Optional[str] = None

class AgentProfileCreate(AgentProfileBase):
    pass

class AgentProfileUpdate(BaseModel):
    aka: Optional[str] = None
    specialization: Optional[str] = None
    experience: Optional[int] = None
    agency_name: Optional[str] = None
    license_number: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    social_media: Optional[SocialMediaLinks] = None
    city: Optional[str] = None
    province: Optional[str] = None
    service_areas: Optional[List[str]] = None
    is_accepting_clients: Optional[bool] = None
    preferred_contact_method: Optional[str] = None

class EnhancedAgentResponse(BaseModel):
    # User information (retrieved via user_id relationship)
    user_id: uuid.UUID
    user: Optional["UserResponse"] = None  # Full user data loaded via relationship
    
    # Agent profile information only
    profile_id: Optional[uuid.UUID] = None
    aka: Optional[str] = None
    specialization: Optional[str] = None
    experience: Optional[int] = None
    agency_name: Optional[str] = None
    license_number: Optional[str] = None
    rating: Optional[Decimal] = Field(None, ge=0, le=5)
    total_sales: Optional[int] = Field(None, ge=0)
    active_listings: Optional[int] = Field(None, ge=0)
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    social_media: Optional[SocialMediaLinks] = None
    city: Optional[str] = None
    province: Optional[str] = None
    service_areas: Optional[List[str]] = []
    is_accepting_clients: Optional[bool] = True
    preferred_contact_method: Optional[str] = None
    profile_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# For backward compatibility, create a computed property version
class EnhancedAgentResponseWithUserData(BaseModel):
    # Combined view that includes user data for easy frontend consumption
    user_id: uuid.UUID
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    
    # Agent profile information
    profile_id: Optional[uuid.UUID] = None
    aka: Optional[str] = None
    specialization: Optional[str] = None
    experience: Optional[int] = None
    agency_name: Optional[str] = None
    license_number: Optional[str] = None
    rating: Optional[Decimal] = Field(None, ge=0, le=5)
    total_sales: Optional[int] = Field(None, ge=0)
    active_listings: Optional[int] = Field(None, ge=0)
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    social_media: Optional[SocialMediaLinks] = None
    city: Optional[str] = None
    province: Optional[str] = None
    service_areas: Optional[List[str]] = []
    is_accepting_clients: Optional[bool] = True
    preferred_contact_method: Optional[str] = None
    profile_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# Legacy Agent schemas (keeping for backward compatibility)
class AgentBase(BaseModel):
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    agency_name: Optional[str] = None
    profile_image: Optional[str] = None

class AgentCreate(AgentBase):
    pass

class AgentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    agency_name: Optional[str] = None
    profile_image: Optional[str] = None

class AgentResponse(AgentBase):
    agent_id: int
    full_name: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Search schemas
class PropertySearchFilters(BaseModel):
    city: Optional[str] = None
    province: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    min_bedrooms: Optional[int] = None
    max_bedrooms: Optional[int] = None
    min_bathrooms: Optional[Decimal] = None
    max_bathrooms: Optional[Decimal] = None
    min_square_feet: Optional[int] = None
    max_square_feet: Optional[int] = None
    property_type_id: Optional[int] = None
    has_garage: Optional[bool] = None
    has_basement: Optional[bool] = None
    status: Optional[str] = None
    is_new: Optional[bool] = None
    skip: Optional[int] = Field(0, ge=0)
    limit: Optional[int] = Field(10, ge=1, le=100)

# Saved Search schemas
class SavedSearchBase(BaseModel):
    search_name: str
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    price_type: Optional[str] = 'List Price'
    city: Optional[str] = None
    province: Optional[str] = None
    bedrooms_min: Optional[int] = 0
    bathrooms_min: Optional[Decimal] = 0
    use_exact_match: Optional[bool] = False
    max_hoa: Optional[Decimal] = None
    parking_spots_min: Optional[int] = 0
    must_have_garage: Optional[bool] = False
    has_basement: Optional[bool] = False
    single_story_only: Optional[bool] = False
    square_feet_min: Optional[int] = None
    square_feet_max: Optional[int] = None
    lot_size_min: Optional[int] = None
    lot_size_max: Optional[int] = None
    year_built_min: Optional[int] = None
    year_built_max: Optional[int] = None
    community_filter: Optional[str] = 'Include'
    include_new_listings: Optional[bool] = True

class SavedSearchCreate(SavedSearchBase):
    pass

class SavedSearchResponse(SavedSearchBase):
    search_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Listing schemas
class ListingBase(BaseModel):
    property_id: uuid.UUID
    agent_id: Optional[int] = None
    listing_type_id: Optional[int] = None
    status_id: Optional[int] = None
    expiry_date: Optional[datetime] = None
    mls_number: Optional[str] = None

class ListingCreate(ListingBase):
    pass

class ListingResponse(ListingBase):
    listing_id: uuid.UUID
    list_date: datetime
    created_at: datetime
    updated_at: datetime
    property: Optional["PropertyResponse"] = None
    agent: Optional["AgentResponse"] = None
    
    class Config:
        from_attributes = True

# Generic response schemas
class Message(BaseModel):
    message: str

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int


# Transport Time Schema
class TransportTime(BaseModel):
    walking: Optional[int] = None  # in minutes
    biking: Optional[int] = None   # in minutes
    car: Optional[int] = None      # in minutes


# Neighbourhood Schemas
class NeighbourhoodBase(BaseModel):
    property_id: uuid.UUID
    name: str
    type: str  # 'Cafes' | 'Grocery stores' | 'Parks' | 'Restaurants' | 'Walk-in Clinics' | 'Bus Stops' | 'Shopping Malls' | 'Banks' | 'Pharmacies' | 'Gas Stations'
    address: str
    distance: float  # in km
    transport_time: Optional[TransportTime] = None
    lat: float
    lng: float
    icon: Optional[str] = None
    
    @validator('type')
    def validate_neighbourhood_type(cls, v):
        allowed_types = [
            'Cafes', 'Grocery stores', 'Parks', 'Restaurants', 
            'Walk-in Clinics', 'Bus Stops', 'Shopping Malls', 
            'Banks', 'Pharmacies', 'Gas Stations'
        ]
        if v not in allowed_types:
            raise ValueError(f'Type must be one of: {allowed_types}')
        return v


class NeighbourhoodCreate(NeighbourhoodBase):
    pass


class NeighbourhoodUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    address: Optional[str] = None
    distance: Optional[float] = None
    transport_time: Optional[TransportTime] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    icon: Optional[str] = None


class NeighbourhoodResponse(NeighbourhoodBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# School Schemas
class SchoolBase(BaseModel):
    property_id: uuid.UUID
    name: str
    type: str  # 'Elementary' | 'Secondary'
    grades: Optional[str] = None
    distance: float  # in km
    address: str
    school_board: Optional[str] = None
    score: Optional[float] = None
    is_assigned: bool = False
    postal_code: Optional[str] = None
    lat: float
    lng: float
    
    @validator('type')
    def validate_school_type(cls, v):
        allowed_types = ['Elementary', 'Secondary']
        if v not in allowed_types:
            raise ValueError(f'Type must be one of: {allowed_types}')
        return v


class SchoolCreate(SchoolBase):
    pass


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    grades: Optional[str] = None
    distance: Optional[float] = None
    address: Optional[str] = None
    school_board: Optional[str] = None
    score: Optional[float] = None
    is_assigned: Optional[bool] = None
    postal_code: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


class SchoolResponse(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Market Stats Schema
class MarketStats(BaseModel):
    home_value_below_average: Optional[float] = None  # percentage below market average
    time_on_houseful: Optional[str] = None
    school_rating: Optional[str] = None
    city_trend: Optional[str] = None
    median_days_on_market: Optional[int] = None
    median_list_price: Optional[float] = None
    median_cost_per_sqft: Optional[float] = None
    price_change_from_listing: Optional[float] = None  # percentage
    total_properties_for_sale: Optional[int] = None
    location: Optional[str] = None


# Economic Indicators Schema
class EconomicIndicators(BaseModel):
    appreciation_rate: Optional[float] = None  # percentage
    market_stability: Optional[str] = None  # 'High' | 'Medium' | 'Low'
    investment_potential: Optional[str] = None  # 'Excellent' | 'Good' | 'Fair' | 'Poor'
    average_rent: Optional[float] = None
    rent_yield: Optional[float] = None  # percentage
    
    @validator('market_stability')
    def validate_market_stability(cls, v):
        if v is not None:
            allowed_values = ['High', 'Medium', 'Low']
            if v not in allowed_values:
                raise ValueError(f'Market stability must be one of: {allowed_values}')
        return v
    
    @validator('investment_potential')
    def validate_investment_potential(cls, v):
        if v is not None:
            allowed_values = ['Excellent', 'Good', 'Fair', 'Poor']
            if v not in allowed_values:
                raise ValueError(f'Investment potential must be one of: {allowed_values}')
        return v


# Market Insight Schemas
class MarketInsightBase(BaseModel):
    property_id: uuid.UUID
    postal_code: str
    market_stats: Optional[MarketStats] = None
    price_per_sqft: Optional[float] = None
    style: Optional[str] = None
    time_on_platform: Optional[str] = None
    market_value: Optional[float] = None
    economic_indicators: Optional[EconomicIndicators] = None


class MarketInsightCreate(MarketInsightBase):
    pass


class MarketInsightUpdate(BaseModel):
    postal_code: Optional[str] = None
    market_stats: Optional[MarketStats] = None
    price_per_sqft: Optional[float] = None
    style: Optional[str] = None
    time_on_platform: Optional[str] = None
    market_value: Optional[float] = None
    economic_indicators: Optional[EconomicIndicators] = None


class MarketInsightResponse(MarketInsightBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True 