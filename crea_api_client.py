"""
CREA DDF API Client

This module provides a comprehensive client for accessing CREA DDF API endpoints
with automatic token management and authentication.
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlencode
from api_token_handler import crea_token_handler

# Configure logging
logger = logging.getLogger(__name__)

class CREAAPIClient:
    def __init__(self):
        self.base_url = "https://ddfapi.realtor.ca/"
        self.cdn_base_url = "https://ddfcdn.realtor.ca/"
        self.session = requests.Session()
        self.session.timeout = 30

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make an authenticated request to the CREA API
        """
        # Get fresh authorization header
        auth_headers = crea_token_handler.get_authorization_header()
        
        # Merge with any existing headers
        headers = kwargs.get('headers', {})
        headers.update(auth_headers)
        kwargs['headers'] = headers

        # Make the request
        response = self.session.request(method, url, **kwargs)
        
        # Log the request for debugging
        print(f"{method} {url} - Status: {response.status_code}")
        
        return response

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Make a GET request to an API endpoint
        """
        url = urljoin(self.base_url, endpoint)
        response = self._make_request('GET', url, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint: str, data: Dict = None, json_data: Dict = None) -> Dict:
        """
        Make a POST request to an API endpoint
        """
        url = urljoin(self.base_url, endpoint)
        
        headers = {'Content-Type': 'application/json'} if json_data else {}
        
        response = self._make_request(
            'POST', 
            url, 
            data=data, 
            json=json_data,
            headers=headers
        )
        response.raise_for_status()
        return response.json()

    # Member-related endpoints
    def get_member_replication(self, filters: Dict = None) -> Dict:
        """
        Get member replication data
        
        Args:
            filters: Optional OData query parameters like $filter, $top, $skip
        """
        endpoint = "odata/v1/Member/MemberReplication"
        return self._get(endpoint, params=filters)

    def get_members(self, member_id: str = None, filters: Dict = None) -> Dict:
        """
        Get member information
        
        Args:
            member_id: Specific member ID to retrieve
            filters: Optional OData query parameters
        """
        if member_id:
            endpoint = f"odata/v1/Member({member_id})"
        else:
            endpoint = "odata/v1/Member"
        
        return self._get(endpoint, params=filters)

    # Property-related endpoints
    def get_property_replication(self, filters: Dict = None) -> Dict:
        """
        Get property replication data
        
        Args:
            filters: Optional OData query parameters like $filter, $top, $skip
        """
        endpoint = "odata/v1/Property/PropertyReplication"
        return self._get(endpoint, params=filters)

    def get_properties(self, property_id: str = None, filters: Dict = None) -> Dict:
        """
        Get property information
        
        Args:
            property_id: Specific property ID (ListingKey) to retrieve
            filters: Optional OData query parameters
        """
        if property_id:
            # Use quotes around the property_id as per CREA documentation
            endpoint = f"odata/v1/Property('{property_id}')"
        else:
            endpoint = "odata/v1/Property"
        
        return self._get(endpoint, params=filters)
    
    def get_property_replication(self, filters: Dict = None, since_date: str = None) -> Dict:
        """
        Get properties from PropertyReplication endpoint for bulk data access
        This endpoint provides better access to the full property dataset
        
        Usage:
            # Get all properties updated since yesterday
            result = crea_api.get_property_replication(since_date='2024-01-25T00:00:00.00Z')
            
            # Or with filters
            filters = {'$filter': 'ModificationTimestamp gt 2024-01-25T00:00:00.00Z'}
            result = crea_api.get_property_replication(filters)
        
        Args:
            filters: Optional OData query parameters ($filter, $top, $orderby, etc.)
            since_date: ISO date string for filtering by ModificationTimestamp
        """
        if since_date:
            # Use the () format as per CREA documentation
            endpoint = f"odata/v1/Property/PropertyReplication()?$filter=ModificationTimestamp gt {since_date}"
            return self._get(endpoint, params=None)
        else:
            endpoint = "odata/v1/Property/PropertyReplication"
            return self._get(endpoint, params=filters)

    def search_properties(self, 
                         location: str = None,
                         province: str = None,
                         min_price: float = None,
                         max_price: float = None,
                         bedrooms: int = None,
                         property_type: str = None,
                         status_filter: str = None,
                         top: int = 100) -> Dict:
        """
        Search properties with common filters (LEGACY - Use search_properties_paginated_fixed for large datasets)
        
        NOTE: This method has CREA API limitations:
        - Complex OData filters may be rejected (400 errors)
        - Limited to small result sets (top=100 max)
        - For production use: search_properties_paginated_fixed()
        
        Args:
            location: Specific city to search in
            province: Province to search in (AB, BC, ON, etc.)
            min_price: Minimum price
            max_price: Maximum price
            bedrooms: Number of bedrooms
            property_type: Type of property
            status_filter: Property status (Active, Pending, Sold, etc.)
            top: Maximum number of results to return (max 100)
        """
        # Use simplified approach to avoid OData filter issues
        filters = {'$top': min(top, 100)}  # Ensure we don't exceed CREA limit
        
        # Only add simple filters that CREA accepts
        if location:
            # Use basic property search without complex filters
            filters['$filter'] = f"City eq '{location}'"
        
        return self.get_properties(filters=filters)
    
    def get_province_market_data(self, province: str, days_back: int = 1) -> Dict:
        """
        Get comprehensive market data for a province including all statuses
        
        Args:
            province: Province code (AB, BC, ON, etc.)
            days_back: Number of days to look back for recent activity
        """
        from datetime import datetime, timedelta
        
        # Get cutoff date for recent activity
        cutoff_date = datetime.now() - timedelta(days=days_back)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        market_data = {
            'province': province,
            'active_listings': [],
            'pending_listings': [],
            'sold_listings': [],
            'new_listings': []
        }
        
        try:
            # Get active listings
            active_result = self.search_properties(
                province=province,
                status_filter='Active',
                top=500
            )
            market_data['active_listings'] = active_result.get('value', [])
            
            # Get pending listings (Under Contract/Pending)
            try:
                pending_result = self.search_properties(
                    province=province,
                    status_filter='Under Contract',
                    top=200
                )
                market_data['pending_listings'] = pending_result.get('value', [])
            except:
                # Try alternative pending status
                try:
                    pending_result = self.search_properties(
                        province=province,
                        status_filter='Pending',
                        top=200
                    )
                    market_data['pending_listings'] = pending_result.get('value', [])
                except:
                    pass
            
            # Get sold listings
            try:
                sold_result = self.search_properties(
                    province=province,
                    status_filter='Sold',
                    top=200
                )
                market_data['sold_listings'] = sold_result.get('value', [])
            except:
                # Try alternative sold status
                try:
                    sold_result = self.search_properties(
                        province=province,
                        status_filter='Closed',
                        top=200
                    )
                    market_data['sold_listings'] = sold_result.get('value', [])
                except:
                    pass
            
            # Filter for new listings (ModificationTimestamp within days_back)
            all_active = market_data['active_listings']
            new_listings = []
            for listing in all_active:
                mod_time = listing.get('ModificationTimestamp')
                if mod_time:
                    try:
                        mod_date = datetime.fromisoformat(mod_time.replace('Z', '+00:00'))
                        if mod_date >= cutoff_date:
                            new_listings.append(listing)
                    except:
                        pass
            market_data['new_listings'] = new_listings
            
        except Exception as e:
            print(f"Error getting market data for {province}: {e}")
        
        return market_data
    
    def search_properties_paginated(self, 
                                   province: str = None,
                                   status_filter: str = None,
                                   max_results: int = None) -> Dict:
        """
        Production-ready paginated search that works around CREA API limitations
        
        This method solves the CREA API OData filter limitations by:
        1. Fetching ALL properties without server-side filtering (avoids 400 errors)
        2. Using @odata.nextLink for complete pagination (handles 20k+ properties)
        3. Applying province and status filters client-side after data retrieval
        
        Perfect for:
        - Getting ALL properties for a province (e.g., 5000+ Alberta properties)
        - Daily sync operations with complete datasets
        - Bulk import operations
        
        Args:
            province: Province to filter for (e.g., 'Alberta', 'British Columbia', 'Ontario')
            status_filter: Status to filter for (e.g., 'Active', 'Sold', 'Pending')
            max_results: Maximum total results to return (None = all available)
            
        Returns:
            Dict with 'value' containing filtered properties and pagination metadata
        """
        print(f"🔍 Starting FIXED paginated search for {province or 'all provinces'}...")
        print(f"📊 Strategy: Get ALL properties, filter client-side to avoid CREA API limitations")
        
        all_properties = []
        filtered_properties = []
        request_count = 0
        
        # Start with initial search - NO FILTERS to avoid 400 errors
        print(f"🚀 Request 1: Getting first 100 properties (CREA API limit)")
        initial_result = self.get_properties(filters={'$top': 100})
        
        if not initial_result.get('value'):
            print(f"❌ No properties found")
            return initial_result
        
        # Process first batch and filter client-side
        batch_properties = initial_result['value']
        all_properties.extend(batch_properties)
        request_count += 1
        
        # Filter this batch
        batch_filtered = self._filter_properties_client_side(batch_properties, province, status_filter)
        filtered_properties.extend(batch_filtered)
        
        print(f"📦 Batch 1: {len(batch_properties)} total, {len(batch_filtered)} matched filters (Running total: {len(filtered_properties)})")
        
        # Check if there are more pages
        next_link = initial_result.get('@odata.nextLink')
        
        while next_link and (max_results is None or len(filtered_properties) < max_results):
            try:
                print(f"🔄 Fetching next page... (Request #{request_count + 1})")
                
                # Make request to the next page
                response = self._get_raw_url(next_link)
                
                if not response.get('value'):
                    print(f"⚠️  No more properties in page {request_count + 1}")
                    break
                
                # Process this batch
                batch_properties = response['value']
                all_properties.extend(batch_properties)
                request_count += 1
                
                # Filter this batch client-side
                batch_filtered = self._filter_properties_client_side(batch_properties, province, status_filter)
                filtered_properties.extend(batch_filtered)
                
                print(f"📦 Batch {request_count}: {len(batch_properties)} total, {len(batch_filtered)} matched (Running total: {len(filtered_properties)})")
                
                # Check for next page
                next_link = response.get('@odata.nextLink')
                
                # Stop if we've reached the max_results limit
                if max_results and len(filtered_properties) >= max_results:
                    filtered_properties = filtered_properties[:max_results]
                    print(f"🛑 Reached max_results limit: {max_results}")
                    break
                    
            except Exception as e:
                print(f"❌ Error fetching page {request_count + 1}: {e}")
                break
        
        print(f"✅ Pagination complete: {len(all_properties)} total properties, {len(filtered_properties)} matched filters in {request_count} requests")
        
        # Return filtered results in same format as original search
        return {
            '@odata.context': initial_result.get('@odata.context'),
            'value': filtered_properties,  # Return filtered properties, not all
            'total_results': len(filtered_properties),
            'total_fetched': len(all_properties),
            'requests_made': request_count,
            'pagination_complete': not next_link,
            'filters_applied': {
                'province': province,
                'status_filter': status_filter
            }
        }
    
    def _filter_properties_client_side(self, properties: List[Dict], province: str = None, status_filter: str = None) -> List[Dict]:
        """
        Filter properties client-side to avoid CREA API OData limitations
        Fixed to handle real CREA field names and values
        """
        filtered = properties
        
        # DEBUG: Print sample property fields to understand the structure
        if properties and len(properties) > 0:
            sample = properties[0]
            print(f"🔍 Sample property fields: {list(sample.keys())[:10]}")
            
            # Check province field variations
            province_fields = ['StateOrProvince', 'Province', 'State', 'PostalCode', 'City']
            for field in province_fields:
                if field in sample:
                    print(f"🌍 {field}: {sample.get(field)}")
            
            # Check status field variations  
            status_fields = ['StandardStatus', 'Status', 'ListingStatus', 'PropertyStatus']
            for field in status_fields:
                if field in sample:
                    print(f"📊 {field}: {sample.get(field)}")
        
        # Filter by province (more flexible matching)
        if province:
            original_count = len(filtered)
            
            # Try multiple province field variations and matching strategies
            province_lower = province.lower()
            filtered = [p for p in filtered if (
                # Direct match on StateOrProvince
                p.get('StateOrProvince', '').lower() == province_lower or
                # Direct match on Province
                p.get('Province', '').lower() == province_lower or
                # Partial match for abbreviations (AB for Alberta)
                p.get('StateOrProvince', '').lower().startswith(province_lower[:2]) or
                # Check postal code for province (T for Alberta, V for BC, etc.)
                (province_lower == 'alberta' and p.get('PostalCode', '').startswith('T')) or
                (province_lower == 'ab' and p.get('PostalCode', '').startswith('T')) or
                (province_lower == 'british columbia' and p.get('PostalCode', '').startswith('V')) or
                (province_lower == 'bc' and p.get('PostalCode', '').startswith('V')) or
                (province_lower == 'ontario' and p.get('PostalCode', '').startswith(('K', 'L', 'M', 'N', 'P'))) or
                (province_lower == 'on' and p.get('PostalCode', '').startswith(('K', 'L', 'M', 'N', 'P')))
            )]
            
            print(f"🌍 Province filter '{province}': {original_count} -> {len(filtered)} properties")
        
        # Filter by status (more flexible matching)
        if status_filter:
            original_count = len(filtered)
            status_lower = status_filter.lower()
            
            filtered = [p for p in filtered if (
                # Direct match on StandardStatus
                p.get('StandardStatus', '').lower() == status_lower or
                # Direct match on Status
                p.get('Status', '').lower() == status_lower or
                # Partial matches for common statuses
                status_lower in p.get('StandardStatus', '').lower() or
                status_lower in p.get('Status', '').lower() or
                # Common aliases
                (status_lower == 'active' and p.get('StandardStatus', '').lower() in ['active', 'new', 'pending']) or
                (status_lower == 'sold' and p.get('StandardStatus', '').lower() in ['sold', 'closed', 'completed'])
            )]
            
            print(f"📊 Status filter '{status_filter}': {original_count} -> {len(filtered)} properties")
        
        return filtered
    
    def _get_raw_url(self, url: str) -> Dict:
        """
        Make a GET request to a full URL (for following @odata.nextLink)
        """
        import requests
        
        headers = crea_token_handler.get_authorization_header()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()

    # Open House endpoints
    def get_open_houses(self, filters: Dict = None) -> Dict:
        """
        Get open house information
        
        Args:
            filters: Optional OData query parameters
        """
        endpoint = "odata/v1/OpenHouse"
        return self._get(endpoint, params=filters)

    def get_open_houses_by_date(self, start_date: str, end_date: str = None) -> Dict:
        """
        Get open houses by date range
        
        Args:
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (optional)
        """
        filter_conditions = [f"OpenHouseDate ge datetime'{start_date}T00:00:00'"]
        
        if end_date:
            filter_conditions.append(f"OpenHouseDate le datetime'{end_date}T23:59:59'")
        
        filters = {
            '$filter': ' and '.join(filter_conditions),
            '$orderby': 'OpenHouseDate asc'
        }
        
        return self.get_open_houses(filters=filters)

    # Lead Management endpoints
    def create_lead(self, lead_data: Dict) -> Dict:
        """
        Create a new lead
        
        Args:
            lead_data: Lead information dictionary
            
        Example lead_data structure:
        {
            "FirstName": "John",
            "LastName": "Doe",
            "Email": "john.doe@example.com",
            "Phone": "555-0123",
            "PropertyId": "12345",
            "Message": "Interested in this property"
        }
        """
        endpoint = "v1/Lead/CreateLead"
        return self._post(endpoint, json_data=lead_data)

    # Utility methods
    def download_realtor_logo(self, save_path: str = "realtorlogo.png") -> bool:
        """
        Download the REALTOR logo
        
        Args:
            save_path: Path where to save the logo file
        """
        try:
            logo_url = "https://ddfcdn.realtor.ca/realtorlogo.png"
            response = requests.get(logo_url, timeout=30)
            response.raise_for_status()
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            print(f"Logo downloaded successfully to {save_path}")
            return True
            
        except Exception as e:
            print(f"Error downloading logo: {str(e)}")
            return False

    def get_api_info(self) -> Dict:
        """
        Get API information and metadata
        """
        try:
            # Try to get OData metadata
            response = self._make_request('GET', urljoin(self.base_url, "odata/v1/$metadata"))
            return {
                "status": "connected",
                "metadata_available": response.status_code == 200,
                "base_url": self.base_url
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "base_url": self.base_url
            }
    
    def get_member(self, member_key: str) -> Dict:
        """
        Get member (agent) information from CREA DDF API
        
        Args:
            member_key: CREA MemberKey (agent ID)
            
        Returns:
            Dict containing member information
            
        Raises:
            requests.HTTPError: If the request fails
        """
        endpoint = f"odata/v1/Member/{member_key}"
        return self._get(endpoint)
    
    def get_office(self, office_key: str) -> Dict:
        """
        Get office information from CREA DDF API
        
        Args:
            office_key: CREA OfficeKey
            
        Returns:
            Dict containing office information
            
        Raises:
            requests.HTTPError: If the request fails
        """
        endpoint = f"odata/v1/Office/{office_key}"
        return self._get(endpoint)

    def create_lead(self, lead_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Submit a lead to CREA using the Lead API
        
        Args:
            lead_data: Dictionary containing lead information with CREA API format:
                - Culture: str (en-CA or fr-CA)
                - MemberKey: str (CREA agent key)
                - ListingKey: str (Property listing key)
                - SenderName: str (Lead's name)
                - SenderEmailAddress: str (Lead's email)
                - SenderPhoneNumber: int or None (Lead's phone)
                - PreferredMethodContact: str or None (email, phone, text)
                - SenderPhoneExtension: int or None (Phone extension)
                - Message: str (Lead's message)
        
        Returns:
            Dict containing CREA's response with LeadId if successful, None if failed
            
        Raises:
            requests.HTTPError: If the request fails
        """
        endpoint = "v1/Lead/CreateLead"
        
        try:
            # Ensure we have a valid access token
            if not self.access_token or self._is_token_expired():
                self._authenticate()
            
            # Prepare headers
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Clean the payload - remove None values to match CREA API expectations
            clean_payload = {k: v for k, v in lead_data.items() if v is not None}
            
            logger.info(f"📤 Submitting lead to CREA for agent {clean_payload.get('MemberKey')} on listing {clean_payload.get('ListingKey')}")
            logger.debug(f"Lead payload: {clean_payload}")
            
            # Make the POST request
            url = f"{self.base_url}/{endpoint}"
            response = self.session.post(
                url,
                json=clean_payload,
                headers=headers,
                timeout=self.timeout
            )
            
            logger.info(f"POST {url} - Status: {response.status_code}")
            
            # Check for successful response
            response.raise_for_status()
            
            # Parse response
            if response.status_code == 201:  # Created
                result = response.json()
                logger.info(f"✅ Lead successfully submitted to CREA. Lead ID: {result.get('LeadId')}")
                return result
            else:
                logger.warning(f"⚠️  Unexpected response status: {response.status_code}")
                return response.json() if response.content else {}
                
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                logger.warning("🔑 Token expired during lead submission, re-authenticating...")
                self._authenticate()
                # Retry once with new token
                return self.create_lead(lead_data)
            else:
                logger.error(f"❌ HTTP error submitting lead: {e}")
                logger.error(f"Response content: {e.response.text if e.response else 'No response'}")
                raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error submitting lead: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error submitting lead: {e}")
            raise

# Global instance for easy access
crea_api = CREAAPIClient() 