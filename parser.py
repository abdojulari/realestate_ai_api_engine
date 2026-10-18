import re

def extract_filters(text):
    filters = {}
    bedroom = re.search(r"(\d+)\s*bedroom", text, re.IGNORECASE)
    if bedroom:
        filters["bedrooms"] = int(bedroom.group(1))
    match = re.search(r"\$(\d+)[kK]?", text)
    if match:
        price = int(match.group(1))
        filters["price_max"] = price * 1000 if "k" in text.lower() else price
    for property_type in ["duplex", "condo", "apartment"]:
        if property_type in text.lower():
            filters["property_type"] = property_type
    if "edmonton" in text.lower():
        filters["location"] = "Edmonton"
    return filters
