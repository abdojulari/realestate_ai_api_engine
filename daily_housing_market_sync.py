#!/usr/bin/env python3
"""
Daily Housing Market Data Sync Script
Syncs housing market data from Statistics Canada WDS API
Run this daily via cron job to keep market data current
"""

import argparse
import logging
import sys
from datetime import datetime
from database import SessionLocal
from statcan_housing_data import HousingDataService, HousingMarketData
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('housing_market_sync.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def run_housing_data_sync(regions=None, dry_run=False):
    """
    Run the housing market data synchronization
    """
    db = SessionLocal()
    
    try:
        logger.info("🏠 Starting Housing Market Data Sync")
        logger.info("=" * 50)
        
        if not regions:
            regions = [
                'Canada',
                'Alberta', 
                'British Columbia',
                'Ontario',
                'Quebec',
                'Saskatchewan',
                'Manitoba',
                'Nova Scotia',
                'New Brunswick',
                'Newfoundland and Labrador',
                'Prince Edward Island',
                'Northwest Territories',
                'Yukon',
                'Nunavut'
            ]
        
        logger.info(f"📍 Syncing data for regions: {', '.join(regions)}")
        
        if dry_run:
            logger.info("🧪 DRY RUN MODE - No data will be saved")
        
        # Initialize housing service
        housing_service = HousingDataService(db)
        
        # Check existing data
        existing_count = db.query(HousingMarketData).count()
        logger.info(f"📊 Current records in database: {existing_count}")
        
        # Sync housing data
        logger.info("🔄 Starting StatCan data sync...")
        
        if not dry_run:
            results = housing_service.sync_housing_data(regions)
        else:
            # Test API access without saving
            from statcan_housing_data import StatCanHousingAPI
            api = StatCanHousingAPI()
            nhpi_data = api.get_housing_price_index(['Canada'])
            results = {
                'nhpi_records': len(nhpi_data),
                'sales_records': 0,
                'price_records': 0,
                'affordability_records': 0,
                'errors': 0
            }
        
        # Log results
        logger.info("📈 Sync Results:")
        logger.info(f"   NHPI records: {results['nhpi_records']}")
        logger.info(f"   Sales records: {results['sales_records']}")
        logger.info(f"   Price records: {results['price_records']}")
        logger.info(f"   Affordability records: {results['affordability_records']}")
        logger.info(f"   Errors: {results['errors']}")
        
        total_new = sum([
            results['nhpi_records'],
            results['sales_records'], 
            results['price_records'],
            results['affordability_records']
        ])
        
        logger.info(f"✅ Total new records: {total_new}")
        
        if not dry_run:
            # Final count
            final_count = db.query(HousingMarketData).count()
            logger.info(f"📊 Final records in database: {final_count}")
            logger.info(f"📈 Net change: +{final_count - existing_count}")
        
        # Test market statistics generation
        logger.info("🧪 Testing market statistics generation...")
        test_stats = housing_service.get_market_statistics('Canada')
        
        logger.info("📊 Sample Market Statistics:")
        logger.info(f"   Properties Sold: {test_stats.get('properties_sold', 'N/A')}")
        logger.info(f"   Average Price: ${test_stats.get('average_price', 'N/A'):,}")
        logger.info(f"   Price Change: {test_stats.get('price_change', 'N/A')}%")
        logger.info(f"   Active Listings: {test_stats.get('active_listings', 'N/A')}")
        
        logger.info("✅ Housing market data sync completed successfully!")
        
        return {
            'status': 'success',
            'total_new_records': total_new,
            'results': results,
            'test_stats': test_stats
        }
        
    except Exception as e:
        logger.error(f"❌ Error during housing data sync: {e}")
        logger.error(traceback.format_exc())
        db.rollback()
        
        return {
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }
        
    finally:
        db.close()


def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Sync housing market data from Statistics Canada')
    
    parser.add_argument(
        '--regions',
        nargs='+',
        help='Specific regions to sync (default: all Canadian provinces/territories)',
        default=None
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Test the sync without saving data to database'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run the sync
    result = run_housing_data_sync(
        regions=args.regions,
        dry_run=args.dry_run
    )
    
    # Exit with appropriate code
    if result['status'] == 'success':
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
