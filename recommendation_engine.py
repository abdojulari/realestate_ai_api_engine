"""
Real Estate Property Recommendation Engine

This module implements a machine learning-based recommendation system for real estate properties.
It combines multiple approaches:
1. Content-based filtering (property features)
2. Collaborative filtering (user behavior patterns)
3. Semantic similarity (natural language processing)
4. Market trend analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import pickle
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PropertyFeatures:
    """Structured property features for recommendation"""
    property_id: str
    price: float
    bedrooms: int
    bathrooms: float
    square_feet: Optional[int]
    property_type: str
    location: str
    age_years: Optional[int]
    garage_spaces: Optional[int]
    description: str
    amenities: List[str]
    neighborhood_score: Optional[float]
    price_per_sqft: Optional[float]

@dataclass
class UserPreferences:
    """User preference profile for recommendations"""
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    preferred_bedrooms: Optional[int] = None
    preferred_bathrooms: Optional[float] = None
    min_sqft: Optional[int] = None
    max_sqft: Optional[int] = None
    preferred_types: List[str] = field(default_factory=list)
    preferred_locations: List[str] = field(default_factory=list)
    must_have_amenities: List[str] = field(default_factory=list)
    preferred_age: Optional[str] = None  # 'new', 'modern', 'classic', 'any'
    garage_required: bool = False
    max_commute_distance: Optional[float] = None
    lifestyle_keywords: List[str] = field(default_factory=list)

@dataclass
class RecommendationScore:
    """Recommendation result with detailed scoring"""
    property_id: str
    overall_score: float
    content_score: float
    semantic_score: float
    price_score: float
    location_score: float
    amenity_score: float
    explanation: List[str]
    
    def __post_init__(self):
        """Convert numpy types to Python native types for JSON serialization"""
        # Convert all float scores to Python float (not numpy.float32)
        self.overall_score = float(self.overall_score)
        self.content_score = float(self.content_score)
        self.semantic_score = float(self.semantic_score)
        self.price_score = float(self.price_score)
        self.location_score = float(self.location_score)
        self.amenity_score = float(self.amenity_score)

class PropertyRecommendationEngine:
    """
    Advanced property recommendation engine using multiple ML approaches
    """
    
    def __init__(self, model_cache_dir: str = "models/recommendation_cache"):
        self.model_cache_dir = model_cache_dir
        os.makedirs(model_cache_dir, exist_ok=True)
        
        # Initialize models
        self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        self.scaler = StandardScaler()
        self.location_encoder = LabelEncoder()
        self.type_encoder = LabelEncoder()
        
        # Property data and features
        self.properties_df = None
        self.property_features = {}
        self.property_embeddings = None
        self.feature_matrix = None
        
        # User interaction tracking
        self.user_interactions = {}
        self.property_clusters = None
        
        # Model state
        self.is_trained = False
        
    def load_properties(self, properties_data: List[Dict]) -> None:
        """Load and preprocess property data"""
        logger.info(f"Loading {len(properties_data)} properties")
        
        # Convert to DataFrame for easier manipulation
        self.properties_df = pd.DataFrame(properties_data)
        
        # Extract and standardize features
        self._extract_features()
        self._compute_property_embeddings()
        self._build_feature_matrix()
        self._cluster_properties()
        
        self.is_trained = True
        logger.info("Property recommendation engine trained successfully")
    
    def _extract_features(self) -> None:
        """Extract and normalize property features"""
        logger.info("Extracting property features")
        
        for _, prop in self.properties_df.iterrows():
            # Calculate derived features
            price_per_sqft = None
            if prop.get('square_feet') and prop.get('square_feet') > 0:
                price_per_sqft = prop['price'] / prop['square_feet']
            
            # Estimate property age if not provided
            age_years = prop.get('age_years')
            if not age_years and prop.get('year_built'):
                age_years = datetime.now().year - prop['year_built']
            
            # Parse amenities
            amenities = prop.get('amenities', [])
            if isinstance(amenities, str):
                amenities = amenities.split(',') if amenities else []
            amenities = [a.strip().lower() for a in amenities]
            
            features = PropertyFeatures(
                property_id=str(prop['id']),
                price=float(prop['price']),
                bedrooms=int(prop.get('bedrooms', 0)),
                bathrooms=float(prop.get('bathrooms', 0)),
                square_feet=prop.get('square_feet'),
                property_type=prop.get('type', 'unknown').lower(),
                location=prop.get('location', 'unknown').lower(),
                age_years=age_years,
                garage_spaces=prop.get('garage_spaces'),
                description=prop.get('description', ''),
                amenities=amenities,
                neighborhood_score=prop.get('neighborhood_score'),
                price_per_sqft=price_per_sqft
            )
            
            self.property_features[features.property_id] = features
    
    def _compute_property_embeddings(self) -> None:
        """Generate semantic embeddings for property descriptions"""
        logger.info("Computing property embeddings")
        
        descriptions = []
        property_ids = []
        
        for prop_id, features in self.property_features.items():
            # Combine description with key features for better embedding
            text = f"{features.description} {features.property_type} {features.location}"
            if features.amenities:
                text += f" amenities: {' '.join(features.amenities)}"
            
            descriptions.append(text)
            property_ids.append(prop_id)
        
        self.property_embeddings = self.sentence_model.encode(descriptions)
        self.property_embedding_ids = property_ids
    
    def _build_feature_matrix(self) -> None:
        """Build numerical feature matrix for similarity calculations"""
        logger.info("Building feature matrix")
        
        features_list = []
        feature_names = []
        
        for prop_id in self.property_features:
            features = self.property_features[prop_id]
            
            # Numerical features
            feature_vector = [
                features.price,
                features.bedrooms,
                features.bathrooms,
                features.square_feet or 0,
                features.age_years or 10,  # Default to 10 years if unknown
                features.garage_spaces or 0,
                features.price_per_sqft or (features.price / 1000),  # Rough estimate
                features.neighborhood_score or 0.5,
                len(features.amenities)
            ]
            
            features_list.append(feature_vector)
        
        self.feature_matrix = np.array(features_list)
        self.feature_matrix_scaled = self.scaler.fit_transform(self.feature_matrix)
        
        self.feature_names = [
            'price', 'bedrooms', 'bathrooms', 'square_feet', 'age_years',
            'garage_spaces', 'price_per_sqft', 'neighborhood_score', 'amenity_count'
        ]
    
    def _cluster_properties(self, n_clusters: int = 8) -> None:
        """Cluster properties for collaborative filtering"""
        num_properties = len(self.property_features)
        
        # Adjust cluster count based on available properties
        n_clusters = min(n_clusters, max(2, num_properties // 2))
        logger.info(f"Clustering {num_properties} properties into {n_clusters} groups")
        
        # Use both feature matrix and embeddings for clustering
        combined_features = np.hstack([
            self.feature_matrix_scaled,
            self.property_embeddings
        ])
        
        self.property_clusters = KMeans(n_clusters=n_clusters, random_state=42)
        cluster_labels = self.property_clusters.fit_predict(combined_features)
        
        # Store cluster labels with property IDs
        self.property_cluster_map = {}
        for i, prop_id in enumerate(self.property_features.keys()):
            self.property_cluster_map[prop_id] = cluster_labels[i]
    
    def recommend_properties(
        self,
        user_preferences: UserPreferences,
        user_id: Optional[str] = None,
        top_k: int = 10,
        explain: bool = True
    ) -> List[RecommendationScore]:
        """
        Generate property recommendations for a user
        
        Args:
            user_preferences: User's search criteria and preferences
            user_id: Optional user ID for personalization
            top_k: Number of recommendations to return
            explain: Whether to include explanation for recommendations
            
        Returns:
            List of recommendations with scores and explanations
        """
        if not self.is_trained:
            raise ValueError("Model not trained. Call load_properties() first.")
        
        logger.info(f"Generating recommendations for user preferences")
        
        recommendations = []
        
        for prop_id, features in self.property_features.items():
            score = self._calculate_property_score(features, user_preferences, explain)
            recommendations.append(score)
        
        # Sort by overall score and return top K
        recommendations.sort(key=lambda x: x.overall_score, reverse=True)
        return recommendations[:top_k]
    
    def _calculate_property_score(
        self,
        property_features: PropertyFeatures,
        user_preferences: UserPreferences,
        explain: bool = True
    ) -> RecommendationScore:
        """Calculate comprehensive recommendation score for a property"""
        
        explanations = []
        
        # 1. Content-based scoring (property features match)
        content_score = self._content_based_score(property_features, user_preferences, explanations)
        
        # 2. Price scoring
        price_score = self._price_score(property_features, user_preferences, explanations)
        
        # 3. Location scoring
        location_score = self._location_score(property_features, user_preferences, explanations)
        
        # 4. Amenity scoring
        amenity_score = self._amenity_score(property_features, user_preferences, explanations)
        
        # 5. Semantic similarity scoring
        semantic_score = self._semantic_score(property_features, user_preferences, explanations)
        
        # Weighted combination of scores
        weights = {
            'content': 0.25,
            'price': 0.25,
            'location': 0.20,
            'amenity': 0.15,
            'semantic': 0.15
        }
        
        overall_score = (
            weights['content'] * content_score +
            weights['price'] * price_score +
            weights['location'] * location_score +
            weights['amenity'] * amenity_score +
            weights['semantic'] * semantic_score
        )
        
        return RecommendationScore(
            property_id=property_features.property_id,
            overall_score=overall_score,
            content_score=content_score,
            semantic_score=semantic_score,
            price_score=price_score,
            location_score=location_score,
            amenity_score=amenity_score,
            explanation=explanations if explain else []
        )
    
    def _content_based_score(
        self,
        prop: PropertyFeatures,
        prefs: UserPreferences,
        explanations: List[str]
    ) -> float:
        """Score based on property features matching user preferences"""
        score = 0.0
        max_score = 0.0
        
        # Bedroom preference
        if prefs.preferred_bedrooms is not None:
            max_score += 1.0
            if prop.bedrooms == prefs.preferred_bedrooms:
                score += 1.0
                explanations.append(f"Exact bedroom match ({prop.bedrooms} bedrooms)")
            elif abs(prop.bedrooms - prefs.preferred_bedrooms) <= 1:
                score += 0.7
                explanations.append(f"Close bedroom match ({prop.bedrooms} vs {prefs.preferred_bedrooms} preferred)")
            elif abs(prop.bedrooms - prefs.preferred_bedrooms) <= 2:
                score += 0.3
        
        # Bathroom preference
        if prefs.preferred_bathrooms is not None:
            max_score += 1.0
            diff = abs(prop.bathrooms - prefs.preferred_bathrooms)
            if diff == 0:
                score += 1.0
                explanations.append(f"Exact bathroom match ({prop.bathrooms} bathrooms)")
            elif diff <= 0.5:
                score += 0.8
            elif diff <= 1.0:
                score += 0.5
        
        # Property type preference
        if prefs.preferred_types:
            max_score += 1.0
            if prop.property_type in [t.lower() for t in prefs.preferred_types]:
                score += 1.0
                explanations.append(f"Preferred property type ({prop.property_type})")
        
        # Square footage preference
        if prefs.min_sqft or prefs.max_sqft:
            if prop.square_feet:
                max_score += 1.0
                within_range = True
                if prefs.min_sqft and prop.square_feet < prefs.min_sqft:
                    within_range = False
                if prefs.max_sqft and prop.square_feet > prefs.max_sqft:
                    within_range = False
                
                if within_range:
                    score += 1.0
                    explanations.append(f"Within size preference ({prop.square_feet} sq ft)")
        
        # Garage requirement
        if prefs.garage_required:
            max_score += 1.0
            if prop.garage_spaces and prop.garage_spaces > 0:
                score += 1.0
                explanations.append(f"Has required garage ({prop.garage_spaces} spaces)")
        
        return score / max_score if max_score > 0 else 0.5
    
    def _price_score(
        self,
        prop: PropertyFeatures,
        prefs: UserPreferences,
        explanations: List[str]
    ) -> float:
        """Score based on price preferences"""
        if not prefs.max_price and not prefs.min_price:
            return 0.5  # Neutral if no price preference
        
        score = 1.0
        
        if prefs.max_price and prop.price > prefs.max_price:
            # Price too high - penalize based on how much over
            overage_ratio = (prop.price - prefs.max_price) / prefs.max_price
            score = max(0, 1.0 - overage_ratio)
            if score < 0.5:
                explanations.append(f"Over budget by ${prop.price - prefs.max_price:,.0f}")
        elif prefs.max_price:
            explanations.append(f"Within budget (${prop.price:,.0f} vs ${prefs.max_price:,.0f} max)")
        
        if prefs.min_price and prop.price < prefs.min_price:
            # Price too low might indicate quality concerns
            score *= 0.8
        
        return score
    
    def _location_score(
        self,
        prop: PropertyFeatures,
        prefs: UserPreferences,
        explanations: List[str]
    ) -> float:
        """Score based on location preferences"""
        if not prefs.preferred_locations:
            return 0.5  # Neutral if no location preference
        
        preferred_locations_lower = [loc.lower() for loc in prefs.preferred_locations]
        
        if prop.location in preferred_locations_lower:
            explanations.append(f"In preferred location ({prop.location})")
            return 1.0
        
        # Check for partial matches
        for pref_loc in preferred_locations_lower:
            if pref_loc in prop.location or prop.location in pref_loc:
                explanations.append(f"Near preferred location ({prop.location})")
                return 0.7
        
        return 0.2  # Not in preferred area
    
    def _amenity_score(
        self,
        prop: PropertyFeatures,
        prefs: UserPreferences,
        explanations: List[str]
    ) -> float:
        """Score based on amenity preferences"""
        if not prefs.must_have_amenities:
            return 0.5  # Neutral if no amenity requirements
        
        required_amenities = [a.lower() for a in prefs.must_have_amenities]
        property_amenities = [a.lower() for a in prop.amenities]
        
        matches = 0
        for req_amenity in required_amenities:
            for prop_amenity in property_amenities:
                if req_amenity in prop_amenity or prop_amenity in req_amenity:
                    matches += 1
                    explanations.append(f"Has {req_amenity}")
                    break
        
        return matches / len(required_amenities) if required_amenities else 0.5
    
    def _semantic_score(
        self,
        prop: PropertyFeatures,
        prefs: UserPreferences,
        explanations: List[str]
    ) -> float:
        """Score based on semantic similarity with lifestyle keywords"""
        if not prefs.lifestyle_keywords:
            return 0.5
        
        # Create user preference text
        pref_text = " ".join(prefs.lifestyle_keywords)
        
        # Get property text
        prop_text = f"{prop.description} {prop.property_type} {' '.join(prop.amenities)}"
        
        # Calculate semantic similarity
        pref_embedding = self.sentence_model.encode([pref_text])
        prop_embedding = self.sentence_model.encode([prop_text])
        
        similarity = cosine_similarity(pref_embedding, prop_embedding)[0][0]
        
        if similarity > 0.7:
            explanations.append("Strong lifestyle match")
        elif similarity > 0.5:
            explanations.append("Good lifestyle fit")
        
        return max(0, similarity)
    
    def get_similar_properties(
        self,
        property_id: str,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """Find properties similar to the given property"""
        if not self.is_trained:
            raise ValueError("Model not trained")
        
        if property_id not in self.property_features:
            raise ValueError(f"Property {property_id} not found")
        
        # Get property index
        prop_ids = list(self.property_features.keys())
        prop_index = prop_ids.index(property_id)
        
        # Calculate similarities using both features and embeddings
        feature_similarities = cosine_similarity(
            [self.feature_matrix_scaled[prop_index]], 
            self.feature_matrix_scaled
        )[0]
        
        semantic_similarities = cosine_similarity(
            [self.property_embeddings[prop_index]], 
            self.property_embeddings
        )[0]
        
        # Combine similarities
        combined_similarities = 0.6 * feature_similarities + 0.4 * semantic_similarities
        
        # Get top K similar properties (excluding the property itself)
        similar_indices = np.argsort(combined_similarities)[::-1][1:top_k+1]
        
        return [(prop_ids[i], combined_similarities[i]) for i in similar_indices]
    
    def save_model(self, filepath: str) -> None:
        """Save the trained model to disk"""
        model_data = {
            'property_features': self.property_features,
            'property_embeddings': self.property_embeddings,
            'feature_matrix': self.feature_matrix,
            'feature_matrix_scaled': self.feature_matrix_scaled,
            'property_cluster_map': self.property_cluster_map,
            'is_trained': self.is_trained
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str) -> None:
        """Load a pre-trained model from disk"""
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.property_features = model_data['property_features']
        self.property_embeddings = model_data['property_embeddings']
        self.feature_matrix = model_data['feature_matrix']
        self.feature_matrix_scaled = model_data['feature_matrix_scaled']
        self.property_cluster_map = model_data['property_cluster_map']
        self.is_trained = model_data['is_trained']
        
        logger.info(f"Model loaded from {filepath}")


def create_sample_data() -> List[Dict]:
    """Create expanded sample property data for testing"""
    return [
        {
            "id": 1, "title": "Modern Downtown Condo", "price": 450000, "bedrooms": 2, "bathrooms": 2.0,
            "square_feet": 1200, "type": "condo", "location": "downtown edmonton", "year_built": 2018,
            "description": "Luxury condo with city views, hardwood floors, stainless appliances",
            "amenities": ["gym", "concierge", "parking", "balcony"], "garage_spaces": 1,
            "neighborhood_score": 0.9
        },
        {
            "id": 2, "title": "Family Home in Suburbs", "price": 580000, "bedrooms": 4, "bathrooms": 3.0,
            "square_feet": 2400, "type": "house", "location": "south edmonton", "year_built": 2010,
            "description": "Spacious family home with large yard, updated kitchen, finished basement",
            "amenities": ["yard", "garage", "basement", "deck"], "garage_spaces": 2,
            "neighborhood_score": 0.8
        },
        {
            "id": 3, "title": "Cozy Townhouse", "price": 320000, "bedrooms": 3, "bathrooms": 2.5,
            "square_feet": 1800, "type": "townhouse", "location": "west edmonton", "year_built": 2015,
            "description": "Well-maintained townhouse in quiet community, perfect for young families",
            "amenities": ["patio", "parking", "storage"], "garage_spaces": 1,
            "neighborhood_score": 0.7
        },
        {
            "id": 4, "title": "Luxury Penthouse", "price": 850000, "bedrooms": 3, "bathrooms": 3.0,
            "square_feet": 2200, "type": "condo", "location": "downtown edmonton", "year_built": 2020,
            "description": "Stunning penthouse with panoramic views, premium finishes, rooftop access",
            "amenities": ["rooftop", "concierge", "gym", "parking", "balcony"], "garage_spaces": 2,
            "neighborhood_score": 0.95
        },
        {
            "id": 5, "title": "Starter Home", "price": 275000, "bedrooms": 2, "bathrooms": 1.0,
            "square_feet": 900, "type": "house", "location": "north edmonton", "year_built": 1985,
            "description": "Affordable starter home with potential for renovation, good neighborhood",
            "amenities": ["yard", "shed"], "garage_spaces": 0,
            "neighborhood_score": 0.6
        }
    ]


# Usage example
if __name__ == "__main__":
    # Initialize recommendation engine
    engine = PropertyRecommendationEngine()
    
    # Load sample data
    sample_properties = create_sample_data()
    engine.load_properties(sample_properties)
    
    # Create user preferences
    user_prefs = UserPreferences(
        max_price=500000,
        preferred_bedrooms=3,
        preferred_bathrooms=2.0,
        preferred_types=["house", "townhouse"],
        preferred_locations=["south edmonton", "west edmonton"],
        must_have_amenities=["garage", "yard"],
        lifestyle_keywords=["family", "quiet", "spacious"]
    )
    
    # Get recommendations
    recommendations = engine.recommend_properties(user_prefs, top_k=3)
    
    # Print results
    for rec in recommendations:
        print(f"Property {rec.property_id}: Score {rec.overall_score:.3f}")
        print(f"  Explanations: {', '.join(rec.explanation)}")
        print()
