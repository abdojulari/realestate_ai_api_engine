from apscheduler.schedulers.background import BackgroundScheduler
from emailer import send_property_email
from connector_mock import search_properties
from matcher import rank_listings
from embedder import generate_embedding
from parser import extract_filters

scheduler = BackgroundScheduler()
scheduler.start()

def user_job(email, prompt):
    filters = extract_filters(prompt)
    embedding = generate_embedding(prompt)
    listings = search_properties(filters)
    ranked = rank_listings(listings, embedding)
    send_property_email(email, ranked[:5])

def schedule_user_task(prompt):
    email = prompt.email
    interval = prompt.frequency or 12
    job_id = f"job_{email}"
    scheduler.add_job(user_job, 'interval', hours=interval, id=job_id, replace_existing=True, args=[email, prompt.prompt])
