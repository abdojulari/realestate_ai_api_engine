import spacy
import re
nlp = spacy.load("en_core_web_sm")

def extract_filters(text):
    doc = nlp(text)
    filters = {}
    if "bedroom" in text:
        for token in doc:
            if token.like_num and "bedroom" in token.head.text:
                filters['bedrooms'] = int(token.text)
    if "$" in text or "k" in text.lower():
        match = re.search(r'\$(\d+)[kK]?', text)
        if match:
            price = int(match.group(1))
            filters['price_max'] = price * 1000 if 'k' in text.lower() else price
    for t in ["duplex", "condo", "apartment"]:
        if t in text.lower():
            filters['property_type'] = t
    if "edmonton" in text.lower():
        filters['location'] = "Edmonton"
    return filters
