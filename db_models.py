from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, DECIMAL, ForeignKey, Table, TIMESTAMP, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
import uuid
from datetime import datetime
from database import Base

# Association tables for many-to-many relationships
property_amenities = Table(
    'property_amenities',
    Base.metadata,
    Column('property_id', UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), primary_key=True),
    Column('amenity_id', Integer, ForeignKey('amenities.amenity_id', ondelete='CASCADE'), primary_key=True)
)

property_views = Table(
    'property_views',
    Base.metadata,
    Column('property_id', UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), primary_key=True),
    Column('view_id', Integer, ForeignKey('views.view_id', ondelete='CASCADE'), primary_key=True)
)

property_tours = Table(
    'property_tours',
    Base.metadata,
    Column('property_id', UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), primary_key=True),
    Column('tour_id', Integer, ForeignKey('tour_options.tour_id', ondelete='CASCADE'), primary_key=True),
    Column('tour_date', TIMESTAMP)
)

saved_properties = Table(
    'saved_properties',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
    Column('property_id', UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', TIMESTAMP, default=func.now())
)

# User model with roles
class User(Base):
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone = Column(String(20))
    role = Column(String(20), default='customer')  # customer, client, agent, admin
    is_active = Column(Boolean, default=True)
    preferences = Column(JSONB)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    saved_properties = relationship("Property", secondary=saved_properties, back_populates="saved_by_users")
    saved_searches = relationship("SavedSearch", back_populates="user", cascade="all, delete-orphan")
    property_views = relationship("PropertyViewHistory", back_populates="user", cascade="all, delete-orphan")
    agent_relationships_as_client = relationship("ClientAgentRelationship", foreign_keys="ClientAgentRelationship.client_id", back_populates="client", cascade="all, delete-orphan")
    client_relationships_as_agent = relationship("ClientAgentRelationship", foreign_keys="ClientAgentRelationship.agent_id", back_populates="agent", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    property_interests = relationship("PropertyInterest", foreign_keys="PropertyInterest.user_id", back_populates="user", cascade="all, delete-orphan")
    agent_profile = relationship("AgentProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    @hybrid_property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

# Property Types
class PropertyType(Base):
    __tablename__ = "property_types"
    
    type_id = Column(Integer, primary_key=True)
    type_name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    properties = relationship("Property", back_populates="property_type")

# Properties (Main table)
class Property(Base):
    __tablename__ = "properties"
    
    property_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic Info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Location fields
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    province = Column(String(50), nullable=False)
    postal_code = Column(String(20))
    location_display = Column(String(255))
    latitude = Column(DECIMAL(10, 8), index=True)
    longitude = Column(DECIMAL(11, 8), index=True)
    
    # Pricing
    price = Column(DECIMAL(12, 2), index=True)
    price_type = Column(String(20), default='List Price')
    hoa_fee = Column(DECIMAL(8, 2), default=0)
    
    # Property Details
    property_type_id = Column(Integer, ForeignKey('property_types.type_id'))
    bedrooms = Column(Integer, default=0, index=True)
    bathrooms = Column(DECIMAL(3, 1), default=0, index=True)
    square_feet = Column(Integer)
    lot_size = Column(Integer)
    year_built = Column(Integer)
    
    # Features
    parking_spots = Column(Integer, default=0)
    has_garage = Column(Boolean, default=False)
    has_basement = Column(Boolean, default=False)
    single_story_only = Column(Boolean, default=False)
    stories = Column(Integer, default=1)
    
    # Status and Marketing
    status = Column(String(20), default='available', index=True)
    is_new = Column(Boolean, default=False, index=True)
    
    # Media
    primary_image = Column(String(500))
    images = Column(JSONB)
    
    # Timestamps
    list_date = Column(TIMESTAMP, default=func.now())
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    property_type = relationship("PropertyType", back_populates="properties")
    amenities = relationship("Amenity", secondary=property_amenities, back_populates="properties")
    views = relationship("View", secondary=property_views, back_populates="properties")
    tours = relationship("TourOption", secondary=property_tours, back_populates="properties")
    saved_by_users = relationship("User", secondary=saved_properties, back_populates="saved_properties")
    listings = relationship("Listing", back_populates="property", cascade="all, delete-orphan")
    property_views_history = relationship("PropertyViewHistory", back_populates="property", cascade="all, delete-orphan")
    property_images = relationship("PropertyImage", back_populates="property", cascade="all, delete-orphan")
    neighbourhoods = relationship("Neighbourhood", back_populates="property", cascade="all, delete-orphan")
    schools = relationship("School", back_populates="property", cascade="all, delete-orphan")
    market_insight = relationship("MarketInsight", back_populates="property", uselist=False, cascade="all, delete-orphan")

# Property Images (Enhanced image management)
class PropertyImage(Base):
    __tablename__ = "property_images"
    
    image_id = Column(Integer, primary_key=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), nullable=False)
    url = Column(String(500), nullable=False)
    caption = Column(Text)
    alt_text = Column(String(255))
    is_primary = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)
    file_size = Column(Integer)  # In bytes
    width = Column(Integer)
    height = Column(Integer)
    format = Column(String(10))  # jpg, png, webp, etc.
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_property_images_property_id', 'property_id'),
        Index('idx_property_images_is_primary', 'property_id', 'is_primary'),
        Index('idx_property_images_order', 'property_id', 'order_index'),
    )
    
    # Relationships
    property = relationship("Property", back_populates="property_images")

# Client-Agent Relationships
class ClientAgentRelationship(Base):
    __tablename__ = "client_agent_relationships"
    
    relationship_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    status = Column(String(20), default='pending')  # pending, active, inactive, terminated
    requested_by = Column(String(20))  # 'client' or 'agent'
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='SET NULL'), nullable=True)  # Property that triggered the relationship
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    activated_at = Column(TIMESTAMP, nullable=True)
    terminated_at = Column(TIMESTAMP, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_client_agent_client_id', 'client_id'),
        Index('idx_client_agent_agent_id', 'agent_id'),
        Index('idx_client_agent_status', 'status'),
        Index('idx_client_agent_active', 'client_id', 'agent_id', 'status'),
    )
    
    # Relationships
    client = relationship("User", foreign_keys=[client_id], back_populates="agent_relationships_as_client")
    agent = relationship("User", foreign_keys=[agent_id], back_populates="client_relationships_as_agent")
    property = relationship("Property")

# Notifications
class Notification(Base):
    __tablename__ = "notifications"
    
    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    type = Column(String(50), nullable=False)  # 'client_request', 'agent_assignment', 'property_interest', etc.
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSONB)  # Additional structured data
    is_read = Column(Boolean, default=False)
    is_email_sent = Column(Boolean, default=False)
    email_sent_at = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, default=func.now())
    read_at = Column(TIMESTAMP, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_notifications_user_id', 'user_id'),
        Index('idx_notifications_unread', 'user_id', 'is_read'),
        Index('idx_notifications_type', 'type'),
        Index('idx_notifications_created', 'created_at'),
    )
    
    # Relationships
    user = relationship("User", back_populates="notifications")

# Property Interest Tracking
class PropertyInterest(Base):
    __tablename__ = "property_interests"
    
    interest_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='SET NULL'), nullable=True)
    interest_level = Column(String(20), default='interested')  # interested, very_interested, ready_to_buy
    status = Column(String(20), default='active')  # active, contacted, closed
    notes = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_property_interests_user', 'user_id'),
        Index('idx_property_interests_property', 'property_id'),
        Index('idx_property_interests_agent', 'agent_id'),
        Index('idx_property_interests_status', 'status'),
    )
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    property = relationship("Property")
    agent = relationship("User", foreign_keys=[agent_id])

# Amenities
class Amenity(Base):
    __tablename__ = "amenities"
    
    amenity_id = Column(Integer, primary_key=True)
    amenity_name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), default='basic')
    icon = Column(String(100))
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    properties = relationship("Property", secondary=property_amenities, back_populates="amenities")

# Views
class View(Base):
    __tablename__ = "views"
    
    view_id = Column(Integer, primary_key=True)
    view_type = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    properties = relationship("Property", secondary=property_views, back_populates="views")

# Enhanced Agent Profiles (extends User table)
class AgentProfile(Base):
    __tablename__ = "agent_profiles"
    
    profile_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), unique=True, nullable=False)
    
    # Professional Information
    aka = Column(String(255))  # Professional nickname/tagline
    specialization = Column(String(255))  # e.g., "Luxury Homes", "Commercial Real Estate"
    experience = Column(Integer)  # Years of experience
    agency_name = Column(String(255))
    license_number = Column(String(100))
    
    # Performance Metrics
    rating = Column(DECIMAL(3, 2), default=0.0)  # Average rating (0.0 to 5.0)
    total_sales = Column(Integer, default=0)
    active_listings = Column(Integer, default=0)
    
    # Profile Content
    bio = Column(Text)
    profile_image = Column(String(500))
    
    # Social Media Links
    social_media = Column(JSONB, default={})  # Store as JSON: {"whatsapp": "+1234567890", "facebook": "username", etc.}
    
    # Location & Service Areas
    city = Column(String(100))
    province = Column(String(100))
    service_areas = Column(JSONB, default=[])  # Array of cities/areas served
    
    # Availability & Preferences
    is_accepting_clients = Column(Boolean, default=True)
    preferred_contact_method = Column(String(50))  # "email", "phone", "whatsapp", etc.
    
    # Timestamps
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Indexes for search optimization
    __table_args__ = (
        Index('idx_agent_profile_user_id', 'user_id'),
        Index('idx_agent_profile_city', 'city'),
        Index('idx_agent_profile_specialization', 'specialization'),
        Index('idx_agent_profile_accepting_clients', 'is_accepting_clients'),
        Index('idx_agent_profile_rating', 'rating'),
    )
    
    # Relationships
    user = relationship("User", back_populates="agent_profile")

# Legacy Agent table removed - now using User + AgentProfile system

# Listing Types
class ListingType(Base):
    __tablename__ = "listing_types"
    
    listing_type_id = Column(Integer, primary_key=True)
    type_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    listings = relationship("Listing", back_populates="listing_type")

# Property Status Types
class PropertyStatusType(Base):
    __tablename__ = "property_status_types"
    
    status_id = Column(Integer, primary_key=True)
    status_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    listings = relationship("Listing", back_populates="status_type")

# Tour Options
class TourOption(Base):
    __tablename__ = "tour_options"
    
    tour_id = Column(Integer, primary_key=True)
    tour_type = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    created_at = Column(TIMESTAMP, default=func.now())
    
    # Relationships
    properties = relationship("Property", secondary=property_tours, back_populates="tours")

# Listings
class Listing(Base):
    __tablename__ = "listings"
    
    listing_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'))
    agent_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id'))
    listing_type_id = Column(Integer, ForeignKey('listing_types.listing_type_id'))
    status_id = Column(Integer, ForeignKey('property_status_types.status_id'))
    list_date = Column(DateTime, default=func.current_date())
    expiry_date = Column(DateTime)
    mls_number = Column(String(100))
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    property = relationship("Property", back_populates="listings")
    agent = relationship("User", foreign_keys=[agent_id])  # Reference User instead of legacy Agent
    listing_type = relationship("ListingType", back_populates="listings")
    status_type = relationship("PropertyStatusType", back_populates="listings")

# Saved Searches
class SavedSearch(Base):
    __tablename__ = "saved_searches"
    
    search_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'))
    search_name = Column(String(255), nullable=False)
    
    # Basic filters
    budget_min = Column(DECIMAL(12, 2))
    budget_max = Column(DECIMAL(12, 2))
    price_type = Column(String(20), default='List Price')
    city = Column(String(100))
    province = Column(String(50))
    
    # Property specifications
    bedrooms_min = Column(Integer, default=0)
    bathrooms_min = Column(DECIMAL(3, 1), default=0)
    use_exact_match = Column(Boolean, default=False)
    
    # Financial filters
    max_hoa = Column(DECIMAL(8, 2))
    
    # Features
    parking_spots_min = Column(Integer, default=0)
    must_have_garage = Column(Boolean, default=False)
    has_basement = Column(Boolean, default=False)
    single_story_only = Column(Boolean, default=False)
    
    # Size filters
    square_feet_min = Column(Integer)
    square_feet_max = Column(Integer)
    lot_size_min = Column(Integer)
    lot_size_max = Column(Integer)
    
    # Age filters
    year_built_min = Column(Integer)
    year_built_max = Column(Integer)
    
    # Community filters
    community_filter = Column(String(20), default='Include')
    
    # Status filters
    include_new_listings = Column(Boolean, default=True)
    
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="saved_searches")
    search_filters = relationship("SearchFilter", back_populates="saved_search", cascade="all, delete-orphan")

# Search Filters
class SearchFilter(Base):
    __tablename__ = "search_filters"
    
    search_id = Column(UUID(as_uuid=True), ForeignKey('saved_searches.search_id', ondelete='CASCADE'), primary_key=True)
    filter_type = Column(String(50), nullable=False, primary_key=True)
    filter_values = Column(JSONB, nullable=False)
    
    # Relationships
    saved_search = relationship("SavedSearch", back_populates="search_filters")

# Property Views History
class PropertyViewHistory(Base):
    __tablename__ = "property_views_history"
    
    view_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id', ondelete='CASCADE'), index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), index=True)
    ip_address = Column(INET)
    user_agent = Column(Text)
    viewed_at = Column(TIMESTAMP, default=func.now(), index=True)
    
    # Relationships
    property = relationship("Property", back_populates="property_views_history")
    user = relationship("User", back_populates="property_views")


# Neighbourhood Model
class Neighbourhood(Base):
    __tablename__ = "neighbourhoods"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id'), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # 'Cafes', 'Grocery stores', 'Parks', etc.
    address = Column(String(500), nullable=False)
    distance = Column(DECIMAL(5, 2), nullable=False)  # in km
    walking_time = Column(Integer)  # in minutes
    biking_time = Column(Integer)  # in minutes
    car_time = Column(Integer)  # in minutes
    lat = Column(DECIMAL(10, 8), nullable=False)
    lng = Column(DECIMAL(11, 8), nullable=False)
    icon = Column(String(255))
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_neighbourhood_property_id', 'property_id'),
        Index('idx_neighbourhood_type', 'type'),
        Index('idx_neighbourhood_distance', 'distance'),
    )
    
    # Relationships
    property = relationship("Property", back_populates="neighbourhoods")


# School Model
class School(Base):
    __tablename__ = "schools"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id'), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)  # 'Elementary', 'Secondary'
    grades = Column(String(50))
    distance = Column(DECIMAL(5, 2), nullable=False)  # in km
    address = Column(String(500), nullable=False)
    school_board = Column(String(255))
    score = Column(DECIMAL(3, 1))  # e.g., 8.5 out of 10
    is_assigned = Column(Boolean, default=False)
    postal_code = Column(String(10))
    lat = Column(DECIMAL(10, 8), nullable=False)
    lng = Column(DECIMAL(11, 8), nullable=False)
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_school_property_id', 'property_id'),
        Index('idx_school_type', 'type'),
        Index('idx_school_distance', 'distance'),
        Index('idx_school_score', 'score'),
    )
    
    # Relationships
    property = relationship("Property", back_populates="schools")


# Market Insight Model
class MarketInsight(Base):
    __tablename__ = "market_insights"
    
    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.property_id'), nullable=False, unique=True)
    postal_code = Column(String(10), nullable=False)
    
    # Market Stats (stored as JSONB for flexibility)
    market_stats = Column(JSONB, default={})
    
    # Direct fields
    price_per_sqft = Column(DECIMAL(10, 2))
    style = Column(String(100))
    time_on_platform = Column(String(50))
    market_value = Column(DECIMAL(15, 2))
    
    # Economic Indicators (stored as JSONB)
    economic_indicators = Column(JSONB, default={})
    
    created_at = Column(TIMESTAMP, default=func.now())
    updated_at = Column(TIMESTAMP, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_market_insight_property_id', 'property_id'),
        Index('idx_market_insight_postal_code', 'postal_code'),
    )
    
    # Relationships
    property = relationship("Property", back_populates="market_insight") 