#!/bin/bash

# Daily CREA Market Data Synchronization Script
# Add to crontab for automated daily execution
#
# Example crontab entries:
# # Daily sync at 6 AM
# 0 6 * * * /path/to/realestate_ai_engine/cron_daily_sync.sh
#
# # Alberta only at noon
# 0 12 * * * /path/to/realestate_ai_engine/cron_daily_sync.sh AB

set -e

# Configuration
BASE_URL="http://localhost:8000/api/v1/crea"
LOG_FILE="./crea_daily_sync.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Function to log with timestamp
log() {
    echo "[$DATE] $1" | tee -a "$LOG_FILE"
}

# Function to sync specific province
sync_province() {
    local province=$1
    local days_back=${2:-1}
    
    log "🔄 Starting daily sync for $province..."
    
    response=$(curl -s -X POST "$BASE_URL/sync/province/$province?days_back=$days_back")
    
    if echo "$response" | grep -q '"success":true'; then
        # Extract key metrics
        new_props=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('sync_results',{}).get('new_properties',0))")
        updated_props=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('sync_results',{}).get('updated_properties',0))")
        status_changes=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('sync_results',{}).get('status_changes',0))")
        new_agents=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('sync_results',{}).get('new_agents',0))")
        
        log "✅ $province sync completed: New=$new_props, Updated=$updated_props, StatusChanges=$status_changes, NewAgents=$new_agents"
    else
        log "❌ $province sync failed: $response"
        return 1
    fi
}

# Function to sync all major provinces
sync_all_provinces() {
    local provinces=("AB" "BC" "ON")
    local days_back=${1:-1}
    
    log "🚀 Starting multi-province sync for: ${provinces[*]}"
    
    # Build query string
    query_params="days_back=$days_back"
    for province in "${provinces[@]}"; do
        query_params="$query_params&provinces=$province"
    done
    
    response=$(curl -s -X POST "$BASE_URL/sync/all-provinces?$query_params")
    
    if echo "$response" | grep -q '"success":true'; then
        # Extract totals
        total_new=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('totals',{}).get('new_properties',0))")
        total_updated=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('totals',{}).get('updated_properties',0))")
        total_status=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('totals',{}).get('status_changes',0))")
        total_agents=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('totals',{}).get('new_agents',0))")
        
        log "🎯 Multi-province sync completed: New=$total_new, Updated=$total_updated, StatusChanges=$total_status, NewAgents=$total_agents"
    else
        log "❌ Multi-province sync failed: $response"
        return 1
    fi
}

# Function to generate daily report
generate_report() {
    log "📊 Generating daily market report..."
    
    response=$(curl -s "$BASE_URL/market/daily-report")
    
    if echo "$response" | grep -q '"success":true'; then
        # Extract summary data
        total_properties=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('summary',{}).get('total_properties',0))")
        total_agents=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('summary',{}).get('total_agents',0))")
        active_listings=$(echo "$response" | python3 -c "import json,sys; data=json.load(sys.stdin); print(data.get('summary',{}).get('total_active_listings',0))")
        
        log "📈 Daily Report: Properties=$total_properties, Agents=$total_agents, ActiveListings=$active_listings"
        
        # Save full report to file
        echo "$response" > "/tmp/crea_daily_report_$(date +%Y%m%d).json"
        log "📄 Full report saved to /tmp/crea_daily_report_$(date +%Y%m%d).json"
    else
        log "❌ Report generation failed: $response"
        return 1
    fi
}

# Main execution
main() {
    log "🏁 Starting CREA daily sync process..."
    
    # Check if specific province provided
    if [ $# -eq 1 ]; then
        sync_province "$1"
    elif [ $# -eq 2 ]; then
        sync_province "$1" "$2"
    else
        # Sync all major provinces
        sync_all_provinces
    fi
    
    # Always generate report
    generate_report
    
    log "✅ CREA daily sync process completed successfully"
}

# Error handling
trap 'log "❌ CREA daily sync failed with error"; exit 1' ERR

# Execute main function
main "$@"

# Success
exit 0