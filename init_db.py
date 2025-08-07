#!/usr/bin/env python3
"""
Database initialization script for Real Estate AI Engine.
This script creates all tables and populates them with default data.
"""

import sys
import os
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add the current directory to Python path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, SessionLocal, create_tables
from db_models import *
from auth import AuthService

def create_default_data():
    """Create default data for the database."""
    print("Creating default data...")
    
    db = SessionLocal()
    
    try:
        # Create default property types
        property_types = [
            {"type_name": "Single Family", "description": "Detached single family homes"},
            {"type_name": "Condo", "description": "Condominium units"},
            {"type_name": "Townhouse", "description": "Townhouse and row homes"},
            {"type_name": "Multi-family", "description": "Duplex, triplex, and multi-unit properties"},
            {"type_name": "Lots/Land", "description": "Vacant lots and land parcels"},
            {"type_name": "Apartment", "description": "Apartment units"},
            {"type_name": "Manufactured", "description": "Manufactured and mobile homes"}
        ]
        
        for pt_data in property_types:
            existing = db.query(PropertyType).filter(PropertyType.type_name == pt_data["type_name"]).first()
            if not existing:
                property_type = PropertyType(**pt_data)
                db.add(property_type)
        
        # Create default listing types
        listing_types = [
            {"type_name": "Owner posted", "description": "For Sale by Owner listings"},
            {"type_name": "Agent listed", "description": "Listed by real estate agent"},
            {"type_name": "New construction", "description": "New construction properties"},
            {"type_name": "Foreclosures", "description": "Foreclosed properties"},
            {"type_name": "Auctions", "description": "Auction properties"},
            {"type_name": "Foreclosed", "description": "Bank-owned foreclosed properties"},
            {"type_name": "Pre-foreclosures", "description": "Pre-foreclosure properties"}
        ]
        
        for lt_data in listing_types:
            existing = db.query(ListingType).filter(ListingType.type_name == lt_data["type_name"]).first()
            if not existing:
                listing_type = ListingType(**lt_data)
                db.add(listing_type)
        
        # Create default property status types
        status_types = [
            {"status_name": "Coming soon", "description": "Properties coming to market soon"},
            {"status_name": "Accepting backup offers", "description": "Accepting backup offers"},
            {"status_name": "Pending & under contract", "description": "Properties pending sale"}
        ]
        
        for st_data in status_types:
            existing = db.query(PropertyStatusType).filter(PropertyStatusType.status_name == st_data["status_name"]).first()
            if not existing:
                status_type = PropertyStatusType(**st_data)
                db.add(status_type)
        
        # Create default tour options
        tour_options = [
            {"tour_type": "Must have open house", "description": "Properties with scheduled open houses"},
            {"tour_type": "Must have 3D Tour", "description": "Properties with 3D virtual tours"},
            {"tour_type": "Must have Showcase", "description": "Properties with showcase presentations"}
        ]
        
        for to_data in tour_options:
            existing = db.query(TourOption).filter(TourOption.tour_type == to_data["tour_type"]).first()
            if not existing:
                tour_option = TourOption(**to_data)
                db.add(tour_option)
        
        # Create default views
        views = [
            {"view_type": "City", "description": "City skyline views"},
            {"view_type": "Mountain", "description": "Mountain and hill views"},
            {"view_type": "Park", "description": "Park and green space views"},
            {"view_type": "Water", "description": "Water and waterfront views"}
        ]
        
        for v_data in views:
            existing = db.query(View).filter(View.view_type == v_data["view_type"]).first()
            if not existing:
                view = View(**v_data)
                db.add(view)
        
        # Create default amenities
        amenities = [
            {"amenity_name": "Must have A/C", "category": "climate"},
            {"amenity_name": "Must have pool", "category": "outdoor"},
            {"amenity_name": "Waterfront", "category": "location"},
            {"amenity_name": "Garage", "category": "parking"},
            {"amenity_name": "Basement", "category": "structure"},
            {"amenity_name": "Modern Kitchen", "category": "kitchen"},
            {"amenity_name": "Updated Bathrooms", "category": "bathroom"},
            {"amenity_name": "Hardwood Floors", "category": "flooring"},
            {"amenity_name": "Fireplace", "category": "comfort"},
            {"amenity_name": "Balcony/Patio", "category": "outdoor"}
        ]
        
        for a_data in amenities:
            existing = db.query(Amenity).filter(Amenity.amenity_name == a_data["amenity_name"]).first()
            if not existing:
                amenity = Amenity(**a_data)
                db.add(amenity)
        
        # Create default admin user
        admin_email = "admin@realestate.com"
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        if not existing_admin:
            admin_user = AuthService.create_user(
                db=db,
                email=admin_email,
                password="admin123",  # Change this in production!
                first_name="Admin",
                last_name="User",
                role="admin"
            )
            print(f"Created admin user: {admin_email} (password: admin123)")
        
        db.commit()
        print("Default data created successfully!")
        
    except Exception as e:
        print(f"Error creating default data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def enable_uuid_extension():
    """Enable UUID extension in PostgreSQL."""
    print("Enabling UUID extension...")
    
    try:
        with engine.connect() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            conn.commit()
        print("UUID extension enabled successfully!")
    except Exception as e:
        print(f"Error enabling UUID extension: {e}")
        # This might fail if not using PostgreSQL, which is okay

def main():
    """Main initialization function."""
    print("Initializing Real Estate AI Engine Database...")
    
    try:
        # Enable UUID extension (PostgreSQL only)
        enable_uuid_extension()
        
        # Create all tables
        print("Creating database tables...")
        create_tables()
        print("Tables created successfully!")
        
        # Create default data
        create_default_data()
        
        print("\n✅ Database initialization completed successfully!")
        print("\nDefault admin credentials:")
        print("Email: admin@realestate.com")
        print("Password: admin123")
        print("\n⚠️  IMPORTANT: Change the admin password before deploying to production!")
        
    except Exception as e:
        print(f"\n❌ Database initialization failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 