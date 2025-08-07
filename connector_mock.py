mock_data = [
    {"id": 1, "title": "3-bed Duplex in South Edmonton", "description": "Spacious duplex with garage.", "price": 580000, "bedrooms": 3, "type": "duplex", "location": "South Edmonton"},
    {"id": 2, "title": "2-bed Condo Downtown", "description": "Modern condo with skyline view.", "price": 420000, "bedrooms": 2, "type": "condo", "location": "Downtown Edmonton"},
]

def search_properties(filters):
    results = []
    for p in mock_data:
        if 'price_max' in filters and p['price'] > filters['price_max']:
            continue
        if 'bedrooms' in filters and p['bedrooms'] < filters['bedrooms']:
            continue
        if 'property_type' in filters and filters['property_type'] not in p['type']:
            continue
        if 'location' in filters and filters['location'].lower() not in p['location'].lower():
            continue
        results.append(p)
    return results
