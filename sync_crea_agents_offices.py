#!/usr/bin/env python3
"""
CREA Agent and Office Data Sync Script

This script fetches real CREA agent and office data from properties and populates
the AgentProfile and Office tables with actual CREA information.

Usage:
    # Sync agents and offices from all existing properties
    python sync_crea_agents_offices.py

    # Sync from specific province
    python sync_crea_agents_offices.py --province "Ontario"

    # Limit processing (for testing)
    python sync_crea_agents_offices.py --limit 100

    # Dry run to see what would be synced
    python sync_crea_agents_offices.py --dry-run
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional, Set
from collections import Counter

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crea_api_client import crea_api
from database import SessionLocal
from db_models import Property, AgentProfile, Office
from sqlalchemy.orm import Session
from data_transformer import CREADataTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crea_agents_offices_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CREAAgentOfficeSyncer:
    """Syncs real CREA agent and office data from existing properties"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            'properties_processed': 0,
            'unique_agent_keys': 0,
            'unique_office_keys': 0,
            'agents_created': 0,
            'agents_updated': 0,
            'offices_created': 0,
            'offices_updated': 0,
            'api_calls_made': 0,
            'api_errors': 0,
            'errors': []
        }
        self.processed_agent_keys: Set[str] = set()
        self.processed_office_keys: Set[str] = set()
    
    def get_agent_office_keys_from_properties(self, db: Session, province: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, List[str]]:
        """Extract unique agent and office keys from existing properties"""
        logger.info("🔍 Extracting agent and office keys from existing properties...")
        
        query = db.query(Property)
        
        if province:
            query = query.filter(Property.province.ilike(f"%{province}%"))
        
        if limit:
            query = query.limit(limit)
        
        properties = query.all()
        self.stats['properties_processed'] = len(properties)
        
        agent_keys = set()
        office_keys = set()
        
        for prop in properties:
            # Collect all agent keys
            for agent_field in ['listing_agent_id', 'co_listing_agent_id', 'co_listing_agent_id2', 'co_listing_agent_id3']:
                agent_key = getattr(prop, agent_field, None)
                if agent_key:
                    agent_keys.add(agent_key)
            
            # Collect all office keys
            for office_field in ['listing_office_id', 'co_listing_office_id', 'co_listing_office_id2', 'co_listing_office_id3']:
                office_key = getattr(prop, office_field, None)
                if office_key:
                    office_keys.add(office_key)
        
        self.stats['unique_agent_keys'] = len(agent_keys)
        self.stats['unique_office_keys'] = len(office_keys)
        
        logger.info(f"📊 Found {len(agent_keys)} unique agent keys and {len(office_keys)} unique office keys")
        logger.info(f"📦 Processed {len(properties)} properties")
        
        return {
            'agent_keys': list(agent_keys),
            'office_keys': list(office_keys)
        }
    
    def fetch_and_sync_agent(self, agent_key: str, db: Session, transformer: CREADataTransformer) -> bool:
        """Fetch real CREA agent data and sync to database"""
        if agent_key in self.processed_agent_keys:
            return True  # Already processed
        
        try:
            logger.info(f"👤 Fetching CREA agent data for: {agent_key}")
            
            # Check if agent already exists
            existing_agent = db.query(AgentProfile).filter(
                AgentProfile.crea_agent_key == agent_key
            ).first()
            
            if existing_agent and existing_agent.first_name and existing_agent.first_name != 'Unknown':
                logger.info(f"✅ Agent {agent_key} already exists with complete data, skipping")
                self.processed_agent_keys.add(agent_key)
                return True
            
            # Fetch real CREA data
            self.stats['api_calls_made'] += 1
            agent_data = crea_api.get_member(agent_key)
            
            if agent_data:
                logger.info(f"📥 Received CREA data for agent {agent_key}")
                
                # Transform CREA member data to our format with field validation
                agent_info = {
                    'agent_key': agent_key,
                    'first_name': transformer.safely_truncate_field(agent_data.get('MemberFirstName', ''), 100, 'first_name'),
                    'last_name': transformer.safely_truncate_field(agent_data.get('MemberLastName', ''), 100, 'last_name'),
                    'middle_name': transformer.safely_truncate_field(agent_data.get('MemberMiddleName', ''), 100, 'middle_name'),
                    'agent_email': transformer.safely_truncate_field(agent_data.get('MemberEmail', ''), 255, 'email'),
                    'phone': transformer.safely_truncate_field(agent_data.get('MemberOfficePhone', ''), 50, 'phone'),
                    'mobile': transformer.safely_truncate_field(agent_data.get('MemberTollFreePhone', ''), 50, 'mobile'),
                    'fax': transformer.safely_truncate_field(agent_data.get('MemberFax', ''), 50, 'fax'),
                    'office_key': transformer.safely_truncate_field(agent_data.get('OfficeKey', ''), 50, 'office_key'),
                    'office_name': transformer.safely_truncate_field(agent_data.get('OfficeName', ''), 300, 'office_name'),
                    'license_number': transformer.safely_truncate_field(agent_data.get('MemberMlsId', agent_key), 100, 'license_number'),
                    'member_designation': transformer.format_designations(agent_data.get('MemberDesignation', []), 500),
                    'member_status': transformer.safely_truncate_field(agent_data.get('MemberStatus', 'Active'), 50, 'member_status'),
                    'city': transformer.safely_truncate_field(agent_data.get('MemberCity', ''), 100, 'city'),
                    'province': transformer.safely_truncate_field(agent_data.get('MemberStateOrProvince', ''), 100, 'province'),
                    'languages': agent_data.get('MemberLanguages', []),  # Store as list in JSONB
                    'specialization': transformer.safely_truncate_field(agent_data.get('MemberSpecialization', ''), 400, 'specialization'),
                    'bio': f"Real estate professional. License: {agent_data.get('MemberMlsId', agent_key)}",
                    'is_accepting_clients': True,
                    # Add missing CREA fields
                    'member_mls_id': transformer.safely_truncate_field(agent_data.get('MemberMlsId', ''), 50, 'member_mls_id'),
                    'member_national_association_id': transformer.safely_truncate_field(agent_data.get('MemberNationalAssociationId', ''), 50, 'member_national_association_id'),
                    'member_aor': transformer.safely_truncate_field(agent_data.get('MemberAOR', ''), 150, 'member_aor'),
                    'member_aor_key': transformer.safely_truncate_field(agent_data.get('MemberAORKey', ''), 50, 'member_aor_key'),
                    'member_country': transformer.safely_truncate_field(agent_data.get('MemberCountry', ''), 50, 'member_country'),
                    'member_email_yn': agent_data.get('MemberEmailYN', True),
                    'member_name_prefix': transformer.safely_truncate_field(agent_data.get('MemberNamePrefix', ''), 20, 'member_name_prefix'),
                    'member_name_suffix': transformer.safely_truncate_field(agent_data.get('MemberNameSuffix', ''), 20, 'member_name_suffix'),
                    'member_office_phone_ext': transformer.safely_truncate_field(agent_data.get('MemberOfficePhoneExt', ''), 20, 'member_office_phone_ext'),
                    'member_toll_free_phone': transformer.safely_truncate_field(agent_data.get('MemberTollFreePhone', ''), 50, 'member_toll_free_phone'),
                    'member_type': transformer.safely_truncate_field(agent_data.get('MemberType', ''), 50, 'member_type'),
                    'member_postal_code': transformer.safely_truncate_field(agent_data.get('MemberPostalCode', ''), 20, 'member_postal_code'),
                    'office_national_association_id': transformer.safely_truncate_field(agent_data.get('OfficeNationalAssociationId', ''), 50, 'office_national_association_id'),
                    'job_title': transformer.safely_truncate_field(agent_data.get('JobTitle', ''), 150, 'job_title'),
                    # Additional fields from migration
                    'member_address1': transformer.safely_truncate_field(agent_data.get('MemberAddress1', ''), 255, 'member_address1'),
                    'member_address2': transformer.safely_truncate_field(agent_data.get('MemberAddress2', ''), 255, 'member_address2'),
                    'member_nickname': transformer.safely_truncate_field(agent_data.get('MemberNickname', ''), 100, 'member_nickname'),
                    'member_pager': transformer.safely_truncate_field(agent_data.get('MemberPager', ''), 50, 'member_pager'),
                    'original_entry_timestamp': agent_data.get('OriginalEntryTimestamp'),
                    'modification_timestamp': agent_data.get('ModificationTimestamp'),
                    'crea_media_data': agent_data.get('Media', []),
                    'social_media': self._extract_social_media(agent_data.get('MemberSocialMedia', [])),
                    'profile_image': self._extract_profile_image(agent_data.get('Media', []))
                }
                
                if not self.dry_run:
                    # Create or update agent
                    agent_profile = transformer._create_agent_from_info(agent_info)
                    if agent_profile:
                        if existing_agent:
                            self.stats['agents_updated'] += 1
                            logger.info(f"✅ Updated agent: {agent_profile.first_name} {agent_profile.last_name}")
                        else:
                            self.stats['agents_created'] += 1
                            logger.info(f"✅ Created agent: {agent_profile.first_name} {agent_profile.last_name}")
                        
                        self.processed_agent_keys.add(agent_key)
                        return True
                    else:
                        logger.error(f"❌ Failed to create/update agent {agent_key}")
                        return False
                else:
                    logger.info(f"🔍 [DRY RUN] Would create/update agent: {agent_info.get('first_name')} {agent_info.get('last_name')}")
                    self.stats['agents_created'] += 1
                    self.processed_agent_keys.add(agent_key)
                    return True
            else:
                logger.warning(f"⚠️  No CREA data found for agent {agent_key}")
                self.processed_agent_keys.add(agent_key)
                return False
                
        except Exception as e:
            logger.error(f"❌ Error syncing agent {agent_key}: {e}")
            self.stats['api_errors'] += 1
            self.stats['errors'].append(f"Agent {agent_key}: {e}")
            return False
    
    def _extract_social_media(self, social_media_list):
        """Extract social media information from CREA data"""
        if not social_media_list:
            return {}
        
        social_media = {}
        for media in social_media_list:
            media_type = media.get('SocialMediaType', '').lower()
            url = media.get('SocialMediaUrlOrId', '')
            
            if media_type == 'facebook':
                social_media['facebook'] = url
            elif media_type == 'website':
                social_media['website'] = url
            elif media_type == 'twitter':
                social_media['twitter'] = url
            elif media_type == 'linkedin':
                social_media['linkedin'] = url
            elif media_type == 'instagram':
                social_media['instagram'] = url
            elif media_type == 'youtube':
                social_media['youtube'] = url
        
        return social_media
    
    def _extract_profile_image(self, media_list):
        """Extract profile image URL from CREA media data"""
        if not media_list:
            return None
        
        for media in media_list:
            if media.get('MediaCategory') == 'Member Photo' and media.get('PreferredPhotoYN'):
                return media.get('MediaURL')
        
        # Fallback to first member photo if no preferred photo
        for media in media_list:
            if media.get('MediaCategory') == 'Member Photo':
                return media.get('MediaURL')
        
        return None
    
    def fetch_and_sync_office(self, office_key: str, db: Session, transformer: CREADataTransformer) -> bool:
        """Fetch real CREA office data and sync to database"""
        if office_key in self.processed_office_keys:
            return True  # Already processed
        
        try:
            logger.info(f"🏢 Fetching CREA office data for: {office_key}")
            
            # Check if office already exists
            existing_office = db.query(Office).filter(
                Office.crea_office_key == office_key
            ).first()
            
            if existing_office and existing_office.office_name and not existing_office.office_name.startswith('Office '):
                logger.info(f"✅ Office {office_key} already exists with complete data, skipping")
                self.processed_office_keys.add(office_key)
                return True
            
            # Fetch real CREA data
            self.stats['api_calls_made'] += 1
            office_data = crea_api.get_office(office_key)
            
            if office_data:
                logger.info(f"📥 Received CREA data for office {office_key}")
                
                # Transform CREA office data to our format
                office_info = {
                    'office_key': office_key,
                    'office_name': office_data.get('OfficeName', f'Office {office_key}'),
                    'office_phone': office_data.get('OfficePhone', ''),
                    'office_email': office_data.get('OfficeEmail', ''),
                    'office_website': office_data.get('OfficeWebsite', ''),
                    'office_address': office_data.get('OfficeAddress', ''),
                    'office_city': office_data.get('OfficeCity', ''),
                    'office_province': office_data.get('OfficeStateOrProvince', ''),
                    'office_postal_code': office_data.get('OfficePostalCode', ''),
                    'office_country': office_data.get('OfficeCountry', 'Canada'),
                    'office_fax': office_data.get('OfficeFax', ''),
                    'office_type': office_data.get('OfficeType', ''),
                    'office_status': office_data.get('OfficeStatus', 'Active'),
                }
                
                if not self.dry_run:
                    if existing_office:
                        # Update existing office
                        transformer._update_existing_office(existing_office, office_info)
                        self.stats['offices_updated'] += 1
                        logger.info(f"✅ Updated office: {office_info['office_name']}")
                    else:
                        # Create new office
                        office = Office(
                            crea_office_key=office_key,
                            office_name=office_info['office_name'],
                            office_phone=office_info['office_phone'],
                            office_email=office_info['office_email'],
                            office_website=office_info['office_website'],
                            office_address=office_info['office_address'],
                            office_city=office_info['office_city'],
                            office_province=office_info['office_province'],
                            office_postal_code=office_info['office_postal_code'],
                            office_country=office_info['office_country'],
                            office_fax=office_info['office_fax'],
                            office_type=office_info['office_type'],
                            office_status=office_info['office_status'],
                        )
                        db.add(office)
                        db.flush()
                        self.stats['offices_created'] += 1
                        logger.info(f"✅ Created office: {office_info['office_name']}")
                    
                    self.processed_office_keys.add(office_key)
                    return True
                else:
                    logger.info(f"🔍 [DRY RUN] Would create/update office: {office_info['office_name']}")
                    self.stats['offices_created'] += 1
                    self.processed_office_keys.add(office_key)
                    return True
            else:
                logger.warning(f"⚠️  No CREA data found for office {office_key}")
                self.processed_office_keys.add(office_key)
                return False
                
        except Exception as e:
            logger.error(f"❌ Error syncing office {office_key}: {e}")
            self.stats['api_errors'] += 1
            self.stats['errors'].append(f"Office {office_key}: {e}")
            return False
    
    def sync_agents_and_offices(self, province: Optional[str] = None, limit: Optional[int] = None) -> Dict:
        """Main sync function"""
        start_time = datetime.now()
        logger.info(f"🚀 Starting CREA Agent and Office sync")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be saved to database")
        
        if province:
            logger.info(f"🌍 Filtering by province: {province}")
        
        db = SessionLocal()
        try:
            # Step 1: Extract unique keys from properties
            keys_data = self.get_agent_office_keys_from_properties(db, province, limit)
            agent_keys = keys_data['agent_keys']
            office_keys = keys_data['office_keys']
            
            if not agent_keys and not office_keys:
                logger.info("ℹ️  No agent or office keys found to sync")
                return self.stats
            
            # Step 2: Initialize transformer
            transformer = CREADataTransformer(db)
            
            # Step 3: Sync offices first (agents may reference them)
            logger.info(f"🏢 Syncing {len(office_keys)} offices...")
            for i, office_key in enumerate(office_keys, 1):
                logger.info(f"📦 Processing office {i}/{len(office_keys)}: {office_key}")
                self.fetch_and_sync_office(office_key, db, transformer)
                
                # Progress update every 10 offices
                if i % 10 == 0:
                    logger.info(f"📊 Office Progress: {i}/{len(office_keys)} processed")
            
            # Step 4: Sync agents
            logger.info(f"👥 Syncing {len(agent_keys)} agents...")
            for i, agent_key in enumerate(agent_keys, 1):
                logger.info(f"📦 Processing agent {i}/{len(agent_keys)}: {agent_key}")
                self.fetch_and_sync_agent(agent_key, db, transformer)
                
                # Progress update every 10 agents
                if i % 10 == 0:
                    logger.info(f"📊 Agent Progress: {i}/{len(agent_keys)} processed")
            
            # Step 5: Commit changes
            if not self.dry_run:
                db.commit()
                logger.info("✅ All changes committed to database")
            
        except Exception as e:
            logger.error(f"❌ Fatal error during sync: {e}")
            if not self.dry_run:
                db.rollback()
            self.stats['errors'].append(f"Fatal error: {e}")
        finally:
            db.close()
        
        # Final statistics
        duration = datetime.now() - start_time
        logger.info(f"✅ Sync completed in {duration}")
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   - Properties processed: {self.stats['properties_processed']}")
        logger.info(f"   - Unique agent keys found: {self.stats['unique_agent_keys']}")
        logger.info(f"   - Unique office keys found: {self.stats['unique_office_keys']}")
        logger.info(f"   - Agents created: {self.stats['agents_created']}")
        logger.info(f"   - Agents updated: {self.stats['agents_updated']}")
        logger.info(f"   - Offices created: {self.stats['offices_created']}")
        logger.info(f"   - Offices updated: {self.stats['offices_updated']}")
        logger.info(f"   - CREA API calls made: {self.stats['api_calls_made']}")
        logger.info(f"   - API errors: {self.stats['api_errors']}")
        logger.info(f"   - Total errors: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            logger.warning(f"⚠️  Errors encountered:")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                logger.warning(f"   - {error}")
        
        return self.stats

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='CREA Agent and Office Data Sync')
    parser.add_argument('--province', type=str,
                       help='Filter properties by province (e.g., "Ontario", "British Columbia")')
    parser.add_argument('--limit', type=int,
                       help='Limit number of properties to process (for testing)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without saving to database')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run the sync
    syncer = CREAAgentOfficeSyncer(dry_run=args.dry_run)
    stats = syncer.sync_agents_and_offices(args.province, args.limit)
    
    # Exit with error code if there were significant failures
    total_operations = stats['agents_created'] + stats['agents_updated'] + stats['offices_created'] + stats['offices_updated']
    if stats['api_errors'] > total_operations / 2:
        logger.error("❌ Too many API failures, exiting with error code")
        sys.exit(1)
    
    logger.info("🎉 CREA Agent and Office sync completed successfully!")

if __name__ == "__main__":
    main()
