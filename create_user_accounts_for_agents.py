#!/usr/bin/env python3
"""
Create User Accounts for CREA Agents

This script creates User accounts for all CREA agents that don't have User accounts,
using their agent_email and agent_phone data, with default password "000000".
This enables agents to login and appear in all agent endpoints.

Usage:
    python create_user_accounts_for_agents.py
    
    # Dry run to see what would be created
    python create_user_accounts_for_agents.py --dry-run
    
    # Limit processing for testing
    python create_user_accounts_for_agents.py --limit 100
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional
from passlib.context import CryptContext

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from db_models import AgentProfile, User
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('create_agent_users.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AgentUserCreator:
    """Creates User accounts for CREA agents"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.stats = {
            'total_agents': 0,
            'agents_without_users': 0,
            'users_created': 0,
            'users_updated': 0,
            'email_conflicts': 0,
            'agents_linked': 0,
            'errors': []
        }
        self.default_password_hash = pwd_context.hash("000000")
    
    def get_member_data_from_crea(self, crea_agent_key: str) -> Optional[Dict]:
        """Fetch complete member data from CREA API"""
        try:
            from crea_api_client import crea_api
            member_data = crea_api.get_member(crea_agent_key)
            logger.info(f"✅ Fetched CREA data for agent {crea_agent_key}")
            return member_data
        except Exception as e:
            logger.warning(f"⚠️  Could not fetch CREA data for agent {crea_agent_key}: {e}")
            return None
    
    def extract_social_media(self, member_data: Dict) -> Dict:
        """Extract and format social media links from CREA member data"""
        social_media = {
            "whatsapp": None,
            "facebook": None,
            "instagram": None,
            "tiktok": None,
            "twitter": None,
            "youtube": None,
            "linkedin": None,
            "website": None
        }
        
        member_social_media = member_data.get('MemberSocialMedia', [])
        for social_item in member_social_media:
            social_type = social_item.get('SocialMediaType', '').lower()
            social_url = social_item.get('SocialMediaUrlOrId', '')
            
            if social_type == 'facebook':
                social_media['facebook'] = social_url
            elif social_type == 'twitter':
                social_media['twitter'] = social_url
            elif social_type == 'linkedin':
                social_media['linkedin'] = social_url
            elif social_type == 'instagram':
                social_media['instagram'] = social_url
            elif social_type == 'youtube':
                social_media['youtube'] = social_url
            elif social_type == 'website':
                social_media['website'] = social_url
        
        return social_media
    
    def extract_profile_image(self, member_data: Dict) -> Optional[str]:
        """Extract profile image URL from CREA member data"""
        media = member_data.get('Media', [])
        for media_item in media:
            if media_item.get('MediaCategory') == 'Member Photo' and media_item.get('PreferredPhotoYN'):
                return media_item.get('MediaURL')
        return None
    
    def get_real_email_from_agent_profile(self, agent_profile: AgentProfile, db: Session) -> Optional[str]:
        """Extract real email from existing agent profile if available"""
        # Only use real email if it exists in agent_profile
        if agent_profile.agent_email and agent_profile.agent_email.strip():
            email = agent_profile.agent_email.strip().lower()
            if '@' in email and not db.query(User).filter(User.email == email).first():
                return email
        return None
    
    def generate_temporary_placeholder_email(self, agent_profile: AgentProfile, member_data: Optional[Dict], db: Session) -> str:
        """Generate a temporary placeholder email - agent must update with real email on first login"""
        
        # Use CREA member data for placeholder if available
        if member_data:
            first_name = member_data.get('MemberFirstName', '').strip().lower().replace(' ', '').replace('.', '')
            last_name = member_data.get('MemberLastName', '').strip().lower().replace(' ', '').replace('.', '')
            member_id = member_data.get('MemberMlsId', member_data.get('MemberKey', ''))
        else:
            # Fallback to agent_profile data  
            first_name = (agent_profile.first_name or '').strip().lower().replace(' ', '').replace('.', '')
            last_name = (agent_profile.last_name or '').strip().lower().replace(' ', '').replace('.', '')
            member_id = agent_profile.crea_agent_key or 'unknown'
        
        # Generate placeholder email that clearly indicates it needs to be updated
        placeholder_combinations = [
            f"TEMP.{first_name}.{last_name}.{member_id}@UPDATE-EMAIL.temp",
            f"TEMP.agent{member_id}@UPDATE-EMAIL.temp",
            f"TEMP.{member_id}.{int(datetime.now().timestamp())}@UPDATE-EMAIL.temp"
        ]
        
        for email in placeholder_combinations:
            if not db.query(User).filter(User.email == email).first():
                return email
        
        # Final fallback
        timestamp = int(datetime.now().timestamp())
        return f"TEMP.{member_id}.{timestamp}@UPDATE-EMAIL.temp"
    
    def create_user_for_agent(self, agent_profile: AgentProfile, db: Session) -> Optional[User]:
        """Create a User account for an AgentProfile with complete REAL CREA data mapping"""
        try:
            # Fetch complete CREA member data for real contact info
            member_data = self.get_member_data_from_crea(agent_profile.crea_agent_key) if agent_profile.crea_agent_key else None
            
            # Try to get real email from existing agent profile first
            real_email = self.get_real_email_from_agent_profile(agent_profile, db)
            
            if real_email:
                email = real_email
                logger.info(f"📧 Using REAL email from profile: {email}")
            else:
                # Create temporary placeholder email - agent MUST update on first login
                email = self.generate_temporary_placeholder_email(agent_profile, member_data, db)
                logger.info(f"⚠️  Created TEMPORARY email (must be updated): {email}")
            
            # Use REAL CREA data first, then fallback to agent_profile data
            if member_data:
                first_name = member_data.get('MemberFirstName') or agent_profile.first_name or 'Agent'
                last_name = member_data.get('MemberLastName') or agent_profile.last_name or f'#{agent_profile.crea_agent_key}'
                middle_name = member_data.get('MemberMiddleName')
                
                # Phone: Use REAL phone numbers from CREA
                phone = (member_data.get('MemberOfficePhone') or 
                        member_data.get('MemberTollFreePhone') or 
                        agent_profile.agent_phone or 
                        agent_profile.agent_mobile or '')
                
                # Extract REAL social media and profile data
                social_media = self.extract_social_media(member_data)
                profile_image = self.extract_profile_image(member_data)
                languages = member_data.get('MemberLanguages', [])
                
                # Update agent profile with REAL CREA data ONLY
                if not self.dry_run:
                    agent_profile.first_name = first_name
                    agent_profile.last_name = last_name
                    agent_profile.middle_name = middle_name
                    
                    # Update with REAL contact info from CREA
                    if member_data.get('MemberOfficePhone'):
                        agent_profile.agent_phone = member_data.get('MemberOfficePhone')
                    if member_data.get('MemberFax'):
                        agent_profile.agent_fax = member_data.get('MemberFax')
                    
                    # Update REAL professional info
                    agent_profile.member_designation = ', '.join(member_data.get('MemberDesignation', []))
                    agent_profile.member_status = member_data.get('MemberStatus')
                    agent_profile.languages = languages
                    agent_profile.social_media = social_media
                    
                    # Update REAL profile image
                    if profile_image:
                        agent_profile.profile_image = profile_image
                        
                    # Update REAL location data
                    if member_data.get('MemberCity'):
                        agent_profile.city = member_data.get('MemberCity')
                    if member_data.get('MemberStateOrProvince'):
                        agent_profile.province = member_data.get('MemberStateOrProvince')
                    
                    # Update bio with REAL CREA information
                    job_title = member_data.get('JobTitle', '')
                    member_type = member_data.get('MemberType', '')
                    aor = member_data.get('MemberAOR', '')
                    
                    bio_parts = [
                        f"Real Estate {member_type}" if member_type else "Real Estate Professional",
                        f"Title: {job_title}" if job_title else None,
                        f"Area: {aor}" if aor else None,
                        f"Languages: {', '.join(languages)}" if languages else None,
                        f"CREA Member ID: {member_data.get('MemberMlsId', agent_profile.crea_agent_key)}"
                    ]
                    agent_profile.bio = ' | '.join([part for part in bio_parts if part])
                    
                    logger.info(f"📋 Updated agent profile with REAL CREA data: {first_name} {last_name}")
                    
            else:
                # Fallback to existing agent_profile data
                first_name = agent_profile.first_name or 'Agent'
                last_name = agent_profile.last_name or f'#{agent_profile.crea_agent_key}'
                phone = agent_profile.agent_phone or agent_profile.agent_mobile or ''
                logger.warning(f"⚠️  No CREA data available for agent {agent_profile.crea_agent_key}")
            
            # Create User account
            user = User(
                email=email,
                password_hash=self.default_password_hash,  # "000000" as requested
                first_name=first_name,
                last_name=last_name, 
                phone=phone,
                role='agent',
                is_active=True,
                preferences={}
            )
            
            if not self.dry_run:
                db.add(user)
                db.flush()  # Get the user ID
                
                # Link AgentProfile to User
                agent_profile.user_id = user.user_id
                
                db.flush()
                
                logger.info(f"✅ Created user with password '000000': {email} for agent {first_name} {last_name}")
                return user
            else:
                logger.info(f"🔍 [DRY RUN] Would create user: {email} for agent {first_name} {last_name}")
                return user
                
        except Exception as e:
            logger.error(f"❌ Error creating user for agent {agent_profile.profile_id}: {e}")
            self.stats['errors'].append(f"Agent {agent_profile.crea_agent_key}: {e}")
            return None
    
    def process_agents_without_users(self, limit: Optional[int] = None) -> Dict:
        """Process all agents that don't have User accounts with complete CREA field mapping"""
        start_time = datetime.now()
        logger.info("🚀 Starting comprehensive User account creation for ALL CREA agents")
        logger.info("📋 Will extract ONLY REAL data from CREA API - NO FAKE DATA GENERATED")
        logger.info("📧 Email Policy: Use real emails if available, otherwise temporary placeholders")
        logger.info("🔐 All accounts created with password: 000000 (agents must update)")
        
        if self.dry_run:
            logger.info("🔍 DRY RUN MODE - No changes will be saved to database")
        
        db = SessionLocal()
        try:
            # Get all agent profiles without user accounts
            query = db.query(AgentProfile).filter(AgentProfile.user_id.is_(None))
            
            if limit:
                query = query.limit(limit)
                logger.info(f"⚠️  LIMIT SET: Processing only {limit} agents for testing")
            else:
                logger.info("✅ Processing ALL agents - No limit set")
            
            agents_without_users = query.all()
            
            self.stats['total_agents'] = db.query(AgentProfile).count()
            self.stats['agents_without_users'] = len(agents_without_users)
            
            logger.info(f"📊 Found {len(agents_without_users):,} agents without User accounts")
            logger.info(f"📊 Total agents in system: {self.stats['total_agents']:,}")
            
            if not agents_without_users:
                logger.info("ℹ️  All agents already have User accounts")
                return self.stats
            
            logger.info("🔍 Each agent will be enriched with REAL CREA data ONLY:")
            logger.info("   ✅ Real phone numbers (MemberOfficePhone, MemberTollFreePhone)")
            logger.info("   ✅ Real fax numbers (MemberFax)")
            logger.info("   ✅ Real social media profiles (Facebook, Twitter, LinkedIn, Website)")
            logger.info("   ✅ Real professional photos (Member Photo)")
            logger.info("   ✅ Real languages spoken (MemberLanguages)")  
            logger.info("   ✅ Real professional designations (MemberDesignation)")
            logger.info("   ✅ Real office information and locations")
            logger.info("   ✅ Real bio with CREA member details")
            logger.info("   ⚠️  NO fake emails - only real emails or temp placeholders")
            
            # Process each agent
            for i, agent_profile in enumerate(agents_without_users, 1):
                if i % 50 == 0:
                    logger.info(f"📊 Progress: {i:,}/{len(agents_without_users):,} processed ({(i/len(agents_without_users)*100):.1f}%)")
                
                user = self.create_user_for_agent(agent_profile, db)
                if user:
                    self.stats['users_created'] += 1
                    self.stats['agents_linked'] += 1
                
                # Commit in batches for performance and avoid timeouts
                if not self.dry_run and i % 500 == 0:
                    db.commit()
                    logger.info(f"💾 Committed batch at {i:,} users")
            
            # Final commit
            if not self.dry_run:
                db.commit()
                logger.info("✅ All changes committed to database")
                
        except Exception as e:
            logger.error(f"❌ Fatal error during processing: {e}")
            if not self.dry_run:
                db.rollback()
            self.stats['errors'].append(f"Fatal error: {e}")
        finally:
            db.close()
        
        # Final statistics
        duration = datetime.now() - start_time
        logger.info(f"✅ Processing completed in {duration}")
        logger.info(f"📊 Final Statistics:")
        logger.info(f"   - Total agents in system: {self.stats['total_agents']:,}")
        logger.info(f"   - Agents without users (processed): {self.stats['agents_without_users']:,}")
        logger.info(f"   - Users created: {self.stats['users_created']:,}")
        logger.info(f"   - Agents linked to users: {self.stats['agents_linked']:,}")
        logger.info(f"   - Email conflicts: {self.stats['email_conflicts']:,}")
        logger.info(f"   - Errors: {len(self.stats['errors'])}")
        
        if self.stats['errors']:
            logger.warning(f"⚠️  Errors encountered:")
            for error in self.stats['errors'][:5]:  # Show first 5 errors
                logger.warning(f"   - {error}")
        
        return self.stats
    
    def verify_results(self) -> Dict:
        """Verify the results after processing"""
        db = SessionLocal()
        try:
            total_agents = db.query(AgentProfile).count()
            agents_with_users = db.query(AgentProfile).filter(AgentProfile.user_id.isnot(None)).count()
            agents_without_users = db.query(AgentProfile).filter(AgentProfile.user_id.is_(None)).count()
            total_users = db.query(User).filter(User.role == 'agent').count()
            
            results = {
                'total_agents': total_agents,
                'agents_with_users': agents_with_users,
                'agents_without_users': agents_without_users,
                'agent_users': total_users,
                'coverage_percentage': (agents_with_users / total_agents * 100) if total_agents > 0 else 0
            }
            
            logger.info(f"🔍 Verification Results:")
            logger.info(f"   - Total AgentProfiles: {results['total_agents']:,}")
            logger.info(f"   - AgentProfiles with Users: {results['agents_with_users']:,}")
            logger.info(f"   - AgentProfiles without Users: {results['agents_without_users']:,}")
            logger.info(f"   - Total Agent Users: {results['agent_users']:,}")
            logger.info(f"   - Coverage: {results['coverage_percentage']:.1f}%")
            
            return results
            
        finally:
            db.close()

def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description='Create User Accounts for CREA Agents')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without saving to database')
    parser.add_argument('--limit', type=int,
                       help='Limit number of agents to process (for testing)')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only run verification, do not create users')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    creator = AgentUserCreator(dry_run=args.dry_run)
    
    if args.verify_only:
        creator.verify_results()
    else:
        # Run the main processing
        stats = creator.process_agents_without_users(args.limit)
        
        # Run verification
        creator.verify_results()
        
        # Exit with error code if there were significant failures
        if len(stats['errors']) > stats['users_created'] / 10:  # More than 10% error rate
            logger.error("❌ Too many errors, exiting with error code")
            sys.exit(1)
    
    logger.info("🎉 User account creation completed successfully!")

if __name__ == "__main__":
    main()
