#!/bin/bash

# 🏠 Real Estate AI - Master Data Sync Runner
# Quick access script for running all synchronizations

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/venv"
PYTHON_SCRIPT="$SCRIPT_DIR/master_data_sync.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    echo -e "${1}${2}${NC}"
}

# Function to print help
print_help() {
    print_color $BLUE "🏠 Real Estate AI - Master Data Sync Runner"
    echo ""
    echo "Quick access commands for running data synchronization:"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  all            Run all syncs (properties, agents, housing, provinces)"
    echo "  quick          Quick sync (limited scope, recent data only)"
    echo "  properties     Sync CREA properties only"
    echo "  agents         Sync CREA agents & offices only"
    echo "  housing        Sync Statistics Canada housing data only"
    echo "  provinces      Sync CREA provinces only"
    echo "  help           Show this help message"
    echo ""
    echo "Options:"
    echo "  --dry-run      Preview changes without making them"
    echo "  --quiet        Minimal output for cron jobs"
    echo ""
    echo "Examples:"
    echo "  $0 all                  # Run complete sync"
    echo "  $0 quick                # Quick sync (6 hours of data)"
    echo "  $0 all --dry-run        # Preview all changes"
    echo "  $0 properties --quiet   # Sync properties silently"
    echo ""
}

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    print_color $RED "❌ Virtual environment not found at $VENV_PATH"
    print_color $YELLOW "Please run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    print_color $RED "❌ Python script not found at $PYTHON_SCRIPT"
    exit 1
fi

# Parse command line arguments
COMMAND=""
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        all|quick|properties|agents|housing|provinces|help)
            COMMAND="$1"
            shift
            ;;
        --dry-run|--quiet)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
        *)
            print_color $RED "❌ Unknown option: $1"
            print_help
            exit 1
            ;;
    esac
done

# Show help if no command provided
if [ -z "$COMMAND" ]; then
    print_help
    exit 0
fi

# Show help command
if [ "$COMMAND" = "help" ]; then
    print_help
    exit 0
fi

# Activate virtual environment and run sync
print_color $BLUE "🔄 Starting Real Estate AI Master Data Sync..."
print_color $YELLOW "📁 Working directory: $SCRIPT_DIR"
print_color $YELLOW "🐍 Using virtual environment: $VENV_PATH"

cd "$SCRIPT_DIR"
source "$VENV_PATH/bin/activate"

# Build Python command based on the selected command
case $COMMAND in
    all)
        PYTHON_ARGS="--all"
        ;;
    quick)
        PYTHON_ARGS="--all --quick"
        ;;
    properties)
        PYTHON_ARGS="--properties"
        ;;
    agents)
        PYTHON_ARGS="--agents"
        ;;
    housing)
        PYTHON_ARGS="--housing-data"
        ;;
    provinces)
        PYTHON_ARGS="--provinces"
        ;;
esac

# Add extra arguments
PYTHON_ARGS="$PYTHON_ARGS $EXTRA_ARGS"

print_color $GREEN "🚀 Executing: python master_data_sync.py $PYTHON_ARGS"
echo ""

# Run the Python script
python "$PYTHON_SCRIPT" $PYTHON_ARGS

# Check exit code
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_color $GREEN "✅ Master sync completed successfully!"
else
    print_color $RED "❌ Master sync failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
