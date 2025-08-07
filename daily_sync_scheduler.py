#!/usr/bin/env python3
"""
Daily CREA Market Data Synchronization Scheduler

This script provides automated daily synchronization of CREA property data
across Canadian provinces with comprehensive status tracking and agent performance monitoring.

Usage:
    python daily_sync_scheduler.py                    # Sync all major provinces
    python daily_sync_scheduler.py --province AB      # Sync specific province
    python daily_sync_scheduler.py --report-only      # Generate report only
"""

import asyncio
import aiohttp
import argparse
import sys
from datetime import datetime
from typing import List, Dict
import json

class CREADailySyncScheduler:
    """Daily synchronization scheduler for CREA market data"""
    
    def __init__(self, base_url: str = "http://localhost:8000/api/v1/crea"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def sync_province(self, province: str, days_back: int = 1) -> Dict:
        """Synchronize a specific province"""
        print(f"🔄 Starting daily sync for {province}...")
        
        url = f"{self.base_url}/sync/province/{province}"
        params = {"days_back": days_back}
        
        try:
            async with self.session.post(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    sync_data = result.get('sync_results', {})
                    
                    print(f"✅ {province} sync completed:")
                    print(f"   🆕 New properties: {sync_data.get('new_properties', 0)}")
                    print(f"   🔄 Updated properties: {sync_data.get('updated_properties', 0)}")
                    print(f"   📊 Status changes: {sync_data.get('status_changes', 0)}")
                    print(f"   👨‍💼 New agents: {sync_data.get('new_agents', 0)}")
                    print(f"   🏠 Active listings: {sync_data.get('active_count', 0)}")
                    print(f"   ⏱️  Time: {sync_data.get('total_time_seconds', 0):.2f}s")
                    print()
                    
                    return result
                else:
                    error_msg = f"HTTP {response.status}: {await response.text()}"
                    print(f"❌ Error syncing {province}: {error_msg}")
                    return {"error": error_msg}
                    
        except Exception as e:
            print(f"❌ Exception syncing {province}: {e}")
            return {"error": str(e)}
    
    async def sync_all_provinces(self, provinces: List[str] = None, days_back: int = 1) -> Dict:
        """Synchronize multiple provinces"""
        if provinces is None:
            provinces = ['AB', 'BC', 'ON']  # Default major provinces
        
        print(f"🚀 Starting multi-province sync for: {', '.join(provinces)}")
        print("=" * 60)
        
        url = f"{self.base_url}/sync/all-provinces"
        params = {
            "days_back": days_back,
            "provinces": provinces
        }
        
        try:
            async with self.session.post(url, params=params) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Print summary
                    totals = result.get('totals', {})
                    print(f"🎯 SYNCHRONIZATION COMPLETE")
                    print(f"   Provinces: {len(provinces)}")
                    print(f"   Total new properties: {totals.get('new_properties', 0)}")
                    print(f"   Total updates: {totals.get('updated_properties', 0)}")
                    print(f"   Status changes: {totals.get('status_changes', 0)}")
                    print(f"   New agents: {totals.get('new_agents', 0)}")
                    print(f"   Total time: {result.get('total_time_seconds', 0):.2f}s")
                    print()
                    
                    return result
                else:
                    error_msg = f"HTTP {response.status}: {await response.text()}"
                    print(f"❌ Error in multi-province sync: {error_msg}")
                    return {"error": error_msg}
                    
        except Exception as e:
            print(f"❌ Exception in multi-province sync: {e}")
            return {"error": str(e)}
    
    async def generate_daily_report(self) -> Dict:
        """Generate comprehensive daily market report"""
        print("📊 Generating daily market report...")
        
        url = f"{self.base_url}/market/daily-report"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    # Print formatted report
                    self._print_daily_report(result)
                    return result
                else:
                    error_msg = f"HTTP {response.status}: {await response.text()}"
                    print(f"❌ Error generating report: {error_msg}")
                    return {"error": error_msg}
                    
        except Exception as e:
            print(f"❌ Exception generating report: {e}")
            return {"error": str(e)}
    
    def _print_daily_report(self, report: Dict):
        """Print formatted daily report"""
        if not report.get('success'):
            print("❌ Report generation failed")
            return
        
        summary = report.get('summary', {})
        provinces = report.get('province_breakdown', {})
        
        print("=" * 70)
        print(f"📈 DAILY REAL ESTATE MARKET REPORT - {report.get('report_date', 'N/A')}")
        print("=" * 70)
        
        print(f"🏠 MARKET OVERVIEW")
        print(f"   Total Properties: {summary.get('total_properties', 0):,}")
        print(f"   Total Agents: {summary.get('total_agents', 0):,}")
        print(f"   Active Listings: {summary.get('total_active_listings', 0):,}")
        print(f"   Total Sales: {summary.get('total_sales', 0):,}")
        print(f"   Provinces Covered: {summary.get('provinces_covered', 0)}")
        print()
        
        print(f"🗺️  PROVINCE BREAKDOWN")
        for province, data in provinces.items():
            if isinstance(data, dict) and 'total_properties' in data:
                status_summary = data.get('property_status_summary', {})
                print(f"   {province}:")
                print(f"      Properties: {data.get('total_properties', 0):,}")
                print(f"      Agents: {data.get('agent_count', 0):,}")
                print(f"      Active Listings: {data.get('total_active_listings', 0):,}")
                if status_summary:
                    print(f"      Status Breakdown: {status_summary}")
                print()
        
        print("=" * 70)
        print(f"Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

async def main():
    """Main scheduler function"""
    parser = argparse.ArgumentParser(description='CREA Daily Sync Scheduler')
    parser.add_argument('--province', type=str, help='Sync specific province (e.g., AB, BC, ON)')
    parser.add_argument('--provinces', nargs='+', default=['AB', 'BC', 'ON'], 
                       help='List of provinces to sync (default: AB BC ON)')
    parser.add_argument('--days-back', type=int, default=1, 
                       help='Number of days to look back for changes (default: 1)')
    parser.add_argument('--report-only', action='store_true', 
                       help='Generate report only, skip synchronization')
    parser.add_argument('--base-url', type=str, default='http://localhost:8000/api/v1/crea',
                       help='Base URL for CREA API endpoints')
    
    args = parser.parse_args()
    
    async with CREADailySyncScheduler(args.base_url) as scheduler:
        if args.report_only:
            # Generate report only
            await scheduler.generate_daily_report()
        elif args.province:
            # Sync specific province
            await scheduler.sync_province(args.province, args.days_back)
            print("\n" + "=" * 50)
            await scheduler.generate_daily_report()
        else:
            # Sync all provinces
            await scheduler.sync_all_provinces(args.provinces, args.days_back)
            print("\n" + "=" * 50)
            await scheduler.generate_daily_report()

if __name__ == "__main__":
    # Example cron job setup (add to crontab):
    # # Daily sync at 6 AM
    # 0 6 * * * cd /path/to/realestate_ai_engine && python daily_sync_scheduler.py
    # 
    # # Alberta only sync at noon  
    # 0 12 * * * cd /path/to/realestate_ai_engine && python daily_sync_scheduler.py --province AB
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)