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
    Listing, ListingType, PropertyStatusType, Room, Office, Lead
)

class CREADataTransformer:
    """Transform CREA API property data to local database schema"""
    
    def __init__(self, db: Session):
        self.db = db
        
        # Initialize mapping dictionaries
        self._init_amenity_mapping()
        self._init_property_type_mapping()
    
    @staticmethod
    def safely_truncate_field(value, max_length, field_name="field"):
        """Safely truncate a field while preserving important information"""
        if not value:
            return value
        
        if isinstance(value, list):
            # For lists like designations, join and truncate intelligently
            value = ', '.join(value) if value else ''
        
        value = str(value).strip()
        
        if len(value) <= max_length:
            return value
        
        # Truncate but try to preserve complete words
        truncated = value[:max_length-3]
        if ' ' in truncated:
            # Find last complete word
            last_space = truncated.rfind(' ')
            if last_space > max_length * 0.8:  # Only if we don't lose too much
                truncated = truncated[:last_space]
        
        logger.warning(f"Truncated {field_name} from {len(value)} to {len(truncated)+3} characters")
        return truncated + '...'
    
    @staticmethod
    def format_designations(designations_list, max_length=500):
        """Format professional designations intelligently"""
        if not designations_list:
            return ''
        
        # Sort by length to prioritize shorter, more common designations
        sorted_designations = sorted(designations_list, key=len)
        
        result = []
        current_length = 0
        
        for designation in sorted_designations:
            # Add 2 for ', ' separator
            needed_length = len(designation) + (2 if result else 0)
            
            if current_length + needed_length <= max_length - 10:  # -10 for potential ' +X more'
                result.append(designation)
                current_length += needed_length
            else:
                break
        
        final_result = ', '.join(result)
        
        # If we couldn't fit all, add indicator
        if len(result) < len(designations_list):
            remaining = len(designations_list) - len(result)
            final_result += f' +{remaining} more'
        
        return final_result
    
    def _parse_timestamp(self, timestamp_str):
        """Parse CREA timestamp string to datetime"""
        if not timestamp_str:
            return None
        
        try:
            from datetime import datetime
            if 'T' in timestamp_str:
                clean_timestamp = timestamp_str.rstrip('Z')
                if '.' in clean_timestamp:
                    datetime_part, fraction = clean_timestamp.split('.')
                    fraction = fraction.ljust(6, '0')[:6]
                    clean_timestamp = f"{datetime_part}.{fraction}"
                return datetime.fromisoformat(clean_timestamp)
            return None
        except Exception as e:
            logger.warning(f"Error parsing timestamp {timestamp_str}: {e}")
            return None
    
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
    
    def transform_property(self, crea_property: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[Dict], List[Dict[str, Any]]]:
        """
        Transform a single CREA property to local property format
        
        Returns:
            - property_data: Main property data dict (now includes 'other_amenities' field)
            - amenity_names: List of mapped amenity names to link
            - images: List of image data dicts
            - room_data: List of room information
        """
        # Extract basic property information
        property_data = self._extract_basic_property_data(crea_property)
        
        # Extract amenities from various CREA fields
        mapped_amenities, unknown_amenities = self._extract_amenities(crea_property)
        
        # Add unknown amenities to property data as JSON array
        if unknown_amenities:
            property_data['other_amenities'] = unknown_amenities
        else:
            property_data['other_amenities'] = []
        
        # Extract and transform images
        images = self._extract_images(crea_property)
        
        # Extract room information
        room_data = self._extract_room_data(crea_property)
        
        return property_data, mapped_amenities, images, room_data
    
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
        
        # Handle dates
        availability_date = self._parse_crea_datetime(crea_property.get('AvailabilityDate'))
        modification_timestamp = self._parse_crea_datetime(crea_property.get('ModificationTimestamp'))
        
        # Build the main property data
        property_data = {
            'property_id': str(uuid.uuid4()),  # Generate new UUID
            
            # CREA Integration fields
            'listing_key': crea_property.get('ListingKey', ''),
            'modification_timestamp': modification_timestamp,
            
            # Basic info
            'title': title,
            'description': crea_property.get('PublicRemarks', ''),
            'address': crea_property.get('UnparsedAddress', ''),
            'city': crea_property.get('City', ''),
            'province': crea_property.get('StateOrProvince', ''),
            'postal_code': crea_property.get('PostalCode', ''),
            'location_display': f"{crea_property.get('UnparsedAddress', '')}, {crea_property.get('City', '')}, {crea_property.get('StateOrProvince', '')}",
            'latitude': Decimal(str(crea_property.get('Latitude', 0))) if crea_property.get('Latitude') else None,
            'longitude': Decimal(str(crea_property.get('Longitude', 0))) if crea_property.get('Longitude') else None,
            
            # Pricing
            'price': Decimal(str(crea_property.get('ListPrice', 0))) if crea_property.get('ListPrice') else None,
            'price_type': 'List Price',
            'hoa_fee': Decimal(str(crea_property.get('AssociationFee', 0))) if crea_property.get('AssociationFee') else Decimal('0'),
            
            # Property details
            'property_type_id': property_type_id,
            'property_sub_type': crea_property.get('PropertySubType', ''),
            'bedrooms': self._safe_numeric(crea_property.get('BedroomsTotal'), 0),
            'bathrooms': Decimal(str(total_bathrooms)),
            'square_feet': self._safe_numeric(crea_property.get('LivingArea') or crea_property.get('AboveGradeFinishedArea')) or None,
            'lot_size': self._safe_numeric(crea_property.get('LotSizeArea')) or None,
            'year_built': self._safe_numeric(crea_property.get('YearBuilt')) or None,
            
            # Features
            'parking_spots': parking_spots,
            'has_garage': has_garage,
            'has_basement': has_basement,
            'single_story_only': single_story_only,
            'stories': stories,
            
            # Status and marketing
            'status': 'available' if crea_property.get('StandardStatus') == 'Active' else 'inactive',
            'is_new': False,  # Could be determined by year_built or list date
            
            # CREA Marketing & Financial fields
            'tax_annual_amount': Decimal(str(crea_property.get('TaxAnnualAmount', 0))) if crea_property.get('TaxAnnualAmount') else None,
            'days_on_market': None,  # This needs to be calculated from listing dates
            'zoning': crea_property.get('Zoning', ''),
            'availability_date': availability_date,
            
            # CREA Agent and Office relationships
            'listing_agent_id': crea_property.get('ListAgentKey'),
            'listing_office_id': crea_property.get('ListOfficeKey'),
            'co_listing_agent_id': crea_property.get('CoListAgentKey'),
            'co_listing_agent_id2': crea_property.get('CoListAgentKey2'),
            'co_listing_agent_id3': crea_property.get('CoListAgentKey3'),
            'co_listing_office_id': crea_property.get('CoListOfficeKey'),
            'co_listing_office_id2': crea_property.get('CoListOfficeKey2'),
            'co_listing_office_id3': crea_property.get('CoListOfficeKey3'),
            
            # CREA Additional fields
            'mls_listing_url': crea_property.get('ListingURL'),
            'common_interest': crea_property.get('CommonInterest'),
            'accessibility_features': crea_property.get('AccessibilityFeatures', []),
        }
        
        return property_data
    
    def _parse_crea_datetime(self, date_str):
        """Parse CREA datetime string to Python datetime"""
        if not date_str:
            return None
        try:
            # CREA format: "2025-07-09T17:55:53.78Z"
            if date_str.endswith('Z'):
                date_str = date_str[:-1]  # Remove 'Z'
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
    
    def _extract_room_data(self, crea_property: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract room information from CREA property data"""
        rooms = crea_property.get('Rooms', [])
        room_data = []
        
        if not rooms:
            return room_data
        
        for room in rooms:
            if not isinstance(room, dict):
                continue
                
            room_info = {
                'room_type': room.get('RoomType', ''),
                'room_level': room.get('RoomLevel', ''),
                'room_dimensions': room.get('RoomDimensions', ''),
                'room_description': room.get('RoomDescription', '')
            }
            
            # Only add if room_type is present
            if room_info['room_type']:
                room_data.append(room_info)
        
        return room_data
    
    def _extract_amenities(self, crea_property: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """
        Extract amenities from various CREA property fields
        
        Returns:
            - mapped_amenities: List of known amenities mapped to our schema
            - unknown_amenities: List of unmapped CREA amenities for "others" category
        """
        mapped_amenities = []
        unknown_amenities = []
        
        # Helper function to process amenity lists
        def process_amenity_list(crea_amenities, source_field=""):
            if not crea_amenities:
                return
            
            for amenity in crea_amenities:
                if not amenity or str(amenity).strip() == "":
                    continue
                    
                amenity_str = str(amenity).strip()
                
                # Skip common "none" values
                if amenity_str.lower() in ['none', 'n/a', 'not applicable', 'unknown']:
                    continue
                
                if amenity_str in self.amenity_mapping:
                    mapped_amenities.append(self.amenity_mapping[amenity_str])
                else:
                    # Add to unknown amenities with source context
                    unknown_entry = f"{amenity_str}"
                    if source_field:
                        unknown_entry = f"{source_field}: {amenity_str}"
                    unknown_amenities.append(unknown_entry)
        
        # Extract from various CREA fields
        process_amenity_list(crea_property.get('Appliances', []), "Appliance")
        process_amenity_list(crea_property.get('Heating', []), "Heating")
        process_amenity_list(crea_property.get('Cooling', []), "Cooling")
        process_amenity_list(crea_property.get('ParkingFeatures', []), "Parking")
        process_amenity_list(crea_property.get('SecurityFeatures', []), "Security")
        process_amenity_list(crea_property.get('Basement', []), "Basement")
        process_amenity_list(crea_property.get('Flooring', []), "Flooring")
        process_amenity_list(crea_property.get('Fencing', []), "Fencing")
        process_amenity_list(crea_property.get('BuildingFeatures', []), "Building")
        process_amenity_list(crea_property.get('ExteriorFeatures', []), "Exterior")
        process_amenity_list(crea_property.get('PoolFeatures', []), "Pool")
        process_amenity_list(crea_property.get('WaterfrontFeatures', []), "Waterfront")
        process_amenity_list(crea_property.get('CommunityFeatures', []), "Community")
        process_amenity_list(crea_property.get('AccessibilityFeatures', []), "Accessibility")
        
        # Handle specific fields
        
        # Fireplace
        fireplace_yn = crea_property.get('FireplaceYN')
        fireplaces_total = self._safe_numeric(crea_property.get('FireplacesTotal'), 0)
        if fireplace_yn or fireplaces_total > 0:
            mapped_amenities.append('fireplace')
            
        # Fireplace features
        fireplace_features = crea_property.get('FireplaceFeatures', [])
        if fireplace_features:
            for feature in fireplace_features:
                if feature and str(feature).strip():
                    unknown_amenities.append(f"Fireplace: {feature}")
        
        # Water and Sewer
        water_source = crea_property.get('WaterSource', [])
        process_amenity_list(water_source, "Water")
        
        sewer = crea_property.get('Sewer', [])
        process_amenity_list(sewer, "Sewer")
        
        # Utilities
        utilities = crea_property.get('Utilities', [])
        process_amenity_list(utilities, "Utilities")
        
        # Remove duplicates
        mapped_amenities = list(set(mapped_amenities))
        unknown_amenities = list(set(unknown_amenities))
        
        return mapped_amenities, unknown_amenities
    
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
                                         room_data: List[Dict[str, Any]] = None) -> Property:
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
            
            # If there are other_amenities, create an "others" amenity and link it
            if property_data.get('other_amenities'):
                self._link_others_amenity(property_obj)
            
            # Create room records
            if room_data:
                self._create_rooms(property_obj, room_data)
            
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
    
    def _link_others_amenity(self, property_obj: Property):
        """Link the 'others' amenity to properties that have unmapped CREA amenities"""
        try:
            # Get or create the "others" amenity
            others_amenity = self.db.query(Amenity).filter(
                Amenity.amenity_name == 'others'
            ).first()
            
            if not others_amenity:
                others_amenity = Amenity(
                    amenity_name='others',
                    category='other'
                )
                self.db.add(others_amenity)
                self.db.flush()
            
            # Link to property
            property_obj.amenities.append(others_amenity)
            
        except Exception as e:
            print(f"Error linking others amenity: {e}")
    
    def _create_rooms(self, property_obj: Property, room_data: List[Dict[str, Any]]):
        """Create room records for the property"""
        try:
            for room_info in room_data:
                room = Room(
                    property_id=property_obj.property_id,
                    room_type=room_info.get('room_type', ''),
                    room_level=room_info.get('room_level', ''),
                    room_dimensions=room_info.get('room_dimensions', ''),
                    room_description=room_info.get('room_description', '')
                )
                self.db.add(room)
        except Exception as e:
            print(f"Error creating rooms: {e}")
    
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
            
            # Get member information using the new method
            agent_data = crea_api.get_member(agent_key)
            
            if agent_data:
                return {
                    'agent_key': agent_key,
                    'first_name': agent_data.get('MemberFirstName', ''),
                    'last_name': agent_data.get('MemberLastName', ''),
                    'middle_name': agent_data.get('MemberMiddleName', ''),
                    'email': '', # Email address not directly provided in CREA Member data
                    'phone': agent_data.get('MemberOfficePhone', ''),
                    'mobile': agent_data.get('MemberTollFreePhone', ''),
                    'fax': agent_data.get('MemberFax', ''),
                    'office_key': agent_data.get('OfficeKey', ''),
                    'office_name': agent_data.get('OfficeName', ''),
                    'license_number': agent_data.get('MemberMlsId', agent_key),
                    'member_designation': agent_data.get('MemberDesignation', []),
                    'member_status': agent_data.get('MemberStatus', ''),
                    'city': agent_data.get('MemberCity', ''),
                    'province': agent_data.get('MemberStateOrProvince', ''),
                    'languages': agent_data.get('MemberLanguages', []),
                    
                    # NEW CREA FIELDS
                    'member_mls_id': agent_data.get('MemberMlsId', ''),
                    'member_national_association_id': agent_data.get('MemberNationalAssociationId', ''),
                    'member_aor': agent_data.get('MemberAOR', ''),
                    'member_aor_key': agent_data.get('MemberAORKey', ''),
                    'member_country': agent_data.get('MemberCountry', ''),
                    'member_email_yn': agent_data.get('MemberEmailYN', False),
                    'member_name_prefix': agent_data.get('MemberNamePrefix', ''),
                    'member_name_suffix': agent_data.get('MemberNameSuffix', ''),
                    'member_office_phone_ext': agent_data.get('MemberOfficePhoneExt', ''),
                    'member_toll_free_phone': agent_data.get('MemberTollFreePhone', ''),
                    'member_type': agent_data.get('MemberType', ''),
                    'member_postal_code': agent_data.get('MemberPostalCode', ''),
                    'office_national_association_id': agent_data.get('OfficeNationalAssociationId', ''),
                    'job_title': agent_data.get('JobTitle', ''),
                }
        except Exception as e:
            print(f"Could not fetch agent details for {agent_key}: {e}")
            
        return None
    
    def transform_listing_agent_data(self, listing_agent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform CREA listing_agent data to AgentProfile schema format
        
        Args:
            listing_agent: CREA listing_agent data from property API response
            
        Returns:
            Dict with transformed agent data ready for AgentProfile creation
        """
        return {
            'agent_key': listing_agent.get('crea_agent_key'),
            'first_name': listing_agent.get('first_name'),
            'last_name': listing_agent.get('last_name'), 
            'middle_name': listing_agent.get('middle_name'),
            'email': listing_agent.get('agent_email'),
            'phone': listing_agent.get('agent_phone'),
            'mobile': listing_agent.get('agent_mobile'),
            'fax': listing_agent.get('agent_fax'),
            'office_key': None,  # This would come from listing_office
            'office_name': listing_agent.get('agency_name'),
            'license_number': listing_agent.get('license_number'),
            'member_designation': listing_agent.get('member_designation'),
            'member_status': listing_agent.get('member_status'),
            'city': listing_agent.get('city'),
            'province': listing_agent.get('province'),
            'languages': listing_agent.get('languages', []),
            'specialization': listing_agent.get('specialization'),
            'experience': listing_agent.get('experience', 0),
            'bio': listing_agent.get('bio'),
            'rating': listing_agent.get('rating'),
            'total_sales': listing_agent.get('total_sales', 0),
            'active_listings': listing_agent.get('active_listings', 0),
            'is_accepting_clients': listing_agent.get('is_accepting_clients', True)
        }
    
    def _get_office_info_from_crea(self, office_key: str) -> Optional[Dict]:
        """
        Try to get detailed office information from CREA API
        """
        try:
            # Import here to avoid circular imports
            from crea_api_client import crea_api
            
            # Get office information using the new method
            office_data = crea_api.get_office(office_key)
            
            if office_data:
                return {
                    'office_key': office_key,
                    'office_name': office_data.get('OfficeName', ''),
                    'office_phone': office_data.get('OfficePhone', ''),
                    'office_email': office_data.get('OfficeEmail', ''),
                    'office_website': office_data.get('OfficeWebsite', ''),
                    'office_address': office_data.get('OfficeAddress', ''),
                    'office_city': office_data.get('OfficeCity', ''),
                    'office_province': office_data.get('OfficeStateOrProvince', ''),
                    'office_postal_code': office_data.get('OfficePostalCode', ''),
                    'office_country': office_data.get('OfficeCountry', ''),
                    'office_fax': office_data.get('OfficeFax', ''),
                    'office_type': office_data.get('OfficeType', ''),
                    'office_status': office_data.get('OfficeStatus', ''),
                }
        except Exception as e:
            print(f"Could not fetch office details for {office_key}: {e}")
            
        return None
    
    def transform_listing_office_data(self, listing_office: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform CREA listing_office data to Office schema format
        
        Args:
            listing_office: CREA listing_office data from property API response
            
        Returns:
            Dict with transformed office data ready for Office creation
        """
        return {
            'office_key': listing_office.get('crea_office_key'),
            'office_name': listing_office.get('office_name'),
            'office_phone': listing_office.get('office_phone'),
            'office_email': listing_office.get('office_email'),
            'office_website': listing_office.get('office_website'),
            'office_address': listing_office.get('office_address'),
            'office_city': listing_office.get('office_city'),
            'office_province': listing_office.get('office_province'),
            'office_postal_code': listing_office.get('office_postal_code'),
            'office_country': listing_office.get('office_country'),
            'office_fax': listing_office.get('office_fax'),
            'office_type': listing_office.get('office_type'),
            'office_status': listing_office.get('office_status')
        }
    
    def _create_agent_from_info(self, agent_info: Dict[str, Any]) -> Optional[AgentProfile]:
        """
        Create a new agent profile from agent information
        """
        try:
            # First, handle the office if provided
            office = None
            office_key = agent_info.get('office_key')
            if office_key:
                office = self._get_or_create_office(office_key)
            
            # Check if agent already exists by CREA key
            agent_key = agent_info.get('agent_key')
            existing_agent = self.db.query(AgentProfile).filter(
                AgentProfile.crea_agent_key == agent_key
            ).first()
            
            if existing_agent:
                # Update existing agent with new CREA data if we have more detailed info
                self._update_existing_agent(existing_agent, agent_info, office)
                return existing_agent
            
            # Generate email if not provided
            email = agent_info.get('email')
            if not email:
                agent_key = agent_info.get('agent_key', 'unknown')
                email = f"agent_{agent_key}@crea.imported"
            
            # Create User (optional for CREA agents)
            agent_user = None
            if agent_info.get('email'):  # Only create user if we have real email
                agent_user = User(
                    email=email,
                    password_hash='$2b$12$placeholder_hash_for_imported_agents',
                    first_name=agent_info.get('first_name', 'Unknown'),
                    last_name=agent_info.get('last_name', 'Agent'),
                    phone=agent_info.get('phone', ''),
                    role='agent',
                    is_active=True,
                    preferences={}
                )
                self.db.add(agent_user)
                self.db.flush()
            
            # Create enhanced AgentProfile
            agent_profile = AgentProfile(
                user_id=agent_user.user_id if agent_user else None,
                crea_agent_key=agent_key,
                
                # NEW CREA INTEGRATION FIELDS
                member_mls_id=agent_info.get('member_mls_id'),
                member_national_association_id=agent_info.get('member_national_association_id'),
                member_aor=agent_info.get('member_aor'),
                member_aor_key=agent_info.get('member_aor_key'),
                member_country=agent_info.get('member_country'),
                member_email_yn=agent_info.get('member_email_yn'),
                member_name_prefix=agent_info.get('member_name_prefix'),
                member_name_suffix=agent_info.get('member_name_suffix'),
                member_office_phone_ext=agent_info.get('member_office_phone_ext'),
                member_toll_free_phone=agent_info.get('member_toll_free_phone'),
                member_type=agent_info.get('member_type'),
                member_postal_code=agent_info.get('member_postal_code'),
                office_key=agent_info.get('office_key'),
                office_national_association_id=agent_info.get('office_national_association_id'),
                job_title=agent_info.get('job_title'),
                
                # EXISTING FIELDS
                first_name=agent_info.get('first_name', 'Unknown'),
                last_name=agent_info.get('last_name', 'Agent'),
                middle_name=agent_info.get('middle_name'),
                agent_email=agent_info.get('email'),
                agent_phone=agent_info.get('phone'),
                agent_mobile=agent_info.get('mobile'),
                agent_fax=agent_info.get('fax'),
                office_id=office.office_id if office else None,
                agency_name=agent_info.get('office_name', 'CREA Import'),
                license_number=agent_info.get('license_number', agent_key),
                member_designation=agent_info.get('member_designation'),
                member_status=agent_info.get('member_status', 'Active'),
                languages=agent_info.get('languages', []),
                specialization=agent_info.get('specialization'),
                experience=agent_info.get('experience', 0),
                bio=agent_info.get('bio') or f"Agent imported from CREA system. License: {agent_info.get('license_number', 'N/A')}",
                rating=Decimal(str(agent_info.get('rating', 0.0))) if agent_info.get('rating') else Decimal('0.0'),
                total_sales=agent_info.get('total_sales', 0),
                active_listings=agent_info.get('active_listings', 0),
                is_accepting_clients=agent_info.get('is_accepting_clients', True),
                preferred_contact_method='email',
                city=agent_info.get('city'),
                province=agent_info.get('province'),
                
                # Additional CREA Fields from migration
                member_address1=agent_info.get('member_address1'),
                member_address2=agent_info.get('member_address2'),
                member_nickname=agent_info.get('member_nickname'),
                member_pager=agent_info.get('member_pager'),
                original_entry_timestamp=self._parse_timestamp(agent_info.get('original_entry_timestamp')),
                modification_timestamp=self._parse_timestamp(agent_info.get('modification_timestamp')),
                crea_media_data=agent_info.get('crea_media_data', []),
                social_media=agent_info.get('social_media', {}),
                profile_image=agent_info.get('profile_image')
            )
            
            self.db.add(agent_profile)
            self.db.commit()
            
            return agent_profile
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error creating agent {agent_key}: {e}")
            logger.error(f"Agent data: {agent_info}")
            return None
    
    def _update_existing_agent(self, existing_agent: AgentProfile, agent_info: Dict[str, Any], office: Optional[Office] = None):
        """
        Update existing agent with new CREA data if we have more detailed info
        """
        # Only update if we have better data (not placeholder CREA data)
        if agent_info.get('first_name') and agent_info.get('first_name') != 'CREA':
            existing_agent.first_name = agent_info.get('first_name', existing_agent.first_name)
            existing_agent.last_name = agent_info.get('last_name', existing_agent.last_name)
            existing_agent.middle_name = agent_info.get('middle_name', existing_agent.middle_name)
            existing_agent.agent_email = agent_info.get('email', existing_agent.agent_email)
            existing_agent.agent_phone = agent_info.get('phone', existing_agent.agent_phone)
            existing_agent.agent_mobile = agent_info.get('mobile', existing_agent.agent_mobile)
            existing_agent.agent_fax = agent_info.get('fax', existing_agent.agent_fax)
            existing_agent.city = agent_info.get('city', existing_agent.city)
            existing_agent.province = agent_info.get('province', existing_agent.province)
            existing_agent.license_number = agent_info.get('license_number', existing_agent.license_number)
            existing_agent.member_status = agent_info.get('member_status', existing_agent.member_status)
            existing_agent.specialization = agent_info.get('specialization', existing_agent.specialization)
            existing_agent.experience = agent_info.get('experience', existing_agent.experience)
            existing_agent.bio = agent_info.get('bio', existing_agent.bio)
            
            # UPDATE NEW CREA FIELDS
            existing_agent.member_mls_id = agent_info.get('member_mls_id', existing_agent.member_mls_id)
            existing_agent.member_national_association_id = agent_info.get('member_national_association_id', existing_agent.member_national_association_id)
            existing_agent.member_aor = agent_info.get('member_aor', existing_agent.member_aor)
            existing_agent.member_aor_key = agent_info.get('member_aor_key', existing_agent.member_aor_key)
            existing_agent.member_country = agent_info.get('member_country', existing_agent.member_country)
            existing_agent.member_email_yn = agent_info.get('member_email_yn', existing_agent.member_email_yn)
            existing_agent.member_name_prefix = agent_info.get('member_name_prefix', existing_agent.member_name_prefix)
            existing_agent.member_name_suffix = agent_info.get('member_name_suffix', existing_agent.member_name_suffix)
            existing_agent.member_office_phone_ext = agent_info.get('member_office_phone_ext', existing_agent.member_office_phone_ext)
            existing_agent.member_toll_free_phone = agent_info.get('member_toll_free_phone', existing_agent.member_toll_free_phone)
            existing_agent.member_type = agent_info.get('member_type', existing_agent.member_type)
            existing_agent.member_postal_code = agent_info.get('member_postal_code', existing_agent.member_postal_code)
            existing_agent.office_key = agent_info.get('office_key', existing_agent.office_key)
            existing_agent.office_national_association_id = agent_info.get('office_national_association_id', existing_agent.office_national_association_id)
            existing_agent.job_title = agent_info.get('job_title', existing_agent.job_title)
            
            # Update performance metrics if provided
            if agent_info.get('rating'):
                existing_agent.rating = Decimal(str(agent_info.get('rating')))
            if agent_info.get('total_sales'):
                existing_agent.total_sales = agent_info.get('total_sales')
            if agent_info.get('active_listings'):
                existing_agent.active_listings = agent_info.get('active_listings')
            if agent_info.get('is_accepting_clients') is not None:
                existing_agent.is_accepting_clients = agent_info.get('is_accepting_clients')
            
            # Update relationships
            if office:
                existing_agent.office_id = office.office_id
                existing_agent.agency_name = agent_info.get('office_name', existing_agent.agency_name)
            
            # Update arrays/lists
            if agent_info.get('member_designation'):
                existing_agent.member_designation = agent_info.get('member_designation')
            if agent_info.get('languages'):
                existing_agent.languages = agent_info.get('languages')
            
            self.db.flush()
    
    def _get_or_create_office(self, office_key: str, fetch_details: bool = True) -> Optional[Office]:
        """
        Get or create an office by CREA office key
        """
        try:
            # Check if office already exists
            existing_office = self.db.query(Office).filter(
                Office.crea_office_key == office_key
            ).first()
            
            if existing_office:
                return existing_office
            
            # Try to fetch office data from CREA
            office_info = self._get_office_info_from_crea(office_key)
            
            if not office_info:
                # Create basic office with just the key
                office_info = {
                    'office_key': office_key,
                    'office_name': f'Office {office_key}',
                }
            
            # Create new office
            office = Office(
                crea_office_key=office_info.get('office_key', office_key),
                office_name=office_info.get('office_name', f'Office {office_key}'),
                office_phone=office_info.get('office_phone'),
                office_email=office_info.get('office_email'),
                office_website=office_info.get('office_website'),
                office_address=office_info.get('office_address'),
                office_city=office_info.get('office_city'),
                office_province=office_info.get('office_province'),
                office_postal_code=office_info.get('office_postal_code'),
                office_country=office_info.get('office_country'),
                office_fax=office_info.get('office_fax'),
                office_type=office_info.get('office_type'),
                office_status=office_info.get('office_status', 'Active'),
            )
            
            self.db.add(office)
            self.db.flush()
            
            return office
            
        except Exception as e:
            print(f"❌ Error creating office {office_key}: {e}")
            return None
    
    def _ensure_agent_and_office_records(self, crea_property: Dict[str, Any]):
        """
        Ensure that agent and office records exist for every property,
        creating basic records even when CREA detailed data is unavailable
        """
        # Ensure listing agent exists
        listing_agent_key = crea_property.get('ListAgentKey')
        if listing_agent_key:
            existing_agent = self.db.query(AgentProfile).filter(
                AgentProfile.crea_agent_key == listing_agent_key
            ).first()
            
            if not existing_agent:
                # Get real CREA data instead of creating mock records
                try:
                    agent_info = self._get_agent_info_from_crea(listing_agent_key)
                    if agent_info:
                        self._create_agent_from_info(agent_info)
                    else:
                        print(f"⚠️  Could not fetch CREA data for agent {listing_agent_key}")
                except Exception as e:
                    print(f"⚠️  Failed to fetch agent {listing_agent_key}: {e}")
        
        # Ensure listing office exists  
        listing_office_key = crea_property.get('ListOfficeKey')
        if listing_office_key:
            existing_office = self.db.query(Office).filter(
                Office.crea_office_key == listing_office_key
            ).first()
            
            if not existing_office:
                # Create office record with real CREA data
                self._get_or_create_office(listing_office_key, fetch_details=True)
        
        # Ensure co-listing agents exist (if any)
    
    def create_agent_from_listing_data(self, listing_agent: Dict[str, Any], listing_office: Optional[Dict[str, Any]] = None) -> Optional[AgentProfile]:
        """
        Create or update agent from CREA listing_agent data
        
        Args:
            listing_agent: CREA listing_agent data
            listing_office: CREA listing_office data (optional)
            
        Returns:
            AgentProfile instance or None
        """
        try:
            # Transform the listing agent data to our format
            agent_info = self.transform_listing_agent_data(listing_agent)
            
            # If we have office data, create/get office first
            office = None
            if listing_office:
                office_info = self.transform_listing_office_data(listing_office)
                office = self.create_office_from_listing_data(listing_office)
                # Update agent info with office key for relationship
                agent_info['office_key'] = office_info.get('office_key')
            
            # Create the agent using existing method
            return self._create_agent_from_info(agent_info)
            
        except Exception as e:
            print(f"❌ Error creating agent from listing data: {e}")
            return None
    
    def create_office_from_listing_data(self, listing_office: Dict[str, Any]) -> Optional[Office]:
        """
        Create or update office from CREA listing_office data
        
        Args:
            listing_office: CREA listing_office data
            
        Returns:
            Office instance or None
        """
        try:
            # Transform the listing office data
            office_info = self.transform_listing_office_data(listing_office)
            office_key = office_info.get('office_key')
            
            if not office_key:
                print("❌ No office key provided in listing_office data")
                return None
            
            # Check if office already exists
            existing_office = self.db.query(Office).filter(
                Office.crea_office_key == office_key
            ).first()
            
            if existing_office:
                # Update existing office with new data
                self._update_existing_office(existing_office, office_info)
                return existing_office
            
            # Create new office
            office = Office(
                crea_office_key=office_key,
                office_name=office_info.get('office_name', f'Office {office_key}'),
                office_phone=office_info.get('office_phone'),
                office_email=office_info.get('office_email'),
                office_website=office_info.get('office_website'),
                office_address=office_info.get('office_address'),
                office_city=office_info.get('office_city'),
                office_province=office_info.get('office_province'),
                office_postal_code=office_info.get('office_postal_code'),
                office_country=office_info.get('office_country'),
                office_fax=office_info.get('office_fax'),
                office_type=office_info.get('office_type'),
                office_status=office_info.get('office_status', 'Active'),
            )
            
            self.db.add(office)
            self.db.flush()
            
            return office
            
        except Exception as e:
            print(f"❌ Error creating office from listing data: {e}")
            return None
    
    def _update_existing_office(self, existing_office: Office, office_info: Dict[str, Any]):
        """
        Update existing office with new data if provided
        """
        if office_info.get('office_name'):
            existing_office.office_name = office_info.get('office_name')
        if office_info.get('office_phone'):
            existing_office.office_phone = office_info.get('office_phone')
        if office_info.get('office_email'):
            existing_office.office_email = office_info.get('office_email')
        if office_info.get('office_website'):
            existing_office.office_website = office_info.get('office_website')
        if office_info.get('office_address'):
            existing_office.office_address = office_info.get('office_address')
        if office_info.get('office_city'):
            existing_office.office_city = office_info.get('office_city')
        if office_info.get('office_province'):
            existing_office.office_province = office_info.get('office_province')
        if office_info.get('office_postal_code'):
            existing_office.office_postal_code = office_info.get('office_postal_code')
        if office_info.get('office_country'):
            existing_office.office_country = office_info.get('office_country')
        if office_info.get('office_fax'):
            existing_office.office_fax = office_info.get('office_fax')
        if office_info.get('office_type'):
            existing_office.office_type = office_info.get('office_type')
        if office_info.get('office_status'):
            existing_office.office_status = office_info.get('office_status')
        
        self.db.flush()
    
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
            
            # Ensure agent and office records exist (creates basic records if CREA data unavailable)
            self._ensure_agent_and_office_records(crea_property)
            
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