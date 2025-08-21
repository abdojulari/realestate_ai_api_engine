#!/usr/bin/env python3
"""
CREA PropertyReplication Daily Sync Script

This script uses the CREA PropertyReplication endpoint to:
1. Get all ListingKeys updated since a specific date
2. Fetch detailed property data for each ListingKey
3. Sync the data to your local database
4. Track the last sync timestamp for incremental updates

Usage:
    # Sync properties updated since yesterday
    python daily_property_replication_sync.py

    # Sync properties updated since a specific date
    python daily_property_replication_sync.py --since-date 2024-01-25

    # Dry run (don't save to database)
    python daily_property_replication_sync.py --dry-run

    # Limit number of properties (for testing)
    python daily_property_replication_sync.py --limit 100
"""

import sys
import os
import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crea_api_client import crea_api
from database import SessionLocal, get_db
from db_models import Property, PropertyType, Listing
from sqlalchemy.orm import Session
from data_transformer import CREADataTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('property_replication_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# File to store last sync timestamp
LAST_SYNC_FILE = "last_property_sync.json"

class PropertyReplicationSyncer:
    """Handles CREA PropertyReplication sync operations"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            'total_listing_keys': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'new_properties': 0,
            'updated_properties': 0,
            'errors': []
        }
    
    def get_last_sync_timestamp(self) -> datetime:
        """Get the last sync timestamp from file"""
        if os.path.exists(LAST_SYNC_FILE):
            try:
                with open(LAST_SYNC_FILE, 'r') as f:
                    data = json.load(f)
                    return datetime.fromisoformat(data['last_sync'])
            except Exception as e:
                logger.warning(f"Could not read last sync file: {e}")
        
        # Default to yesterday if no previous sync
        return datetime.now() - timedelta(days=1)
    
    def save_last_sync_timestamp(self, timestamp: datetime):
        """Save the last sync timestamp to file"""
        if not self.dry_run:
            try:
                with open(LAST_SYNC_FILE, 'w') as f:
                    json.dump({
                        'last_sync': timestamp.isoformat(),
                        'sync_completed_at': datetime.now().isoformat()
                    }, f, indent=2)
                logger.info(f"✅ Saved last sync timestamp: {timestamp}")
            except Exception as e:
                logger.error(f"❌ Failed to save last sync timestamp: {e}")
    
    def get_property_replication_data(self, since_date: datetime, limit: Optional[int] = None) -> List[Dict]:
        """
        Get PropertyReplication data from CREA API
        
        Args:
            since_date: Get properties modified since this date
            limit: Optional limit for testing
            
        Returns:
            List of property replication records with ListingKeys
        """
        logger.info(f"🔍 Fetching PropertyReplication data since {since_date}")
        
        # Format date for OData filter
        odata_date = since_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        # Build OData filter
        filters = {
            '$filter': f"ModificationTimestamp gt {odata_date}",
            '$orderby': 'ModificationTimestamp desc'
        }
        
        if limit:
            filters['$top'] = limit
            logger.info(f"🔢 Limiting to {limit} records for testing")
        
        try:
            # Use the corrected PropertyReplication API call with since_date parameter
            logger.info(f"🚀 Calling PropertyReplication endpoint with since_date: {odata_date}")
            response = crea_api.get_property_replication(since_date=odata_date)
            
            if 'value' in response:
                properties = response['value']
                logger.info(f"✅ Found {len(properties)} properties updated since {since_date}")
                
                # Apply limit if specified (PropertyReplication doesn't support $top)
                if limit and len(properties) > limit:
                    properties = properties[:limit]
                    logger.info(f"🔢 Limited to {limit} properties for testing")
                
                # Show sample of what we got
                if properties:
                    sample = properties[0]
                    logger.info(f"📋 Sample fields: {list(sample.keys())[:10]}")
                    if 'ListingKey' in sample:
                        logger.info(f"🔑 Sample ListingKey: {sample['ListingKey']}")
                    if 'ModificationTimestamp' in sample:
                        logger.info(f"📅 Sample ModificationTimestamp: {sample['ModificationTimestamp']}")
                
                return properties
            else:
                logger.warning(f"⚠️  No 'value' field in response: {response}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching PropertyReplication data: {e}")
            self.stats['errors'].append(f"PropertyReplication fetch error: {e}")
            return []
    
    def get_detailed_property_data(self, listing_key: str) -> Optional[Dict]:
        """
        Get detailed property data using ListingKey
        
        Args:
            listing_key: The ListingKey from PropertyReplication
            
        Returns:
            Detailed property data or None if failed
        """
        try:
            logger.debug(f"🔍 Fetching detailed data for ListingKey: {listing_key}")
            
            # Use the specific property endpoint with ListingKey
            response = crea_api.get_properties(property_id=listing_key)
            
            if response and ('value' in response or 'ListingKey' in response):
                # Handle both single property and array responses
                if 'value' in response and isinstance(response['value'], list):
                    if response['value']:
                        return response['value'][0]
                    else:
                        logger.warning(f"⚠️  Empty array for ListingKey: {listing_key}")
                        return None
                elif 'ListingKey' in response:
                    # Direct property object
                    return response
                else:
                    logger.warning(f"⚠️  Unexpected response format for ListingKey: {listing_key}")
                    return None
            else:
                logger.warning(f"⚠️  No property data found for ListingKey: {listing_key}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error fetching property {listing_key}: {e}")
            self.stats['errors'].append(f"Property fetch error for {listing_key}: {e}")
            return None
    
    def save_property_to_database(self, property_data: Dict, db: Session) -> bool:
        """
        Save or update property in local database using CREADataTransformer
        
        Args:
            property_data: Property data from CREA API
            db: Database session
            
        Returns:
            True if successful, False otherwise
        """
        try:
            listing_key = property_data.get('ListingKey')
            if not listing_key:
                logger.warning("⚠️  Property data missing ListingKey")
                return False
            
            # Initialize the CREA data transformer
            transformer = CREADataTransformer(db)
            
            # Check if property already exists by MLS number (which corresponds to ListingKey)
            # Note: Using the existing Listing.mls_number field instead of a new listing_key field
            existing_listing = db.query(Listing).filter(
                Listing.mls_number == listing_key
            ).first()
            
            existing_property = existing_listing.property if existing_listing else None
            
            if existing_property:
                # Update existing property using transformer's update logic
                logger.info(f"🔄 Updating existing property with ListingKey: {listing_key}")
                
                # Use the transformer's process_listing_update method
                result = transformer._process_listing_update(
                    property_data, 
                    'Active' if property_data.get('StandardStatus') == 'Active' else 'Inactive'
                )
                
                if result.get('updated'):
                    self.stats['updated_properties'] += 1
                    action = "updated"
                else:
                    action = "no changes"
                    
            else:
                # Create new property with full transformation
                logger.info(f"🆕 Creating new property with ListingKey: {listing_key}")
                
                if not self.dry_run:
                    # Use the comprehensive transformer method
                    property_obj, agent, listing = transformer.transform_and_create_property_with_agent(property_data)
                    
                    if property_obj:
                        self.stats['new_properties'] += 1
                        action = "created"
                        logger.info(f"✅ Created property: {property_obj.title}")
                        
                        if agent:
                            logger.info(f"👤 Associated with agent: {agent.full_name}")
                        if listing:
                            logger.info(f"📋 Created listing with MLS: {listing.mls_number}")
                    else:
                        action = "failed to create"
                        return False
                else:
                    # Dry run - just transform and validate
                    transformed_data, amenities, images, rooms = transformer.transform_property(property_data)
                    self.stats['new_properties'] += 1
                    action = "would create"
                    logger.info(f"🔍 [DRY RUN] Would create property: {transformed_data.get('title', 'Unknown')}")
                    logger.info(f"🔍 [DRY RUN] Would add {len(amenities)} amenities, {len(images)} images")
            
            if not self.dry_run:
                logger.info(f"✅ Property {listing_key} {action} successfully")
            else:
                logger.info(f"🔍 [DRY RUN] Property {listing_key} {action}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving property {property_data.get('ListingKey', 'unknown')}: {e}")
            self.stats['errors'].append(f"Database save error: {e}")
            if not self.dry_run:
                db.rollback()
            return False
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int"""
        if value is None or value == '':
            return None
        try:
            return int(float(value))  # Handle string numbers
        except (ValueError, TypeError):
            return None
    
    def _safe_datetime(self, value) -> Optional[datetime]:
        """Safely convert value to datetime"""
        if value is None or value == '':
            return None
        try:
            # Handle ISO format with Z suffix
            if isinstance(value, str):
                if value.endswith('Z'):
                    value = value[:-1] + '+00:00'
                return datetime.fromisoformat(value)
            return value
        except (ValueError, TypeError):
            return None
    
    def sync_properties(self, since_date: datetime, limit: Optional[int] = None) -> Dict:
        """
        Main sync function that orchestrates the entire process
        
        Args:
            since_date: Sync properties modified since this date
            limit: Optional limit for testing
            
        Returns:
            Dictionary with sync statistics
        """
        start_time = datetime.now()
        logger.info(f"🚀 Starting PropertyReplication sync since {since_date}")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be saved to database")
        
        # Step 1: Get PropertyReplication data (ListingKeys)
        replication_data = self.get_property_replication_data(since_date, limit)
        self.stats['total_listing_keys'] = len(replication_data)
        
        if not replication_data:
            logger.info("ℹ️  No properties found to sync")
            return self.stats
        
        # Step 2: Extract ListingKeys
        listing_keys = []
        for item in replication_data:
            if 'ListingKey' in item:
                listing_keys.append(item['ListingKey'])
        
        logger.info(f"🔑 Extracted {len(listing_keys)} ListingKeys to process")
        
        # Step 3: Get detailed data for each ListingKey and save to database
        db = SessionLocal()
        try:
            for i, listing_key in enumerate(listing_keys, 1):
                logger.info(f"📦 Processing {i}/{len(listing_keys)}: {listing_key}")
                
                # Get detailed property data
                property_data = self.get_detailed_property_data(listing_key)
                
                if property_data:
                    self.stats['successful_fetches'] += 1
                    
                    # Save to database
                    success = self.save_property_to_database(property_data, db)
                    if not success:
                        self.stats['failed_fetches'] += 1
                else:
                    self.stats['failed_fetches'] += 1
                
                # Progress update every 10 properties
                if i % 10 == 0:
                    logger.info(f"📊 Progress: {i}/{len(listing_keys)} processed")
        
        finally:
            db.close()
        
        # Step 4: Update last sync timestamp
        latest_timestamp = max(
            [self._safe_datetime(item.get('ModificationTimestamp')) for item in replication_data 
             if self._safe_datetime(item.get('ModificationTimestamp'))] or [since_date]
        )
        self.save_last_sync_timestamp(latest_timestamp)
        
        # Final statistics
        duration = datetime.now() - start_time
        logger.info(f"✅ Sync completed in {duration}")
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   - Total ListingKeys found: {self.stats['total_listing_keys']}")
        logger.info(f"   - Successful fetches: {self.stats['successful_fetches']}")
        logger.info(f"   - Failed fetches: {self.stats['failed_fetches']}")
        logger.info(f"   - New properties: {self.stats['new_properties']}")
        logger.info(f"   - Updated properties: {self.stats['updated_properties']}")
        logger.info(f"   - Errors: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            logger.warning(f"⚠️  Errors encountered:")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                logger.warning(f"   - {error}")
        
        return self.stats

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='CREA PropertyReplication Daily Sync')
    parser.add_argument('--since-date', type=str, 
                       help='Sync properties since this date (YYYY-MM-DD format)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without saving to database')
    parser.add_argument('--limit', type=int,
                       help='Limit number of properties to process (for testing)')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Determine since_date
    if args.since_date:
        try:
            since_date = datetime.strptime(args.since_date, '%Y-%m-%d')
        except ValueError:
            logger.error("❌ Invalid date format. Use YYYY-MM-DD")
            sys.exit(1)
    else:
        syncer = PropertyReplicationSyncer(dry_run=True)  # Don't save timestamp in dry mode
        since_date = syncer.get_last_sync_timestamp()
        logger.info(f"📅 Using last sync timestamp: {since_date}")
    
    # Run the sync
    syncer = PropertyReplicationSyncer(dry_run=args.dry_run)
    stats = syncer.sync_properties(since_date, args.limit)
    
    # Exit with error code if there were significant failures
    if stats['failed_fetches'] > stats['successful_fetches'] / 2:
        logger.error("❌ Too many failures, exiting with error code")
        sys.exit(1)
    
    logger.info("🎉 Sync completed successfully!")

if __name__ == "__main__":
    main()
