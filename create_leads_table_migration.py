#!/usr/bin/env python3
"""
Database Migration: Create Leads Table

This migration creates the leads table for capturing and managing real estate leads
with automatic integration.

Usage:
    python create_leads_table_migration.py
"""

import sys
import os
from sqlalchemy import text

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine

def run_migration():
    """Create leads table with all required fields and indexes"""
    
    print("🚀 Starting Leads table migration...")
    
    # SQL to create the leads table
    migration_sql = """
    -- Create leads table
    CREATE TABLE IF NOT EXISTS leads (
        lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        
        -- Auto-populated from AgentProfile
        agent_profile_id UUID NOT NULL REFERENCES agent_profiles(profile_id) ON DELETE CASCADE,
        crea_agent_key VARCHAR(50) NOT NULL,
        office_key VARCHAR(50),
        
        -- Required Lead API fields
        culture VARCHAR(10) NOT NULL DEFAULT 'en-CA',
        listing_key VARCHAR(50) NOT NULL,
        sender_name VARCHAR(255) NOT NULL,
        sender_email_address VARCHAR(255) NOT NULL,
        sender_phone_number VARCHAR(50),
        preferred_method_contact VARCHAR(20),
        sender_phone_extension INTEGER,
        message TEXT NOT NULL,
        
        -- Lead tracking and management
        lead_status VARCHAR(50) NOT NULL DEFAULT 'new',
        lead_source VARCHAR(100),
        lead_priority VARCHAR(20) NOT NULL DEFAULT 'medium',
        
        -- API response tracking
        crea_lead_id VARCHAR(100),
        crea_submission_status VARCHAR(50) NOT NULL DEFAULT 'pending',
        crea_submission_error TEXT,
        crea_submitted_at TIMESTAMP,
        
        -- Lead qualification data
        budget_min DECIMAL(12,2),
        budget_max DECIMAL(12,2),
        desired_location VARCHAR(255),
        property_type_preference VARCHAR(100),
        timeline VARCHAR(100),
        financing_pre_approved BOOLEAN DEFAULT FALSE,
        
        -- Follow-up tracking
        follow_up_date TIMESTAMP,
        last_contact_date TIMESTAMP,
        contact_attempts INTEGER DEFAULT 0,
        notes TEXT,
        
        -- Timestamps
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- Constraints
        CONSTRAINT chk_culture CHECK (culture IN ('en-CA', 'fr-CA')),
        CONSTRAINT chk_lead_status CHECK (lead_status IN ('new', 'contacted', 'qualified', 'converted', 'closed')),
        CONSTRAINT chk_lead_priority CHECK (lead_priority IN ('low', 'medium', 'high', 'urgent')),
        CONSTRAINT chk_preferred_contact CHECK (preferred_method_contact IN ('email', 'phone', 'text') OR preferred_method_contact IS NULL),
        CONSTRAINT chk_submission_status CHECK (crea_submission_status IN ('pending', 'submitted', 'failed')),
        CONSTRAINT chk_budget_range CHECK (budget_max IS NULL OR budget_min IS NULL OR budget_max >= budget_min)
    );
    
    -- Create indexes for performance
    CREATE INDEX IF NOT EXISTS idx_leads_agent_profile ON leads(agent_profile_id);
    CREATE INDEX IF NOT EXISTS idx_leads_crea_agent_key ON leads(crea_agent_key);
    CREATE INDEX IF NOT EXISTS idx_leads_listing_key ON leads(listing_key);
    CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(lead_status);
    CREATE INDEX IF NOT EXISTS idx_leads_created_date ON leads(created_at);
    CREATE INDEX IF NOT EXISTS idx_leads_follow_up_date ON leads(follow_up_date);
    CREATE INDEX IF NOT EXISTS idx_leads_priority_status ON leads(lead_priority, lead_status);
    CREATE INDEX IF NOT EXISTS idx_leads_sender_email ON leads(sender_email_address);
    
    -- Create trigger to update updated_at timestamp
    CREATE OR REPLACE FUNCTION update_leads_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    
    DROP TRIGGER IF EXISTS trigger_update_leads_updated_at ON leads;
    CREATE TRIGGER trigger_update_leads_updated_at
        BEFORE UPDATE ON leads
        FOR EACH ROW
        EXECUTE FUNCTION update_leads_updated_at();
    """
    
    try:
        db = SessionLocal()
        
        # Execute the migration
        db.execute(text(migration_sql))
        db.commit()
        
        print("✅ Migration completed successfully!")
        print("✅ Created leads table with all required fields")
        print("✅ Created 8 indexes for search optimization")
        print("✅ Added constraints for data validation")
        print("✅ Created auto-update trigger for updated_at field")
        
        # Verify the table was created
        result = db.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'leads' 
            ORDER BY ordinal_position;
        """))
        
        columns = result.fetchall()
        print(f"✅ Verified table created with {len(columns)} columns:")
        for col in columns[:5]:  # Show first 5 columns
            print(f"   • {col[0]} ({col[1]}) - nullable: {col[2]}")
        if len(columns) > 5:
            print(f"   ... and {len(columns) - 5} more columns")
            
        db.close()
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False
        
    return True

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("\\n🎉 Leads table migration completed! You can now:")
        print("   1. Create leads via POST /api/v1/leads/")
        print("   2. Leads will auto-sync crea_agent_key and office_key")
        print("   3. Leads are automatically submitted to API")
        print("   4. Track lead status and follow-ups")
    else:
        print("\\n❌ Migration failed. Please check the error above.")
        sys.exit(1)
