from embedder import generate_embedding
from numpy import dot
from numpy.linalg import norm

def cosine_sim(a, b):
    return dot(a, b) / (norm(a) * norm(b))

def rank_listings(listings, query_vec):
    for l in listings: 
        emb = generate_embedding(l['description'])
        l['score'] = cosine_sim(query_vec, emb)
    return sorted(listings, key=lambda x: x['score'], reverse=True)
