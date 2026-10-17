#!/usr/bin/env python3
"""Insert fictional records so the API can be exercised locally.

Safe to run more than once. Existing seed rows are updated in place.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from db_models import (
    User,
    Office,
    AgentProfile,
    Property,
    PropertyImage,
    Listing,
    ClientAgentRelationship,
    Notification,
    PropertyInterest,
    SavedSearch,
    Neighbourhood,
    School,
    MarketInsight,
    Room,
    DailyTip,
    Lead,
    Amenity,
    View,
)
from auth import AuthService
from init_db import create_default_data

SEED_PASSWORD = "SeedPass123!"
SEED_CITY = "Seedville"
AGENT_KEY = "SEED-AGENT-001"
OFFICE_KEY = "SEED-OFFICE-001"
LISTING_KEYS = ("SEED-LISTING-001", "SEED-LISTING-002")


def upsert_user(db, email, role, first_name, last_name, phone):
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.role = role
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.is_active = True
        user.password_hash = AuthService.get_password_hash(SEED_PASSWORD)
        db.commit()
        db.refresh(user)
        return user
    return AuthService.create_user(
        db=db,
        email=email,
        password=SEED_PASSWORD,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=role,
    )


def seed():
    create_default_data()
    db = SessionLocal()
    try:
        admin = upsert_user(
            db, "seed.admin@example.com", "admin", "Seed", "Admin", "403-555-0100"
        )
        agent_user = upsert_user(
            db, "seed.agent@example.com", "agent", "Seed", "Agent", "403-555-0101"
        )
        customer = upsert_user(
            db, "seed.customer@example.com", "customer", "Seed", "Customer", "403-555-0102"
        )

        office = db.query(Office).filter(Office.crea_office_key == OFFICE_KEY).first()
        if not office:
            office = Office(crea_office_key=OFFICE_KEY)
            db.add(office)
        office.office_name = "Seed Realty"
        office.office_phone = "403-555-0199"
        office.office_email = "office@example.com"
        office.office_address = "1 Seed Plaza"
        office.office_city = SEED_CITY
        office.office_province = "Alberta"
        office.office_postal_code = "A1A 1A1"
        office.office_country = "Canada"
        office.office_status = "Active"
        db.flush()

        profile = db.query(AgentProfile).filter(AgentProfile.crea_agent_key == AGENT_KEY).first()
        if not profile:
            profile = AgentProfile(crea_agent_key=AGENT_KEY)
            db.add(profile)
        profile.user_id = agent_user.user_id
        profile.office_id = office.office_id
        profile.office_key = OFFICE_KEY
        profile.first_name = "Seed"
        profile.last_name = "Agent"
        profile.agent_email = "seed.agent@example.com"
        profile.agent_phone = "403-555-0101"
        profile.agency_name = "Seed Realty"
        profile.license_number = "SEED-LIC-001"
        profile.specialization = "Family homes"
        profile.experience = 8
        profile.bio = "Fictional agent used for local API checks."
        profile.rating = 4.8
        profile.total_sales = 12
        profile.active_listings = 2
        profile.member_status = "Active"
        profile.city = SEED_CITY
        profile.province = "Alberta"
        profile.is_accepting_clients = True
        profile.languages = ["English"]
        profile.service_areas = [SEED_CITY]
        db.flush()

        single_family = None
        from db_models import PropertyType

        single_family = (
            db.query(PropertyType).filter(PropertyType.type_name == "Single Family").first()
        )
        garage = db.query(Amenity).filter(Amenity.amenity_name == "Garage").first()
        city_view = db.query(View).filter(View.view_type == "City").first()

        properties = []
        specs = [
            {
                "listing_key": LISTING_KEYS[0],
                "title": "Seed Family Home",
                "address": "100 Seed Street",
                "price": 549000,
                "bedrooms": 3,
                "bathrooms": 2,
                "square_feet": 1680,
                "is_new": True,
            },
            {
                "listing_key": LISTING_KEYS[1],
                "title": "Seed Corner Condo",
                "address": "200 Seed Avenue",
                "price": 329000,
                "bedrooms": 2,
                "bathrooms": 1,
                "square_feet": 910,
                "is_new": False,
            },
        ]
        for spec in specs:
            prop = db.query(Property).filter(Property.listing_key == spec["listing_key"]).first()
            if not prop:
                prop = Property(listing_key=spec["listing_key"])
                db.add(prop)
            prop.title = spec["title"]
            prop.description = "Fictional listing created by seed_data.py."
            prop.address = spec["address"]
            prop.city = SEED_CITY
            prop.province = "Alberta"
            prop.postal_code = "A1A 1A1"
            prop.location_display = f"{spec['address']}, {SEED_CITY}"
            prop.latitude = 51.0447
            prop.longitude = -114.0719
            prop.price = spec["price"]
            prop.bedrooms = spec["bedrooms"]
            prop.bathrooms = spec["bathrooms"]
            prop.square_feet = spec["square_feet"]
            prop.year_built = 2016
            prop.parking_spots = 2
            prop.has_garage = True
            prop.status = "available"
            prop.is_new = spec["is_new"]
            prop.property_type_id = single_family.type_id if single_family else None
            prop.listing_agent_id = AGENT_KEY
            prop.listing_office_id = OFFICE_KEY
            prop.primary_image = "https://example.com/seed-home.jpg"
            prop.images = ["https://example.com/seed-home.jpg"]
            prop.days_on_market = 14
            db.flush()
            properties.append(prop)

        home = properties[0]
        if garage and garage not in home.amenities:
            home.amenities.append(garage)
        if city_view and city_view not in home.views:
            home.views.append(city_view)

        image = (
            db.query(PropertyImage)
            .filter(PropertyImage.property_id == home.property_id, PropertyImage.is_primary.is_(True))
            .first()
        )
        if not image:
            image = PropertyImage(property_id=home.property_id, is_primary=True)
            db.add(image)
        image.url = "https://example.com/seed-home.jpg"
        image.caption = "Seed listing photo"
        image.order_index = 0

        from db_models import ListingType, PropertyStatusType

        listing_type = db.query(ListingType).filter(ListingType.type_name == "Agent listed").first()
        status_type = (
            db.query(PropertyStatusType)
            .filter(PropertyStatusType.status_name == "Coming soon")
            .first()
        )
        listing = db.query(Listing).filter(Listing.mls_number == "SEED-MLS-001").first()
        if not listing:
            listing = Listing(mls_number="SEED-MLS-001")
            db.add(listing)
        listing.property_id = home.property_id
        listing.agent_id = agent_user.user_id
        listing.listing_type_id = listing_type.listing_type_id if listing_type else None
        listing.status_id = status_type.status_id if status_type else None

        relationship = (
            db.query(ClientAgentRelationship)
            .filter(
                ClientAgentRelationship.client_id == customer.user_id,
                ClientAgentRelationship.agent_id == agent_user.user_id,
            )
            .first()
        )
        if not relationship:
            relationship = ClientAgentRelationship(
                client_id=customer.user_id,
                agent_id=agent_user.user_id,
            )
            db.add(relationship)
        relationship.status = "active"
        relationship.requested_by = "client"
        relationship.property_id = home.property_id
        relationship.notes = "Seed relationship for API checks."

        interest = (
            db.query(PropertyInterest)
            .filter(
                PropertyInterest.user_id == customer.user_id,
                PropertyInterest.property_id == home.property_id,
            )
            .first()
        )
        if not interest:
            interest = PropertyInterest(user_id=customer.user_id, property_id=home.property_id)
            db.add(interest)
        interest.agent_id = agent_user.user_id
        interest.interest_level = "very_interested"
        interest.status = "active"
        interest.notes = "Seed interest."

        search = (
            db.query(SavedSearch)
            .filter(SavedSearch.user_id == customer.user_id, SavedSearch.search_name == "Seedville homes")
            .first()
        )
        if not search:
            search = SavedSearch(user_id=customer.user_id, search_name="Seedville homes")
            db.add(search)
        search.city = SEED_CITY
        search.province = "Alberta"
        search.budget_min = 300000
        search.budget_max = 600000
        search.bedrooms_min = 2

        note = (
            db.query(Notification)
            .filter(Notification.user_id == customer.user_id, Notification.title == "Seed notification")
            .first()
        )
        if not note:
            note = Notification(user_id=customer.user_id, title="Seed notification")
            db.add(note)
        note.type = "property_interest"
        note.message = "A fictional notification created by seed_data.py."
        note.is_read = False
        note.data = {"listing_key": home.listing_key}

        neighbourhood = (
            db.query(Neighbourhood)
            .filter(Neighbourhood.property_id == home.property_id, Neighbourhood.name == "Seed Park")
            .first()
        )
        if not neighbourhood:
            neighbourhood = Neighbourhood(property_id=home.property_id, name="Seed Park")
            db.add(neighbourhood)
        neighbourhood.type = "Parks"
        neighbourhood.address = "10 Seed Park Road"
        neighbourhood.distance = 0.4
        neighbourhood.walking_time = 6
        neighbourhood.lat = 51.0460
        neighbourhood.lng = -114.0700

        school = (
            db.query(School)
            .filter(School.property_id == home.property_id, School.name == "Seed Elementary")
            .first()
        )
        if not school:
            school = School(property_id=home.property_id, name="Seed Elementary")
            db.add(school)
        school.type = "Elementary"
        school.grades = "K-6"
        school.distance = 0.8
        school.address = "20 Seed School Lane"
        school.school_board = "Seed Board"
        school.score = 8.2
        school.is_assigned = True
        school.postal_code = "A1A 1A1"
        school.lat = 51.0480
        school.lng = -114.0740

        insight = db.query(MarketInsight).filter(MarketInsight.property_id == home.property_id).first()
        if not insight:
            insight = MarketInsight(property_id=home.property_id, postal_code="A1A 1A1")
            db.add(insight)
        insight.postal_code = "A1A 1A1"
        insight.price_per_sqft = 327
        insight.style = "Detached"
        insight.time_on_platform = "14 days"
        insight.market_value = 540000
        insight.market_stats = {"median_price": 525000, "inventory": 18}
        insight.economic_indicators = {"rate": 4.5}

        room = (
            db.query(Room)
            .filter(Room.property_id == home.property_id, Room.room_type == "Primary Bedroom")
            .first()
        )
        if not room:
            room = Room(property_id=home.property_id, room_type="Primary Bedroom")
            db.add(room)
        room.room_level = "Main"
        room.room_dimensions = "12 x 14"
        room.room_description = "Seed room."

        tip = db.query(DailyTip).filter(DailyTip.title == "Seed tip: compare recent sales").first()
        if not tip:
            tip = DailyTip(title="Seed tip: compare recent sales", created_by=admin.user_id)
            db.add(tip)
        tip.tip = "Look at a few recent sales nearby before you write an offer."
        tip.is_active = True
        tip.display_order = 0
        tip.created_by = admin.user_id
        tip.images = []

        lead = (
            db.query(Lead)
            .filter(Lead.listing_key == home.listing_key, Lead.sender_email_address == "seed.customer@example.com")
            .first()
        )
        if not lead:
            lead = Lead(
                agent_profile_id=profile.profile_id,
                crea_agent_key=AGENT_KEY,
                listing_key=home.listing_key,
                sender_name="Seed Customer",
                sender_email_address="seed.customer@example.com",
                message="Fictional lead created by seed_data.py.",
            )
            db.add(lead)
        lead.agent_profile_id = profile.profile_id
        lead.crea_agent_key = AGENT_KEY
        lead.office_key = OFFICE_KEY
        lead.sender_name = "Seed Customer"
        lead.sender_phone_number = "403-555-0102"
        lead.preferred_method_contact = "email"
        lead.message = "Fictional lead created by seed_data.py."
        lead.lead_status = "new"
        lead.lead_source = "seed"
        lead.lead_priority = "medium"
        lead.budget_min = 300000
        lead.budget_max = 600000
        lead.desired_location = SEED_CITY

        db.commit()
        print("Seed data ready.")
        print(f"Password for every seed account: {SEED_PASSWORD}")
        print("seed.admin@example.com")
        print("seed.agent@example.com")
        print("seed.customer@example.com")
        print(f"Properties in {SEED_CITY}: {', '.join(LISTING_KEYS)}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
