"""
Data Transformation Middleware for CREA API Integration

This module handles the transformation of CREA DDF API data to our local property schema,
including mapping of properties, amenities, images, and related data.
"""

import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from db_models import (
    Property, PropertyType, Amenity, PropertyImage, Neighbourhood, 
    School, MarketInsight, property_amenities, User, AgentProfile, 
    Listing, ListingType, PropertyStatusType
)

class CREADataTransformer:
    """Transform CREA API property data to local database schema"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Initialize mapping dictionaries
        self._init_amenity_mapping()
        self._init_property_type_mapping()
    
    def _safe_numeric(self, value, default=0, as_type=int):
        """Safely convert value to numeric type with default fallback"""
        if value is None or value == '':
            return default
        try:
            return as_type(value)
        except (ValueError, TypeError):
            return default
        
    def _init_amenity_mapping(self):
        """Map CREA appliances/features to local amenities"""
        self.amenity_mapping = {
            # Kitchen appliances
            "Refrigerator": "refrigerator",
            "Stove": "stove",
            "Microwave": "microwave",
            "Hood Fan": "range_hood",
            "Dishwasher": "dishwasher",
            "Washer & Dryer": "washer_dryer",
            "Washer": "washer",
            "Dryer": "dryer",
            
            # HVAC and utilities
            "Air Conditioned": "air_conditioning",
            "Central Air": "central_air",
            "Forced air": "forced_air_heating",
            "Baseboard heaters": "baseboard_heating",
            "Heat Recovery Ventilation (HRV)": "hrv_system",
            
            # Structural features
            "Garage": "garage",
            "Detached Garage": "detached_garage",
            "Attached Garage": "attached_garage",
            "Fireplace": "fireplace",
            "Full Sprinkler System": "sprinkler_system",
            "Partial Sprinkler System": "sprinkler_system",
            
            # Outdoor features
            "Fence": "fenced_yard",
            "Partially fenced": "partial_fence",
            "Swimming Pool": "swimming_pool",
            "Hot Tub": "hot_tub",
            
            # Interior features
            "Window Coverings": "window_coverings",
            "Hardwood Floors": "hardwood_floors",
            "Laminate": "laminate_flooring",
            "Carpet": "carpet",
            "Tile": "tile_flooring",
            
            # Security
            "Security System": "security_system",
            "Alarm System": "alarm_system",
            
            # Basement features
            "Finished Basement": "finished_basement",
            "Unfinished": "unfinished_basement",
            "Crawl space": "crawl_space",
            
            # Parking
            "No Garage": "no_garage",
            "Street": "street_parking",
            
            # Utilities
            "Municipal water": "municipal_water",
            "Well": "well_water",
            "Septic": "septic_system",
            "City Sewer": "city_sewer"
        }
    
    def _init_property_type_mapping(self):
        """Map CREA PropertySubType to local property types"""
        self.property_type_mapping = {
            "Single Family": "Single Family Detached",
            "Single Family Detached": "Single Family Detached", 
            "Single Family Attached": "Townhouse",
            "Townhouse": "Townhouse",
            "Condo": "Condo",
            "Condominium": "Condo",
            "Apartment": "Apartment",
            "Duplex": "Duplex",
            "Triplex": "Triplex",
            "Fourplex": "Fourplex",
            "Multi-Family": "Multi-Family",
            "Manufactured": "Manufactured Home",
            "Mobile Home": "Mobile Home",
            "Vacant Land": "Land",
            "Commercial": "Commercial",
            "Industrial": "Industrial",
            "Office": "Commercial",
            "Retail": "Commercial",
            "Mixed Use": "Mixed Use"
        }
    
    def transform_property(self, crea_property: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[Dict], List[str]]:
        """
        Transform a single CREA property to local property format
        
        Returns:
            - property_data: Main property data dict
            - amenity_names: List of amenity names to link
            - images: List of image data dicts
            - room_data: List of room information
        """
        # Extract basic property information
        property_data = self._extract_basic_property_data(crea_property)
        
        # Extract amenities from various CREA fields
        amenity_names = self._extract_amenities(crea_property)
        
        # Extract and transform images
        images = self._extract_images(crea_property)
        
        # Extract room information
        room_data = self._extract_room_data(crea_property)
        
        return property_data, amenity_names, images, room_data
    
    def _extract_basic_property_data(self, crea_property: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and map basic property fields"""
        
        # Generate a title from address and property type
        address = crea_property.get('UnparsedAddress', '')
        city = crea_property.get('City', '')
        property_subtype = crea_property.get('PropertySubType', '')
        title = f"{property_subtype} in {city}" if property_subtype else f"Property in {city}"
        if address:
            title = f"{address}, {city}"
        
        # Calculate bathrooms total from separate fields
        bathrooms_full = self._safe_numeric(crea_property.get('BathroomsTotalInteger'), 0, float)
        bathrooms_partial = self._safe_numeric(crea_property.get('BathroomsPartial'), 0, float)
        total_bathrooms = bathrooms_full + (bathrooms_partial * 0.5)
        
        # Determine garage and basement features
        parking_features = crea_property.get('ParkingFeatures', []) or []
        has_garage = any('Garage' in str(feature) for feature in parking_features if str(feature) != 'No Garage')
        parking_spots = self._safe_numeric(crea_property.get('ParkingTotal'), 0)
        
        basement_features = crea_property.get('Basement', []) or []
        has_basement = len(basement_features) > 0 and 'None' not in [str(f) for f in basement_features]
        
        # Handle stories safely
        stories = self._safe_numeric(crea_property.get('Stories'), 1)
        single_story_only = stories == 1
        
        # Map property type
        crea_property_type = crea_property.get('PropertySubType', '')
        property_type_name = self.property_type_mapping.get(crea_property_type, 'Other')
        
        # Get property type ID from database
        property_type_id = self._get_or_create_property_type_id(property_type_name)
        
        # Build the main property data
        property_data = {
            'property_id': str(uuid.uuid4()),  # Generate new UUID
            'title': title,
            'description': crea_property.get('PublicRemarks', ''),
            'address': crea_property.get('UnparsedAddress', ''),
            'city': crea_property.get('City', ''),
            'province': crea_property.get('StateOrProvince', ''),
            'postal_code': crea_property.get('PostalCode', ''),
            'location_display': f"{crea_property.get('UnparsedAddress', '')}, {crea_property.get('City', '')}, {crea_property.get('StateOrProvince', '')}",
            'latitude': Decimal(str(crea_property.get('Latitude', 0))) if crea_property.get('Latitude') else None,
            'longitude': Decimal(str(crea_property.get('Longitude', 0))) if crea_property.get('Longitude') else None,
            'price': Decimal(str(crea_property.get('ListPrice', 0))) if crea_property.get('ListPrice') else None,
            'price_type': 'List Price',
            'hoa_fee': Decimal(str(crea_property.get('AssociationFee', 0))) if crea_property.get('AssociationFee') else Decimal('0'),
            'property_type_id': property_type_id,
            'bedrooms': self._safe_numeric(crea_property.get('BedroomsTotal'), 0),
            'bathrooms': Decimal(str(total_bathrooms)),
            'square_feet': self._safe_numeric(crea_property.get('LivingArea') or crea_property.get('AboveGradeFinishedArea')) or None,
            'lot_size': self._safe_numeric(crea_property.get('LotSizeArea')) or None,
            'year_built': self._safe_numeric(crea_property.get('YearBuilt')) or None,
            'parking_spots': parking_spots,
            'has_garage': has_garage,
            'has_basement': has_basement,
            'single_story_only': single_story_only,
            'stories': stories,
            'status': 'available' if crea_property.get('StandardStatus') == 'Active' else 'inactive',
            'is_new': False,  # Could be determined by year_built or list date
        }
        
        return property_data
    
    def _extract_amenities(self, crea_property: Dict[str, Any]) -> List[str]:
        """Extract amenities from various CREA property fields"""
        amenities = []
        
        # Extract from Appliances field
        appliances = crea_property.get('Appliances', [])
        for appliance in appliances:
            if appliance in self.amenity_mapping:
                amenities.append(self.amenity_mapping[appliance])
        
        # Extract from Heating field
        heating = crea_property.get('Heating', [])
        for heat_type in heating:
            if heat_type in self.amenity_mapping:
                amenities.append(self.amenity_mapping[heat_type])
        
        # Extract from Cooling field
        cooling = crea_property.get('Cooling', [])
        for cool_type in cooling:
            if cool_type in self.amenity_mapping:
                amenities.append(self.amenity_mapping[cool_type])
        
        # Extract from ParkingFeatures
        parking_features = crea_property.get('ParkingFeatures', [])
        for feature in parking_features:
            if feature in self.amenity_mapping:
                amenities.append(self.amenity_mapping[feature])
        
        # Extract from SecurityFeatures
        security_features = crea_property.get('SecurityFeatures', [])
        for feature in security_features:
            if feature in self.amenity_mapping:
                amenities.append(self.amenity_mapping[feature])
        
        # Extract from Basement features
        basement_features = crea_property.get('Basement', [])
        for feature in basement_features:
            if feature in self.amenity_mapping:
                amenities.append(self.amenity_mapping[feature])
        
        # Extract from Flooring
        flooring = crea_property.get('Flooring', [])
        for floor_type in flooring:
            if floor_type in self.amenity_mapping:
                amenities.append(self.amenity_mapping[floor_type])
        
        # Extract from Fencing
        fencing = crea_property.get('Fencing', [])
        for fence_type in fencing:
            if fence_type in self.amenity_mapping:
                amenities.append(self.amenity_mapping[fence_type])
        
        # Check for fireplace
        fireplace_yn = crea_property.get('FireplaceYN')
        fireplaces_total = self._safe_numeric(crea_property.get('FireplacesTotal'), 0)
        if fireplace_yn or fireplaces_total > 0:
            amenities.append('fireplace')
        
        # Remove duplicates and return
        return list(set(amenities))
    
    def _extract_images(self, crea_property: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract and transform image data"""
        images = []
        media_list = crea_property.get('Media', [])
        
        for media in media_list:
            if media.get('MediaCategory') == 'Property Photo' and media.get('MediaURL'):
                image_data = {
                    'url': media['MediaURL'],
                    'caption': media.get('LongDescription') or f"Property Photo {media.get('Order', 1)}",
                    'alt_text': f"Property Photo {media.get('Order', 1)}",
                    'order_index': media.get('Order', 1),
                    'is_primary': media.get('PreferredPhotoYN', False)
                }
                images.append(image_data)
        
        # Sort by order index
        images.sort(key=lambda x: x['order_index'])
        
        return images
    
    def _extract_room_data(self, crea_property: Dict[str, Any]) -> List[str]:
        """Extract room information for potential future use"""
        rooms = crea_property.get('Rooms', [])
        room_info = []
        
        for room in rooms:
            room_data = f"{room.get('RoomType', 'Unknown')} ({room.get('RoomDimensions', 'No dimensions')}) - {room.get('RoomLevel', 'Unknown level')}"
            room_info.append(room_data)
        
        return room_info
    
    def _get_or_create_property_type_id(self, property_type_name: str) -> Optional[int]:
        """Get existing property type ID or create new one"""
        try:
            property_type = self.db.query(PropertyType).filter(
                PropertyType.type_name == property_type_name
            ).first()
            
            if property_type:
                return property_type.type_id
            
            # Create new property type if it doesn't exist
            new_property_type = PropertyType(
                type_name=property_type_name,
                description=f"Property type: {property_type_name}"
            )
            self.db.add(new_property_type)
            self.db.flush()  # Get the ID without committing
            return new_property_type.type_id
            
        except Exception as e:
            print(f"Error getting/creating property type: {e}")
            return None
    
    def create_property_with_relationships(self, 
                                         property_data: Dict[str, Any], 
                                         amenity_names: List[str], 
                                         images: List[Dict[str, Any]],
                                         room_data: List[str] = None) -> Property:
        """
        Create property and all its relationships in the database
        """
        try:
            # Create the main property
            property_obj = Property(**property_data)
            self.db.add(property_obj)
            self.db.flush()  # Get the property_id
            
            # Handle primary image
            if images:
                primary_image = next((img for img in images if img.get('is_primary')), images[0])
                property_obj.primary_image = primary_image['url']
                
                # Store image URLs in JSONB field
                image_urls = [img['url'] for img in images]
                property_obj.images = image_urls
            
            # Create property images
            for image_data in images:
                property_image = PropertyImage(
                    property_id=property_obj.property_id,
                    **image_data
                )
                self.db.add(property_image)
            
            # Link amenities
            self._link_amenities(property_obj, amenity_names)
            
            # Create market insight placeholder
            self._create_market_insight_placeholder(property_obj)
            
            self.db.commit()
            return property_obj
            
        except Exception as e:
            self.db.rollback()
            raise Exception(f"Error creating property: {e}")
    
    def _link_amenities(self, property_obj: Property, amenity_names: List[str]):
        """Link amenities to the property"""
        for amenity_name in amenity_names:
            try:
                # Get or create amenity
                amenity = self.db.query(Amenity).filter(
                    Amenity.amenity_name == amenity_name
                ).first()
                
                if not amenity:
                    amenity = Amenity(
                        amenity_name=amenity_name,
                        category='appliance' if amenity_name in ['refrigerator', 'stove', 'microwave', 'dishwasher'] else 'feature'
                    )
                    self.db.add(amenity)
                    self.db.flush()
                
                # Link to property
                property_obj.amenities.append(amenity)
                
            except Exception as e:
                print(f"Error linking amenity {amenity_name}: {e}")
                continue
    
    def _create_market_insight_placeholder(self, property_obj: Property):
        """Create a market insight placeholder for the property"""
        try:
            market_insight = MarketInsight(
                property_id=property_obj.property_id,
                postal_code=property_obj.postal_code or '',
                market_stats={},
                economic_indicators={}
            )
            self.db.add(market_insight)
        except Exception as e:
            print(f"Error creating market insight: {e}")
    
    def transform_and_create_property(self, crea_property: Dict[str, Any]) -> Property:
        """
        Complete pipeline: transform CREA property and create in database
        """
        try:
            # Transform the data
            property_data, amenity_names, images, room_data = self.transform_property(crea_property)
            
            # Create in database
            return self.create_property_with_relationships(
                property_data, amenity_names, images, room_data
            )
        except Exception as e:
            print(f"Error in transform_and_create_property: {e}")
            print(f"Property data: {crea_property.get('ListingId', 'Unknown')}")
            print(f"Key fields: Bedrooms={crea_property.get('BedroomsTotal')}, Bathrooms={crea_property.get('BathroomsTotalInteger')}, Stories={crea_property.get('Stories')}")
            raise

    def bulk_transform_properties(self, crea_properties: List[Dict[str, Any]]) -> List[Property]:
        """
        Transform and create multiple properties in bulk
        """
        created_properties = []
        
        for crea_property in crea_properties:
            try:
                property_obj = self.transform_and_create_property(crea_property)
                created_properties.append(property_obj)
                print(f"✅ Created property: {property_obj.title}")
                
            except Exception as e:
                print(f"❌ Error creating property {crea_property.get('ListingId', 'Unknown')}: {e}")
                continue
        
        return created_properties
    
    # ============================================================================
    # AGENT AND LISTING TRANSFORMATION METHODS
    # ============================================================================
    
    def get_or_create_agent_from_crea(self, crea_property: Dict[str, Any]) -> Optional[User]:
        """
        Extract agent information from CREA property and create/get local agent
        """
        # Extract agent information from CREA property
        list_agent_key = crea_property.get('ListAgentKey')
        
        if not list_agent_key:
            return None
        
        try:
            # Check if agent already exists by external ID or similar identifier
            # For now, we'll use the ListAgentKey as a unique identifier
            
            # Try to get more agent details from CREA API
            agent_info = self._get_agent_info_from_crea(list_agent_key)
            
            if not agent_info:
                # Create a basic agent profile with available information
                agent_info = {
                    'agent_key': list_agent_key,
                    'office_key': crea_property.get('ListOfficeKey'),
                    'office_name': crea_property.get('OriginatingSystemName', ''),
                }
            
            # Check if agent already exists
            existing_agent = self.db.query(User).join(AgentProfile).filter(
                AgentProfile.license_number == list_agent_key
            ).first()
            
            if existing_agent:
                return existing_agent
            
            # Create new agent
            return self._create_agent_from_info(agent_info)
            
        except Exception as e:
            print(f"Error creating agent for key {list_agent_key}: {e}")
            return None
    
    def _get_agent_info_from_crea(self, agent_key: str) -> Optional[Dict]:
        """
        Try to get detailed agent information from CREA API
        """
        try:
            # Import here to avoid circular imports
            from crea_api_client import crea_api
            
            # Get member information (agents are members)
            result = crea_api.get_members(member_id=agent_key)
            
            if result and result.get('value'):
                agent_data = result['value'][0] if isinstance(result['value'], list) else result['value']
                return {
                    'agent_key': agent_key,
                    'first_name': agent_data.get('FirstName', ''),
                    'last_name': agent_data.get('LastName', ''),
                    'email': agent_data.get('Email', ''),
                    'phone': agent_data.get('Phone', ''),
                    'office_name': agent_data.get('OfficeName', ''),
                    'license_number': agent_data.get('LicenseNumber', agent_key),
                }
        except Exception as e:
            print(f"Could not fetch agent details for {agent_key}: {e}")
            
        return None
    
    def _create_agent_from_info(self, agent_info: Dict[str, Any]) -> User:
        """
        Create a new agent user and profile from agent information
        """
        try:
            # Generate email if not provided
            email = agent_info.get('email')
            if not email:
                # Create a placeholder email
                agent_key = agent_info.get('agent_key', 'unknown')
                email = f"agent_{agent_key}@crea.imported"
            
            # Create User
            agent_user = User(
                email=email,
                password_hash='$2b$12$placeholder_hash_for_imported_agents',  # Placeholder - they'll need to reset
                first_name=agent_info.get('first_name', 'CREA'),
                last_name=agent_info.get('last_name', 'Agent'),
                phone=agent_info.get('phone', ''),
                role='agent',
                is_active=True,
                preferences={}
            )
            
            self.db.add(agent_user)
            self.db.flush()  # Get the user_id
            
            # Create AgentProfile
            agent_profile = AgentProfile(
                user_id=agent_user.user_id,
                agency_name=agent_info.get('office_name', 'CREA Import'),
                license_number=agent_info.get('license_number', agent_info.get('agent_key')),
                bio=f"Agent imported from CREA system. License: {agent_info.get('license_number', 'N/A')}",
                is_accepting_clients=True,
                preferred_contact_method='email',
                experience=0,  # Unknown from CREA data
                total_sales=0,
                active_listings=0,
                rating=Decimal('0.0')
            )
            
            self.db.add(agent_profile)
            self.db.commit()
            
            print(f"✅ Created agent: {agent_user.full_name} ({email})")
            return agent_user
            
        except Exception as e:
            self.db.rollback()
            print(f"❌ Error creating agent: {e}")
            raise
    
    def create_listing_for_property(self, property_obj: Property, agent: Optional[User], crea_property: Dict[str, Any]) -> Optional[Listing]:
        """
        Create a listing record linking the property to the agent
        """
        if not agent:
            return None
            
        try:
            # Get or create listing type
            listing_type = self._get_or_create_listing_type("For Sale")
            
            # Get or create status type
            status_type = self._get_or_create_status_type("Active")
            
            # Create listing
            listing = Listing(
                property_id=property_obj.property_id,
                agent_id=agent.user_id,
                listing_type_id=listing_type.listing_type_id,
                status_id=status_type.status_id,
                mls_number=crea_property.get('ListingId'),
                list_date=datetime.now(),
                expiry_date=None  # Could be calculated from CREA data if available
            )
            
            self.db.add(listing)
            self.db.commit()
            
            # Update agent's active listings count
            if agent.agent_profile:
                agent.agent_profile.active_listings += 1
                self.db.commit()
            
            print(f"✅ Created listing: {crea_property.get('ListingId')} for agent {agent.full_name}")
            return listing
            
        except Exception as e:
            print(f"❌ Error creating listing: {e}")
            return None
    
    def _get_or_create_listing_type(self, type_name: str) -> ListingType:
        """Get or create a listing type"""
        listing_type = self.db.query(ListingType).filter(
            ListingType.type_name == type_name
        ).first()
        
        if not listing_type:
            listing_type = ListingType(
                type_name=type_name,
                description=f"Listing type: {type_name}"
            )
            self.db.add(listing_type)
            self.db.flush()
        
        return listing_type
    
    def _get_or_create_status_type(self, status_name: str) -> PropertyStatusType:
        """Get or create a property status type"""
        status_type = self.db.query(PropertyStatusType).filter(
            PropertyStatusType.status_name == status_name
        ).first()
        
        if not status_type:
            status_type = PropertyStatusType(
                status_name=status_name,
                description=f"Property status: {status_name}"
            )
            self.db.add(status_type)
            self.db.flush()
        
        return status_type
    
    def transform_and_create_property_with_agent(self, crea_property: Dict[str, Any]) -> Tuple[Property, Optional[User], Optional[Listing]]:
        """
        Complete pipeline: transform CREA property, create agent, and establish relationships
        """
        try:
            # Transform the property data
            property_data, amenity_names, images, room_data = self.transform_property(crea_property)
            
            # Get or create agent
            agent = self.get_or_create_agent_from_crea(crea_property)
            
            # Create property with relationships
            property_obj = self.create_property_with_relationships(
                property_data, amenity_names, images, room_data
            )
            
            # Create listing linking property to agent
            listing = self.create_listing_for_property(property_obj, agent, crea_property)
            
            return property_obj, agent, listing
            
        except Exception as e:
            print(f"Error in transform_and_create_property_with_agent: {e}")
            raise
    
    # ============================================================================
    # DAILY SYNC AND STATUS TRACKING METHODS
    # ============================================================================
    
    def sync_province_market_data(self, province: str, days_back: int = 1) -> Dict:
        """
        Daily synchronization of province market data with status tracking
        """
        from crea_api_client import crea_api
        
        print(f"🔄 Starting daily sync for {province}...")
        
        # Get comprehensive market data from CREA using efficient pagination
        print(f"🔍 Fetching province data for {province} using optimized approach...")
        
        # Get ALL active listings for the province (most important for daily sync)
        active_result = crea_api.search_properties_paginated(
            province=province,
            status_filter='Active'
        )
        
        # Get smaller samples of pending/sold for efficiency (daily sync focuses on active)
        pending_result = crea_api.search_properties_paginated(
            province=province,
            status_filter='Under Contract',
            max_results=500  # Limit for efficiency
        )
        
        sold_result = crea_api.search_properties_paginated(
            province=province,
            status_filter='Sold',
            max_results=500  # Recent sales sample
        )
        
        # Combine into market_data format
        market_data = {
            'province': province,
            'active_listings': active_result.get('value', []),
            'pending_listings': pending_result.get('value', []),
            'sold_listings': sold_result.get('value', []),
            'new_listings': []  # Will be filtered from active listings
        }
        
        print(f"📊 Retrieved {len(market_data['active_listings'])} active, {len(market_data['pending_listings'])} pending, {len(market_data['sold_listings'])} sold properties")
        
        sync_stats = {
            'province': province,
            'new_properties': 0,
            'updated_properties': 0,
            'status_changes': 0,
            'new_agents': 0,
            'agent_performance_updates': 0,
            'active_count': len(market_data['active_listings']),
            'pending_count': len(market_data['pending_listings']),
            'sold_count': len(market_data['sold_listings']),
            'new_listings_count': len(market_data['new_listings'])
        }
        
        try:
            # Process active listings
            for listing in market_data['active_listings']:
                result = self._process_listing_update(listing, 'Active')
                if result['created']:
                    sync_stats['new_properties'] += 1
                elif result['updated']:
                    sync_stats['updated_properties'] += 1
                if result['status_changed']:
                    sync_stats['status_changes'] += 1
                if result['new_agent']:
                    sync_stats['new_agents'] += 1
            
            # Process pending listings
            for listing in market_data['pending_listings']:
                result = self._process_listing_update(listing, 'Pending')
                if result['status_changed']:
                    sync_stats['status_changes'] += 1
                if result['updated']:
                    sync_stats['updated_properties'] += 1
            
            # Process sold listings
            for listing in market_data['sold_listings']:
                result = self._process_listing_update(listing, 'Sold')
                if result['status_changed']:
                    sync_stats['status_changes'] += 1
                    # Update agent sales count
                    self._update_agent_sales_performance(listing)
                    sync_stats['agent_performance_updates'] += 1
                if result['updated']:
                    sync_stats['updated_properties'] += 1
            
            print(f"✅ {province} sync complete: {sync_stats}")
            
        except Exception as e:
            print(f"❌ Error syncing {province}: {e}")
            sync_stats['error'] = str(e)
        
        return sync_stats
    
    def _process_listing_update(self, crea_listing: Dict, target_status: str) -> Dict:
        """
        Process individual listing update with status tracking
        """
        result = {
            'created': False,
            'updated': False,
            'status_changed': False,
            'new_agent': False
        }
        
        try:
            listing_id = crea_listing.get('ListingId')
            if not listing_id:
                return result
            
            # Check if property exists by MLS number
            existing_listing = self.db.query(Listing).filter(
                Listing.mls_number == listing_id
            ).first()
            
            if existing_listing:
                # Update existing property
                result['updated'] = True
                
                # Check for status change
                current_status = existing_listing.status_type.status_name if existing_listing.status_type else 'Unknown'
                if current_status != target_status:
                    # Update status
                    new_status = self._get_or_create_status_type(target_status)
                    existing_listing.status_id = new_status.status_id
                    existing_listing.updated_at = datetime.now()
                    
                    # Update property status too
                    if existing_listing.property:
                        status_map = {
                            'Active': 'available',
                            'Pending': 'pending',
                            'Sold': 'sold',
                            'Under Contract': 'pending'
                        }
                        existing_listing.property.status = status_map.get(target_status, 'available')
                        existing_listing.property.updated_at = datetime.now()
                    
                    result['status_changed'] = True
                    print(f"📊 Status change: {listing_id} {current_status} → {target_status}")
                
                # Update price if changed
                new_price = self._safe_numeric(crea_listing.get('ListPrice'), 0, float)
                if existing_listing.property and new_price > 0:
                    current_price = float(existing_listing.property.price or 0)
                    if abs(current_price - new_price) > 100:  # Significant price change
                        existing_listing.property.price = Decimal(str(new_price))
                        existing_listing.property.updated_at = datetime.now()
                        print(f"💰 Price update: {listing_id} ${current_price:,.0f} → ${new_price:,.0f}")
                
                self.db.commit()
                
            else:
                # Create new property with agent relationships
                try:
                    property_obj, agent, listing = self.transform_and_create_property_with_agent(crea_listing)
                    
                    # Set the correct status
                    if listing:
                        status_type = self._get_or_create_status_type(target_status)
                        listing.status_id = status_type.status_id
                        
                        # Update property status
                        status_map = {
                            'Active': 'available',
                            'Pending': 'pending', 
                            'Sold': 'sold',
                            'Under Contract': 'pending'
                        }
                        property_obj.status = status_map.get(target_status, 'available')
                        self.db.commit()
                    
                    result['created'] = True
                    if agent:
                        result['new_agent'] = True
                    
                    print(f"🆕 New {target_status} property: {listing_id}")
                    
                except Exception as e:
                    print(f"❌ Error creating property {listing_id}: {e}")
        
        except Exception as e:
            print(f"❌ Error processing listing {crea_listing.get('ListingId', 'Unknown')}: {e}")
        
        return result
    
    def _update_agent_sales_performance(self, sold_listing: Dict):
        """
        Update agent performance metrics when a property is sold
        """
        try:
            agent_key = sold_listing.get('ListAgentKey')
            if not agent_key:
                return
            
            # Find agent by license number (using ListAgentKey)
            agent = self.db.query(User).join(AgentProfile).filter(
                AgentProfile.license_number == agent_key
            ).first()
            
            if agent and agent.agent_profile:
                # Increment total sales
                agent.agent_profile.total_sales += 1
                
                # Decrease active listings count
                if agent.agent_profile.active_listings > 0:
                    agent.agent_profile.active_listings -= 1
                
                # Update performance timestamp
                agent.agent_profile.updated_at = datetime.now()
                
                self.db.commit()
                print(f"📈 Updated sales performance for agent {agent.full_name}: {agent.agent_profile.total_sales} total sales")
                
        except Exception as e:
            print(f"❌ Error updating agent performance: {e}")
    
    def get_province_summary(self, province: str) -> Dict:
        """
        Get comprehensive summary of properties and agents by province
        """
        try:
            # Get property counts by status
            property_counts = self.db.query(Property.status, func.count(Property.property_id)).filter(
                Property.province == province
            ).group_by(Property.status).all()
            
            status_summary = {status: count for status, count in property_counts}
            
            # Get agent information for this province
            agents_in_province = self.db.query(User).join(AgentProfile).filter(
                User.role == 'agent',
                AgentProfile.city.like(f'%{province}%')  # Rough province matching
            ).all()
            
            agent_summary = []
            for agent in agents_in_province:
                profile = agent.agent_profile
                agent_info = {
                    'agent_id': str(agent.user_id),
                    'name': agent.full_name,
                    'email': agent.email,
                    'agency': profile.agency_name if profile else None,
                    'active_listings': profile.active_listings if profile else 0,
                    'total_sales': profile.total_sales if profile else 0,
                    'rating': float(profile.rating) if profile and profile.rating else 0.0
                }
                agent_summary.append(agent_info)
            
            # Sort agents by performance
            agent_summary.sort(key=lambda x: (x['total_sales'], x['active_listings']), reverse=True)
            
            return {
                'province': province,
                'property_status_summary': status_summary,
                'total_properties': sum(status_summary.values()),
                'agent_count': len(agent_summary),
                'top_agents': agent_summary[:10],  # Top 10 performing agents
                'total_active_listings': sum([a['active_listings'] for a in agent_summary]),
                'total_sales': sum([a['total_sales'] for a in agent_summary])
            }
            
        except Exception as e:
            print(f"❌ Error getting province summary for {province}: {e}")
            return {'error': str(e)}