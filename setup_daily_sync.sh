#!/bin/bash
# Setup script for daily housing market data sync
# Run this once to configure automatic daily updates

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYNC_SCRIPT="$SCRIPT_DIR/daily_housing_market_sync.py"
PYTHON_PATH="$SCRIPT_DIR/venv/bin/python"

echo "🏠 Setting up Housing Market Data Daily Sync"
echo "============================================="

# Make sure the sync script is executable
chmod +x "$SYNC_SCRIPT"

# Test the sync script first
echo "🧪 Testing sync script..."
cd "$SCRIPT_DIR"
source venv/bin/activate
python daily_housing_market_sync.py --dry-run --verbose

if [ $? -eq 0 ]; then
    echo "✅ Sync script test successful!"
    
    # Create cron job entry
    echo ""
    echo "📅 Cron Job Setup"
    echo "=================="
    echo "Add this line to your crontab (run 'crontab -e'):"
    echo ""
    echo "# Daily housing market data sync at 6 AM"
    echo "0 6 * * * cd $SCRIPT_DIR && source venv/bin/activate && python daily_housing_market_sync.py --verbose >> housing_sync.log 2>&1"
    echo ""
    echo "Or run this command to add it automatically:"
    echo "(crontab -l 2>/dev/null; echo \"0 6 * * * cd $SCRIPT_DIR && source venv/bin/activate && python daily_housing_market_sync.py --verbose >> housing_sync.log 2>&1\") | crontab -"
    echo ""
    
    # Manual sync options
    echo "🔧 Manual Sync Commands"
    echo "======================="
    echo "Dry run:     ./daily_housing_market_sync.py --dry-run"
    echo "Full sync:   ./daily_housing_market_sync.py --verbose"
    echo "Specific:    ./daily_housing_market_sync.py --regions Canada Alberta"
    echo ""
    
    # API endpoints
    echo "🌐 API Endpoints Available"
    echo "=========================="
    echo "Market Statistics:     GET /api/v1/market/statistics"
    echo "Market Trends:         GET /api/v1/market/trends"
    echo "Investment Metrics:    GET /api/v1/market/investment-metrics"
    echo "Investment Opportunities: GET /api/v1/market/investment-opportunities"
    echo "Complete Data:         GET /api/v1/market/complete"
    echo "Manual Sync:           POST /api/v1/market/sync"
    echo "Health Check:          GET /api/v1/market/health"
    echo ""
    
    echo "✅ Setup complete! Your frontend can now access real Canadian housing market data."
    
else
    echo "❌ Sync script test failed. Please check the configuration."
    exit 1
fi
