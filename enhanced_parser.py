"""
Enhanced Real Estate Prompt Parser

This parser can comprehensively extract property features, amenities, location preferences,
and other detailed requirements from natural language prompts.
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class PropertyRequirements:
    """Comprehensive property requirements extracted from user prompt"""
    
    # Basic Property Features
    bedrooms_total: Optional[int] = None
    bedrooms_above_grade: Optional[int] = None
    bedrooms_main_floor: Optional[int] = None
    bedrooms_basement: Optional[int] = None
    
    bathrooms_total: Optional[int] = None
    bathrooms_full: Optional[int] = None
    bathrooms_half: Optional[int] = None
    bathrooms_main_floor: Optional[int] = None
    
    # Price
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    
    # Property Type
    property_types: List[str] = None
    
    # Size and Space
    square_feet_min: Optional[int] = None
    square_feet_max: Optional[int] = None
    lot_size_min: Optional[float] = None
    
    # Garage and Parking
    garage_type: Optional[str] = None  # "single", "double", "triple", "attached", "detached"
    garage_spaces: Optional[int] = None
    parking_spaces: Optional[int] = None
    
    # Special Rooms and Features
    bonus_room: Optional[bool] = None
    family_room: Optional[bool] = None
    den_office: Optional[bool] = None
    basement_developed: Optional[bool] = None
    basement_walkout: Optional[bool] = None
    
    # Kitchen Features
    spice_kitchen: Optional[bool] = None
    kitchen_island: Optional[bool] = None
    kitchen_updated: Optional[bool] = None
    
    # Architectural Features
    open_concept: Optional[bool] = None
    open_to_below: Optional[bool] = None
    open_to_above: Optional[bool] = None
    vaulted_ceilings: Optional[bool] = None
    hardwood_floors: Optional[bool] = None
    
    # Outdoor Features
    deck: Optional[bool] = None
    patio: Optional[bool] = None
    balcony: Optional[bool] = None
    yard_size: Optional[str] = None  # "small", "medium", "large"
    fenced_yard: Optional[bool] = None
    
    # Utilities and Systems
    air_conditioning: Optional[bool] = None
    fireplace: Optional[bool] = None
    in_suite_laundry: Optional[bool] = None
    
    # Location Preferences
    cities: List[str] = None
    neighborhoods: List[str] = None
    postal_codes: List[str] = None
    proximity_requirements: List[str] = None
    
    # School Requirements
    school_districts: List[str] = None
    school_types: List[str] = None  # "public", "catholic", "private"
    school_ratings: Optional[str] = None
    
    # Lifestyle and Amenities
    lifestyle_keywords: List[str] = None
    must_have_amenities: List[str] = None
    nice_to_have_amenities: List[str] = None
    
    def __post_init__(self):
        """Initialize empty lists"""
        if self.property_types is None:
            self.property_types = []
        if self.cities is None:
            self.cities = []
        if self.neighborhoods is None:
            self.neighborhoods = []
        if self.postal_codes is None:
            self.postal_codes = []
        if self.proximity_requirements is None:
            self.proximity_requirements = []
        if self.school_districts is None:
            self.school_districts = []
        if self.school_types is None:
            self.school_types = []
        if self.lifestyle_keywords is None:
            self.lifestyle_keywords = []
        if self.must_have_amenities is None:
            self.must_have_amenities = []
        if self.nice_to_have_amenities is None:
            self.nice_to_have_amenities = []

class EnhancedRealEstateParser:
    """Advanced parser for real estate natural language requirements"""
    
    def __init__(self):
        self.property_types = {
            'house', 'home', 'detached', 'single-family', 'bungalow', 'two-story', 'split-level',
            'condo', 'condominium', 'apartment', 'unit', 'townhouse', 'townhome', 'duplex', 
            'triplex', 'fourplex', 'villa', 'cottage', 'ranch', 'mansion'
        }
        
        self.garage_patterns = {
            r'single\s+garage': ('single', 1),
            r'double\s+garage': ('double', 2),
            r'triple\s+garage': ('triple', 3),
            r'2\s*car\s+garage': ('double', 2),
            r'3\s*car\s+garage': ('triple', 3),
            r'attached\s+garage': ('attached', None),
            r'detached\s+garage': ('detached', None)
        }
        
        self.room_features = {
            'bonus room': 'bonus_room',
            'family room': 'family_room', 
            'den': 'den_office',
            'office': 'den_office',
            'study': 'den_office',
            'spice kitchen': 'spice_kitchen',
            'butler pantry': 'spice_kitchen',
            'walkout basement': 'basement_walkout',
            'finished basement': 'basement_developed',
            'developed basement': 'basement_developed'
        }
        
        self.architectural_features = {
            'open concept': 'open_concept',
            'open to below': 'open_to_below',
            'open to above': 'open_to_above', 
            'vaulted ceiling': 'vaulted_ceilings',
            'cathedral ceiling': 'vaulted_ceilings',
            'hardwood floor': 'hardwood_floors',
            'hardwood': 'hardwood_floors'
        }
        
        self.outdoor_features = {
            'deck': 'deck',
            'patio': 'patio', 
            'balcony': 'balcony',
            'fenced yard': 'fenced_yard',
            'fence': 'fenced_yard'
        }
        
        self.cities_canada = {
            'edmonton', 'calgary', 'vancouver', 'toronto', 'montreal', 'ottawa', 'winnipeg', 'seedville',
            'quebec city', 'hamilton', 'kitchener', 'london', 'st. catharines', 'halifax',
            'victoria', 'windsor', 'oshawa', 'saskatoon', 'regina', 'sherbrooke', 'barrie',
            'st. johns', 'kelowna', 'abbotsford', 'greater sudbury', 'kingston', 'saguenay'
        }
        
        # Edmonton neighborhoods
        self.edmonton_neighborhoods = {
            'strathcona', 'garneau', 'old strathcona', 'whyte avenue', 'downtown', 'oliver',
            'westmount', 'glenora', 'alberta avenue', 'norwood', 'bonnie doon', 'mill woods',
            'sherwood park', 'st. albert', 'spruce grove', 'leduc', 'beaumont', 'devon',
            'windermere', 'summerside', 'terwillegar', 'riverbend', 'ellerslie', 'south edmonton',
            'west edmonton', 'north edmonton', 'east edmonton', 'southwest edmonton'
        }
    
    def parse_comprehensive(self, text: str) -> PropertyRequirements:
        """
        Comprehensively parse real estate requirements from natural language
        
        Example: "I am looking to purchase 3 bedrooms above grade, 1 bedroom on main floor, 
                 double garage, bonus room, spice kitchen, open to below, 3 full bathrooms 
                 with full bath on main floor"
        """
        text_lower = text.lower()
        requirements = PropertyRequirements()
        
        # Parse bedrooms with context
        self._parse_bedrooms(text_lower, requirements)
        
        # Parse bathrooms with context
        self._parse_bathrooms(text_lower, requirements)
        
        # Parse price information
        self._parse_price(text_lower, requirements)
        
        # Parse property types
        self._parse_property_types(text_lower, requirements)
        
        # Parse garage and parking
        self._parse_garage_parking(text_lower, requirements)
        
        # Parse special rooms and features
        self._parse_room_features(text_lower, requirements)
        
        # Parse architectural features
        self._parse_architectural_features(text_lower, requirements)
        
        # Parse outdoor features
        self._parse_outdoor_features(text_lower, requirements)
        
        # Parse location information
        self._parse_location(text_lower, requirements)
        
        # Parse school requirements
        self._parse_school_requirements(text_lower, requirements)
        
        # Parse lifestyle and amenities
        self._parse_lifestyle_amenities(text, requirements)
        
        # Parse size requirements
        self._parse_size_requirements(text_lower, requirements)
        
        logger.info(f"Parsed requirements: {asdict(requirements)}")
        return requirements
    
    def _parse_bedrooms(self, text: str, req: PropertyRequirements):
        """Parse bedroom requirements with context"""
        
        # Total bedrooms
        bedroom_patterns = [
            r'(\d+)\s+bedroom',
            r'(\d+)\s+bed(?:room)?s?',
            r'(\d+)br',
            r'(\d+)\s*-\s*bedroom'
        ]
        
        for pattern in bedroom_patterns:
            matches = re.findall(pattern, text)
            if matches:
                req.bedrooms_total = int(matches[0])
                break
        
        # Bedrooms above grade
        above_grade_patterns = [
            r'(\d+)\s+bedroom[s]?\s+above\s+grade',
            r'(\d+)\s+bed[s]?\s+above\s+grade',
            r'(\d+)\s+upstairs\s+bedroom',
            r'(\d+)\s+bedroom[s]?\s+upstairs'
        ]
        
        for pattern in above_grade_patterns:
            match = re.search(pattern, text)
            if match:
                req.bedrooms_above_grade = int(match.group(1))
                break
        
        # Bedrooms on main floor
        main_floor_patterns = [
            r'(\d+)\s+bedroom[s]?\s+(?:on\s+)?main\s+floor',
            r'(\d+)\s+bed[s]?\s+(?:on\s+)?main\s+floor',
            r'(\d+)\s+main\s+floor\s+bedroom',
            r'main\s+floor\s+bedroom'
        ]
        
        for pattern in main_floor_patterns:
            match = re.search(pattern, text)
            if match:
                if match.groups() and match.group(1):
                    req.bedrooms_main_floor = int(match.group(1))
                else:
                    req.bedrooms_main_floor = 1
                break
    
    def _parse_bathrooms(self, text: str, req: PropertyRequirements):
        """Parse bathroom requirements with context"""
        
        # Full bathrooms
        full_bath_patterns = [
            r'(\d+)\s+full\s+bathroom[s]?',
            r'(\d+)\s+full\s+bath[s]?',
            r'(\d+)\s+complete\s+bathroom[s]?'
        ]
        
        for pattern in full_bath_patterns:
            match = re.search(pattern, text)
            if match:
                req.bathrooms_full = int(match.group(1))
                break
        
        # Total bathrooms
        if not req.bathrooms_full:
            bath_patterns = [
                r'(\d+(?:\.\d+)?)\s+bathroom[s]?',
                r'(\d+(?:\.\d+)?)\s+bath[s]?',
                r'(\d+(?:\.\d+)?)ba'
            ]
            
            for pattern in bath_patterns:
                match = re.search(pattern, text)
                if match:
                    req.bathrooms_total = float(match.group(1))
                    break
        
        # Bathroom on main floor
        main_bath_patterns = [
            r'(?:full\s+)?bath(?:room)?\s+(?:on\s+)?main\s+floor',
            r'main\s+floor\s+(?:full\s+)?bath(?:room)?'
        ]
        
        for pattern in main_bath_patterns:
            if re.search(pattern, text):
                req.bathrooms_main_floor = 1
                break
    
    def _parse_garage_parking(self, text: str, req: PropertyRequirements):
        """Parse garage and parking requirements"""
        
        for pattern, (garage_type, spaces) in self.garage_patterns.items():
            if re.search(pattern, text):
                req.garage_type = garage_type
                if spaces:
                    req.garage_spaces = spaces
                break
        
        # Parse general garage spaces
        garage_space_patterns = [
            r'(\d+)\s*car\s+garage',
            r'(\d+)\s+stall\s+garage',
            r'garage\s+for\s+(\d+)'
        ]
        
        for pattern in garage_space_patterns:
            match = re.search(pattern, text)
            if match:
                req.garage_spaces = int(match.group(1))
                break
    
    def _parse_room_features(self, text: str, req: PropertyRequirements):
        """Parse special room features"""
        
        for feature_text, attribute in self.room_features.items():
            if feature_text in text:
                setattr(req, attribute, True)
    
    def _parse_architectural_features(self, text: str, req: PropertyRequirements):
        """Parse architectural features"""
        
        for feature_text, attribute in self.architectural_features.items():
            if feature_text in text:
                setattr(req, attribute, True)
    
    def _parse_outdoor_features(self, text: str, req: PropertyRequirements):
        """Parse outdoor features"""
        
        for feature_text, attribute in self.outdoor_features.items():
            if feature_text in text:
                setattr(req, attribute, True)
        
        # Yard size
        if 'large yard' in text:
            req.yard_size = 'large'
        elif 'big yard' in text:
            req.yard_size = 'large'
        elif 'small yard' in text:
            req.yard_size = 'small'
    
    def _parse_price(self, text: str, req: PropertyRequirements):
        """Parse price requirements"""
        
        price_patterns = [
            r'under\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'below\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'max\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'budget\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'\$(\d+(?:,\d+)*(?:k)?)\s+max'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(',', '')
                if 'k' in price_str.lower():
                    price = float(price_str.replace('k', '').replace('K', '')) * 1000
                else:
                    price = float(price_str)
                req.max_price = price
                break
        
        min_price_patterns = [
            r'above\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'over\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'minimum\s+\$(\d+(?:,\d+)*(?:k)?)',
            r'\$(\d+(?:,\d+)*(?:k)?)\s+minimum'
        ]
        
        for pattern in min_price_patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(',', '')
                if 'k' in price_str.lower():
                    price = float(price_str.replace('k', '').replace('K', '')) * 1000
                else:
                    price = float(price_str)
                req.min_price = price
                break
    
    def _parse_property_types(self, text: str, req: PropertyRequirements):
        """Parse property types"""
        
        for prop_type in self.property_types:
            if prop_type in text:
                req.property_types.append(prop_type)
    
    def _parse_location(self, text: str, req: PropertyRequirements):
        """Parse location requirements"""
        
        # Cities
        for city in self.cities_canada:
            if city in text:
                req.cities.append(city)
        
        # Edmonton neighborhoods
        for neighborhood in self.edmonton_neighborhoods:
            if neighborhood in text:
                req.neighborhoods.append(neighborhood)
        
        # Postal codes
        postal_pattern = r'[A-Za-z]\d[A-Za-z]\s*\d[A-Za-z]\d'
        postal_matches = re.findall(postal_pattern, text)
        req.postal_codes.extend(postal_matches)
        
        # Proximity requirements
        proximity_patterns = [
            r'near\s+(\w+(?:\s+\w+)*)',
            r'close\s+to\s+(\w+(?:\s+\w+)*)',
            r'walking\s+distance\s+to\s+(\w+(?:\s+\w+)*)'
        ]
        
        for pattern in proximity_patterns:
            matches = re.findall(pattern, text)
            req.proximity_requirements.extend(matches)
    
    def _parse_school_requirements(self, text: str, req: PropertyRequirements):
        """Parse school-related requirements"""
        
        school_keywords = ['school', 'education', 'district']
        if any(keyword in text for keyword in school_keywords):
            if 'public school' in text:
                req.school_types.append('public')
            if 'catholic school' in text:
                req.school_types.append('catholic')
            if 'private school' in text:
                req.school_types.append('private')
            
            if 'good school' in text or 'top rated school' in text:
                req.school_ratings = 'high'
    
    def _parse_lifestyle_amenities(self, text: str, req: PropertyRequirements):
        """Parse lifestyle keywords and amenities"""
        
        # Common amenities
        amenities_map = {
            'gym': 'fitness center',
            'fitness': 'fitness center',
            'pool': 'swimming pool',
            'swimming': 'swimming pool',
            'concierge': 'concierge',
            'doorman': 'doorman',
            'security': 'security',
            'playground': 'playground',
            'park': 'nearby park'
        }
        
        for keyword, amenity in amenities_map.items():
            if keyword in text.lower():
                req.must_have_amenities.append(amenity)
        
        # Lifestyle keywords
        lifestyle_words = ['family', 'quiet', 'modern', 'luxury', 'cozy', 'spacious', 'bright']
        req.lifestyle_keywords = [word for word in lifestyle_words if word in text.lower()]
    
    def _parse_size_requirements(self, text: str, req: PropertyRequirements):
        """Parse size requirements"""
        
        sqft_patterns = [
            r'(\d+(?:,\d+)?)\s+sq\.?\s*ft',
            r'(\d+(?:,\d+)?)\s+square\s+feet',
            r'(\d+(?:,\d+)?)\s+sqft'
        ]
        
        for pattern in sqft_patterns:
            match = re.search(pattern, text)
            if match:
                sqft = int(match.group(1).replace(',', ''))
                if 'minimum' in text or 'at least' in text:
                    req.square_feet_min = sqft
                else:
                    req.square_feet_min = sqft
                break

# Enhanced filter extraction function (backward compatible)
def extract_filters_enhanced(text: str) -> Dict[str, Any]:
    """
    Enhanced filter extraction that's backward compatible with existing code
    but provides much more comprehensive parsing
    """
    parser = EnhancedRealEstateParser()
    requirements = parser.parse_comprehensive(text)
    
    # Convert to dictionary format compatible with existing system
    filters = {}
    
    # Basic compatibility
    if requirements.bedrooms_total:
        filters['bedrooms'] = requirements.bedrooms_total
    if requirements.bathrooms_total:
        filters['bathrooms'] = requirements.bathrooms_total
    if requirements.max_price:
        filters['price_max'] = requirements.max_price
    if requirements.min_price:
        filters['price_min'] = requirements.min_price
    
    # Property types
    if requirements.property_types:
        filters['property_type'] = requirements.property_types
    
    # Location
    if requirements.cities:
        filters['location'] = requirements.cities
    if requirements.neighborhoods:
        filters['neighborhoods'] = requirements.neighborhoods
    
    # Enhanced features (new)
    filters['enhanced'] = asdict(requirements)
    
    return filters

# Legacy function for backward compatibility
def extract_filters(text: str) -> Dict[str, Any]:
    """Legacy function - now uses enhanced parser"""
    return extract_filters_enhanced(text)

# Example usage and testing
if __name__ == "__main__":
    parser = EnhancedRealEstateParser()
    
    # Test with your complex example
    test_prompt = """I am looking to purchase 3 bedrooms above grade, 1 bedroom on main floor, 
    double garage, bonus room, spice kitchen, open to below or open to above, 3 full bathrooms 
    with full bath on main floor, under $600k in south Edmonton near good schools"""
    
    print("🔍 ENHANCED PARSER TEST")
    print("=" * 50)
    print(f"Input: {test_prompt}")
    print("\n📊 Extracted Requirements:")
    
    requirements = parser.parse_comprehensive(test_prompt)
    
    # Print results in organized format
    for field, value in asdict(requirements).items():
        if value is not None and value != [] and value != "":
            print(f"  {field}: {value}")
    
    print("\n🔄 Legacy Compatibility:")
    legacy_filters = extract_filters(test_prompt)
    print(f"  Legacy filters: {legacy_filters}")
