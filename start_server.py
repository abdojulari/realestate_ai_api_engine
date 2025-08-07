#!/usr/bin/env python3
"""
Real Estate AI Engine Server Startup Script
"""

import os
import sys
import subprocess
from pathlib import Path

def check_requirements():
    """Check if all required packages are installed."""
    print("Checking requirements...")
    
    required_packages = [
        'fastapi', 'uvicorn', 'sqlalchemy', 'psycopg2', 'passlib', 'python-jose'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing packages: {', '.join(missing_packages)}")
        print("Please run: pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_environment():
    """Check if environment is properly configured."""
    print("Checking environment configuration...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        print("Please copy .env.template to .env and configure your settings")
        return False
    
    print("✅ Environment file found")
    return True

def check_database():
    """Check if database connection works."""
    print("Checking database connection...")
    
    try:
        from database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Please check your DATABASE_URL in .env file")
        print("Make sure PostgreSQL is running and the database exists")
        return False

def start_server():
    """Start the FastAPI server."""
    print("Starting Real Estate AI Engine server...")
    print("Server will be available at: http://localhost:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        import uvicorn
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")

def main():
    """Main startup function."""
    print("🏠 Real Estate AI Engine Server")
    print("=" * 40)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Run checks
    checks = [
        check_requirements(),
        check_environment(),
        check_database()
    ]
    
    if not all(checks):
        print("\n❌ Startup checks failed. Please fix the issues above.")
        sys.exit(1)
    
    print("\n✅ All checks passed! Starting server...")
    print()
    
    # Start server
    start_server()

if __name__ == "__main__":
    main() 