#!/usr/bin/env python3
"""
Populate Missing CREA Fields for Existing Agents

This script updates existing AgentProfile records that have crea_agent_key
but are missing the new CREA fields we just added to the database.

Usage:
    python populate_missing_crea_fields.py
    
    # Dry run to see what would be updated
    python populate_missing_crea_fields.py --dry-run
    
    # Limit processing for testing
    python populate_missing_crea_fields.py --limit 10
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from db_models import AgentProfile
from crea_api_client import crea_api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class CREAFieldsPopulator:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            'total_agents': 0,
            'agents_needing_update': 0,
            'successfully_updated': 0,
            'api_errors': 0,
            'database_errors': 0
        }
    
    def get_crea_member_data(self, crea_agent_key: str) -> Optional[Dict]:
        """Fetch complete CREA member data"""
        try:
            member_data = crea_api.get_member(crea_agent_key)
            if member_data:
                logger.debug(f"✅ Fetched CREA data for agent {crea_agent_key}")
                return member_data
            else:
                logger.warning(f"⚠️  No CREA data returned for agent {crea_agent_key}")
                return None
        except Exception as e:
            logger.error(f"❌ Error fetching CREA data for agent {crea_agent_key}: {e}")
            self.stats['api_errors'] += 1
            return None
    
    def update_agent_with_crea_data(self, agent: AgentProfile, member_data: Dict, db) -> bool:
        """Update agent with missing CREA fields"""
        try:
            if self.dry_run:
                logger.info(f"🔍 DRY RUN: Would update agent {agent.crea_agent_key} with:")
                logger.info(f"   • MemberMlsId: {member_data.get('MemberMlsId')}")
                logger.info(f"   • MemberType: {member_data.get('MemberType')}")
                logger.info(f"   • MemberAOR: {member_data.get('MemberAOR')}")
                logger.info(f"   • JobTitle: {member_data.get('JobTitle')}")
                return True
            
            # Update the new CREA fields
            agent.member_mls_id = member_data.get('MemberMlsId', '')
            agent.member_national_association_id = member_data.get('MemberNationalAssociationId', '')
            agent.member_aor = member_data.get('MemberAOR', '')
            agent.member_aor_key = member_data.get('MemberAORKey', '')
            agent.member_country = member_data.get('MemberCountry', '')
            agent.member_email_yn = member_data.get('MemberEmailYN', False)
            agent.member_name_prefix = member_data.get('MemberNamePrefix', '')
            agent.member_name_suffix = member_data.get('MemberNameSuffix', '')
            agent.member_office_phone_ext = member_data.get('MemberOfficePhoneExt', '')
            agent.member_toll_free_phone = member_data.get('MemberTollFreePhone', '')
            agent.member_type = member_data.get('MemberType', '')
            agent.member_postal_code = member_data.get('MemberPostalCode', '')
            agent.office_key = member_data.get('OfficeKey', '')
            agent.office_national_association_id = member_data.get('OfficeNationalAssociationId', '')
            agent.job_title = member_data.get('JobTitle', '')
            
            # Update languages if provided and currently empty
            if member_data.get('MemberLanguages') and not agent.languages:
                agent.languages = member_data.get('MemberLanguages', [])
            
            db.flush()
            logger.info(f"✅ Updated agent {agent.crea_agent_key} ({agent.first_name} {agent.last_name})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database error updating agent {agent.crea_agent_key}: {e}")
            self.stats['database_errors'] += 1
            return False
    
    def populate_missing_fields(self, limit: Optional[int] = None) -> Dict:
        """Find agents with missing CREA fields and populate them"""
        start_time = datetime.now()
        logger.info("🚀 Starting CREA fields population for existing agents")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be saved to database")
        
        db = SessionLocal()
        try:
            # Find agents with crea_agent_key but missing new CREA fields
            query = db.query(AgentProfile).filter(
                AgentProfile.crea_agent_key.isnot(None),
                AgentProfile.member_mls_id.is_(None)  # If this is None, other fields likely are too
            )
            
            if limit:
                query = query.limit(limit)
                logger.info(f"⚠️  LIMIT SET: Processing only {limit} agents for testing")
            
            agents_to_update = query.all()
            
            self.stats['total_agents'] = db.query(AgentProfile).filter(
                AgentProfile.crea_agent_key.isnot(None)
            ).count()
            self.stats['agents_needing_update'] = len(agents_to_update)
            
            logger.info(f"📊 Found {self.stats['agents_needing_update']} agents needing CREA field updates")
            logger.info(f"📊 Total CREA agents in database: {self.stats['total_agents']}")
            
            if not agents_to_update:
                logger.info("✅ All agents already have complete CREA data!")
                return self.stats
            
            # Process each agent
            for i, agent in enumerate(agents_to_update, 1):
                logger.info(f"🔄 Processing agent {i}/{len(agents_to_update)}: {agent.crea_agent_key}")
                
                # Fetch CREA member data
                member_data = self.get_crea_member_data(agent.crea_agent_key)
                
                if member_data:
                    # Update agent with new fields
                    if self.update_agent_with_crea_data(agent, member_data, db):
                        self.stats['successfully_updated'] += 1
                
                # Show progress every 10 agents
                if i % 10 == 0:
                    logger.info(f"⏳ Progress: {i}/{len(agents_to_update)} agents processed")
            
            # Commit all changes
            if not self.dry_run:
                db.commit()
                logger.info("💾 All changes committed to database")
            else:
                logger.info("🔍 DRY RUN: No changes committed")
            
            elapsed = datetime.now() - start_time
            logger.info(f"⏱️  Total processing time: {elapsed.total_seconds():.2f} seconds")
            
            return self.stats
            
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Fatal error during population: {e}")
            return self.stats
        finally:
            db.close()
    
    def print_summary(self):
        """Print final summary of the population process"""
        logger.info("\\n" + "="*60)
        logger.info("📊 CREA FIELDS POPULATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total CREA agents in database: {self.stats['total_agents']}")
        logger.info(f"Agents needing field updates: {self.stats['agents_needing_update']}")
        logger.info(f"Successfully updated: {self.stats['successfully_updated']}")
        logger.info(f"API errors: {self.stats['api_errors']}")
        logger.info(f"Database errors: {self.stats['database_errors']}")
        
        success_rate = (self.stats['successfully_updated'] / max(1, self.stats['agents_needing_update'])) * 100
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        if self.stats['successfully_updated'] > 0:
            logger.info("\\n✅ POPULATION COMPLETED!")
            logger.info("🔍 You can now test the endpoints to see all CREA fields populated")
        else:
            logger.info("\\n⚠️  No agents were updated")

def main():
    parser = argparse.ArgumentParser(description='Populate missing CREA fields for existing agents')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be updated without making changes')
    parser.add_argument('--limit', type=int,
                       help='Limit number of agents to process (for testing)')
    
    args = parser.parse_args()
    
    populator = CREAFieldsPopulator(dry_run=args.dry_run)
    
    try:
        stats = populator.populate_missing_fields(limit=args.limit)
        populator.print_summary()
        
        if stats['successfully_updated'] > 0 and not args.dry_run:
            logger.info("\\n🎉 CREA fields population completed successfully!")
            logger.info("   1. Test /api/v1/agents/ to see populated CREA fields")
            logger.info("   2. Test /api/v1/agent-profiles/ for complete data")
        
    except KeyboardInterrupt:
        logger.info("\\n⚠️  Population interrupted by user")
    except Exception as e:
        logger.error(f"\\n❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
