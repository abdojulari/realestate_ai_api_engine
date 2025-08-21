"""
Model Management System for Real Estate Recommendation Engine

This module handles model persistence, caching, and production deployment
of the recommendation engine across different environments.
"""

import os
import json
import logging
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import threading
from contextlib import contextmanager

from recommendation_engine import PropertyRecommendationEngine, create_sample_data
from database import SessionLocal
from db_models import Property

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelManager:
    """
    Manages recommendation model lifecycle, caching, and environment-specific deployment
    """
    
    def __init__(self, 
                 environment: str = "development",
                 model_cache_dir: str = "models",
                 auto_retrain_hours: int = 24):
        """
        Initialize model manager
        
        Args:
            environment: 'development', 'staging', or 'production'
            model_cache_dir: Directory to store model files
            auto_retrain_hours: Hours between automatic model retraining
        """
        self.environment = environment
        self.model_cache_dir = Path(model_cache_dir)
        self.auto_retrain_hours = auto_retrain_hours
        
        # Create directories
        self.model_cache_dir.mkdir(exist_ok=True)
        (self.model_cache_dir / "backups").mkdir(exist_ok=True)
        
        # Model state
        self.recommendation_engine = None
        self.model_metadata = {}
        self.last_trained = None
        self.is_loading = False
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Environment-specific settings
        self._configure_environment()
        
        logger.info(f"ModelManager initialized for {environment} environment")
    
    def _configure_environment(self):
        """Configure settings based on environment"""
        if self.environment == "development":
            self.model_file = self.model_cache_dir / "recommendation_model_dev.pkl"
            self.metadata_file = self.model_cache_dir / "model_metadata_dev.json"
            self.use_sample_data = True
            self.cache_ttl_hours = 1  # Shorter cache for dev
            
        elif self.environment == "staging":
            self.model_file = self.model_cache_dir / "recommendation_model_staging.pkl"
            self.metadata_file = self.model_cache_dir / "model_metadata_staging.json"
            self.use_sample_data = False
            self.cache_ttl_hours = 6
            
        elif self.environment == "production":
            self.model_file = self.model_cache_dir / "recommendation_model_prod.pkl"
            self.metadata_file = self.model_cache_dir / "model_metadata_prod.json"
            self.use_sample_data = False
            self.cache_ttl_hours = 12
            
        else:
            raise ValueError(f"Invalid environment: {self.environment}")
    
    @contextmanager
    def get_db_session(self):
        """Get database session with proper cleanup"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def load_model(self, force_retrain: bool = False) -> PropertyRecommendationEngine:
        """
        Load or create recommendation model
        
        Args:
            force_retrain: Force model retraining even if cached model exists
            
        Returns:
            Trained PropertyRecommendationEngine instance
        """
        with self._lock:
            if self.recommendation_engine and not force_retrain and not self._needs_retraining():
                logger.info("Using cached recommendation model")
                return self.recommendation_engine
            
            self.is_loading = True
            try:
                # Try to load existing model
                if not force_retrain and self.model_file.exists() and not self._needs_retraining():
                    logger.info(f"Loading model from {self.model_file}")
                    self.recommendation_engine = self._load_from_disk()
                    self._load_metadata()
                else:
                    logger.info("Training new recommendation model")
                    self.recommendation_engine = self._train_new_model()
                    self._save_model()
                    self._save_metadata()
                
                self.last_trained = datetime.now()
                return self.recommendation_engine
                
            finally:
                self.is_loading = False
    
    def _needs_retraining(self) -> bool:
        """Check if model needs retraining based on age and data changes"""
        if not self.model_file.exists():
            return True
        
        # Check model age
        model_age = datetime.now() - datetime.fromtimestamp(self.model_file.stat().st_mtime)
        if model_age > timedelta(hours=self.auto_retrain_hours):
            logger.info(f"Model is {model_age} old, needs retraining")
            return True
        
        # In production, also check for data changes
        if self.environment == "production":
            return self._check_data_changes()
        
        return False
    
    def _check_data_changes(self) -> bool:
        """Check if property data has changed since last training"""
        try:
            with self.get_db_session() as db:
                # Get latest property update time
                latest_property = db.query(Property).order_by(Property.updated_at.desc()).first()
                if not latest_property:
                    return False
                
                # Compare with model training time
                if self.last_trained and latest_property.updated_at > self.last_trained:
                    logger.info("Property data has been updated since last training")
                    return True
                    
        except Exception as e:
            logger.warning(f"Could not check data changes: {e}")
            
        return False
    
    def _train_new_model(self) -> PropertyRecommendationEngine:
        """Train a new recommendation model"""
        engine = PropertyRecommendationEngine()
        
        if self.use_sample_data:
            # Use sample data for development
            logger.info("Training model with sample data")
            properties_data = create_sample_data()
        else:
            # Load real data from database
            logger.info("Loading property data from database")
            properties_data = self._load_property_data_from_db()
        
        if not properties_data:
            logger.warning("No property data available, using sample data")
            properties_data = create_sample_data()
        
        engine.load_properties(properties_data)
        
        # Store training metadata
        self.model_metadata = {
            "environment": self.environment,
            "training_time": datetime.now().isoformat(),
            "property_count": len(properties_data),
            "model_version": "1.0.0",
            "features": ["content_filtering", "semantic_similarity", "clustering"]
        }
        
        logger.info(f"Model trained successfully with {len(properties_data)} properties")
        return engine
    
    def _load_property_data_from_db(self) -> List[Dict]:
        """Load property data from database"""
        properties_data = []
        
        try:
            with self.get_db_session() as db:
                properties = db.query(Property).filter(Property.is_active == True).all()
                
                for prop in properties:
                    # Convert database model to dictionary format
                    prop_dict = {
                        "id": prop.id,
                        "title": prop.title or f"{prop.bedrooms}BR {prop.property_type}",
                        "price": float(prop.price) if prop.price else 0,
                        "bedrooms": prop.bedrooms or 0,
                        "bathrooms": float(prop.bathrooms) if prop.bathrooms else 0,
                        "square_feet": prop.square_feet,
                        "type": prop.property_type or "unknown",
                        "location": f"{prop.city}, {prop.province}" if prop.city and prop.province else "unknown",
                        "year_built": prop.year_built,
                        "description": prop.description or "",
                        "amenities": prop.amenities.split(",") if prop.amenities else [],
                        "garage_spaces": prop.garage_spaces,
                        "neighborhood_score": 0.7  # Could be calculated based on area data
                    }
                    properties_data.append(prop_dict)
                
                logger.info(f"Loaded {len(properties_data)} properties from database")
                
        except Exception as e:
            logger.error(f"Error loading properties from database: {e}")
            
        return properties_data
    
    def _load_from_disk(self) -> PropertyRecommendationEngine:
        """Load model from disk"""
        engine = PropertyRecommendationEngine()
        engine.load_model(str(self.model_file))
        return engine
    
    def _save_model(self):
        """Save model to disk with backup"""
        if self.recommendation_engine:
            # Create backup if existing model exists
            if self.model_file.exists():
                backup_file = self.model_cache_dir / "backups" / f"model_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
                self.model_file.rename(backup_file)
                logger.info(f"Created model backup: {backup_file}")
            
            # Save new model
            self.recommendation_engine.save_model(str(self.model_file))
            logger.info(f"Model saved to {self.model_file}")
    
    def _save_metadata(self):
        """Save model metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.model_metadata, f, indent=2)
        logger.info(f"Metadata saved to {self.metadata_file}")
    
    def _load_metadata(self):
        """Load model metadata"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                self.model_metadata = json.load(f)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get model information and status"""
        return {
            "environment": self.environment,
            "model_loaded": self.recommendation_engine is not None,
            "is_loading": self.is_loading,
            "last_trained": self.last_trained.isoformat() if self.last_trained else None,
            "model_file_exists": self.model_file.exists(),
            "model_metadata": self.model_metadata,
            "cache_ttl_hours": self.cache_ttl_hours,
            "auto_retrain_hours": self.auto_retrain_hours
        }
    
    def force_retrain(self) -> bool:
        """Force model retraining"""
        try:
            logger.info("Forcing model retraining")
            self.load_model(force_retrain=True)
            return True
        except Exception as e:
            logger.error(f"Error during forced retraining: {e}")
            return False
    
    def cleanup_old_backups(self, keep_backups: int = 5):
        """Clean up old model backups"""
        backup_dir = self.model_cache_dir / "backups"
        if not backup_dir.exists():
            return
        
        # Get all backup files sorted by modification time
        backup_files = sorted(
            backup_dir.glob("model_backup_*.pkl"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Remove old backups
        for backup_file in backup_files[keep_backups:]:
            backup_file.unlink()
            logger.info(f"Removed old backup: {backup_file}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the model"""
        status = {
            "healthy": True,
            "issues": [],
            "recommendations": []
        }
        
        # Check if model is loaded
        if not self.recommendation_engine:
            status["healthy"] = False
            status["issues"].append("Model not loaded")
            status["recommendations"].append("Call load_model()")
        
        # Check model age
        if self.model_file.exists():
            model_age = datetime.now() - datetime.fromtimestamp(self.model_file.stat().st_mtime)
            if model_age > timedelta(hours=self.auto_retrain_hours * 2):
                status["issues"].append(f"Model is very old ({model_age})")
                status["recommendations"].append("Consider retraining model")
        
        # Check if model is currently training
        if self.is_loading:
            status["recommendations"].append("Model is currently being loaded/trained")
        
        return status


# Global model manager instance
_model_manager = None

def get_model_manager(environment: str = "development") -> ModelManager:
    """Get global model manager instance"""
    global _model_manager
    
    if _model_manager is None or _model_manager.environment != environment:
        _model_manager = ModelManager(environment=environment)
    
    return _model_manager

def get_recommendation_engine(environment: str = "development") -> PropertyRecommendationEngine:
    """Get recommendation engine instance"""
    manager = get_model_manager(environment)
    return manager.load_model()


# Production initialization
if __name__ == "__main__":
    import sys
    
    # Command line interface for model management
    if len(sys.argv) > 1:
        command = sys.argv[1]
        env = sys.argv[2] if len(sys.argv) > 2 else "development"
        
        manager = ModelManager(environment=env)
        
        if command == "train":
            print(f"Training model for {env} environment...")
            manager.load_model(force_retrain=True)
            print("Training completed!")
            
        elif command == "info":
            info = manager.get_model_info()
            print(json.dumps(info, indent=2))
            
        elif command == "health":
            health = manager.health_check()
            print(json.dumps(health, indent=2))
            
        elif command == "cleanup":
            manager.cleanup_old_backups()
            print("Cleanup completed!")
            
        else:
            print("Usage: python model_manager.py [train|info|health|cleanup] [development|staging|production]")
    else:
        # Default: start in development mode
        manager = ModelManager(environment="development")
        engine = manager.load_model()
        print(f"Model manager ready in development mode")
        print(f"Model info: {manager.get_model_info()}")
