#!/usr/bin/env python3
"""
Database Migration: Add Missing CREA Fields to AgentProfile

This migration adds 15 missing CREA fields to the agent_profiles table:
- member_mls_id
- member_national_association_id  
- member_aor
- member_aor_key
- member_country
- member_email_yn
- member_name_prefix
- member_name_suffix
- member_office_phone_ext
- member_toll_free_phone
- member_type
- member_postal_code
- office_key
- office_national_association_id
- job_title

Usage:
    python add_crea_fields_migration.py
"""

import sys
import os
from sqlalchemy import text

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine

def run_migration():
    """Add missing CREA fields to agent_profiles table"""
    
    print("🚀 Starting CREA fields migration...")
    
    # SQL to add the new columns
    migration_sql = """
    -- Add missing CREA fields to agent_profiles table
    ALTER TABLE agent_profiles 
    ADD COLUMN IF NOT EXISTS member_mls_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS member_national_association_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS member_aor VARCHAR(100),
    ADD COLUMN IF NOT EXISTS member_aor_key VARCHAR(50),
    ADD COLUMN IF NOT EXISTS member_country VARCHAR(50),
    ADD COLUMN IF NOT EXISTS member_email_yn BOOLEAN,
    ADD COLUMN IF NOT EXISTS member_name_prefix VARCHAR(20),
    ADD COLUMN IF NOT EXISTS member_name_suffix VARCHAR(20),
    ADD COLUMN IF NOT EXISTS member_office_phone_ext VARCHAR(20),
    ADD COLUMN IF NOT EXISTS member_toll_free_phone VARCHAR(50),
    ADD COLUMN IF NOT EXISTS member_type VARCHAR(50),
    ADD COLUMN IF NOT EXISTS member_postal_code VARCHAR(20),
    ADD COLUMN IF NOT EXISTS office_key VARCHAR(50),
    ADD COLUMN IF NOT EXISTS office_national_association_id VARCHAR(50),
    ADD COLUMN IF NOT EXISTS job_title VARCHAR(100);
    
    -- Add indexes for the new fields
    CREATE INDEX IF NOT EXISTS idx_agent_profile_mls_id ON agent_profiles(member_mls_id);
    CREATE INDEX IF NOT EXISTS idx_agent_profile_national_id ON agent_profiles(member_national_association_id);
    CREATE INDEX IF NOT EXISTS idx_agent_profile_office_key ON agent_profiles(office_key);
    CREATE INDEX IF NOT EXISTS idx_agent_profile_member_type ON agent_profiles(member_type);
    CREATE INDEX IF NOT EXISTS idx_agent_profile_aor ON agent_profiles(member_aor);
    """
    
    try:
        db = SessionLocal()
        
        # Execute the migration
        db.execute(text(migration_sql))
        db.commit()
        
        print("✅ Migration completed successfully!")
        print("✅ Added 15 new CREA fields to agent_profiles table")
        print("✅ Created 5 new indexes for search optimization")
        
        # Verify the columns were added
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'agent_profiles' 
            AND column_name IN (
                'member_mls_id', 'member_national_association_id', 'member_aor',
                'member_aor_key', 'member_country', 'member_email_yn',
                'member_name_prefix', 'member_name_suffix', 'member_office_phone_ext',
                'member_toll_free_phone', 'member_type', 'member_postal_code',
                'office_key', 'office_national_association_id', 'job_title'
            )
            ORDER BY column_name;
        """))
        
        added_columns = [row[0] for row in result.fetchall()]
        print(f"✅ Verified {len(added_columns)} columns added:")
        for col in added_columns:
            print(f"   • {col}")
            
        db.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
        
    return True

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("\\n🎉 Migration completed! You can now:")
        print("   1. Test the /api/v1/agent-profiles/ endpoint")
        print("   2. See all CREA fields in agent responses")
        print("   3. Run the user creation script for agents")
    else:
        print("\\n❌ Migration failed. Please check the error above.")
        sys.exit(1)
