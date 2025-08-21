#!/usr/bin/env python3
"""
Email Setup Helper Script

This script helps you configure SMTP settings for the Real Estate AI Engine
to enable automatic property alert emails.
"""

import os
import sys
from pathlib import Path

def check_current_setup():
    """Check current SMTP configuration"""
    print("🔍 Checking current email setup...")
    
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    
    if smtp_username and smtp_password:
        print(f"✅ SMTP Username: {smtp_username}")
        print("✅ SMTP Password: Set")
        return True
    else:
        print("❌ SMTP not configured")
        return False

def setup_gmail():
    """Guide user through Gmail setup"""
    print("\n📧 Setting up Gmail SMTP...")
    print("=" * 50)
    print("To use Gmail for sending property alerts, you need:")
    print("1. A Gmail account")
    print("2. An App Password (not your regular Gmail password)")
    print("\nHow to create a Gmail App Password:")
    print("1. Go to https://myaccount.google.com/")
    print("2. Click 'Security' in the left sidebar")
    print("3. Under 'Signing in to Google', click '2-Step Verification'")
    print("4. Scroll down and click 'App passwords'")
    print("5. Select 'Mail' and 'Other (Custom name)'")
    print("6. Enter 'Real Estate AI' as the custom name")
    print("7. Click 'Generate' and copy the 16-character password")
    print("\n" + "=" * 50)
    
    email = input("Enter your Gmail address: ").strip()
    if not email or "@gmail.com" not in email:
        print("❌ Please enter a valid Gmail address")
        return False
    
    password = input("Enter your Gmail App Password (16 characters): ").strip()
    if not password or len(password) != 16:
        print("❌ App Password should be exactly 16 characters")
        return False
    
    return email, password

def create_env_file(email, password):
    """Create or update .env file"""
    env_file = Path(".env")
    
    # Read existing .env if it exists
    existing_vars = {}
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    existing_vars[key] = value
    
    # Update SMTP variables
    existing_vars['SMTP_USERNAME'] = email
    existing_vars['SMTP_PASSWORD'] = password
    
    # Write back to .env file
    with open(env_file, 'w') as f:
        for key, value in existing_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ SMTP configuration saved to {env_file}")

def test_configuration():
    """Test the email configuration"""
    print("\n🧪 Testing email configuration...")
    
    try:
        # Reload environment variables
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Import and test emailer
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        import asyncio
        from emailer import send_property_email
        
        async def test_email():
            test_listings = [{
                'title': 'Test Property',
                'description': 'This is a test email from your Real Estate AI system',
                'price': 350000
            }]
            
            result = await send_property_email(
                email=os.getenv("SMTP_USERNAME"),
                listings=test_listings,
                subject="🧪 Real Estate AI - Test Email"
            )
            return result
        
        result = asyncio.run(test_email())
        
        if result:
            print("✅ Email configuration test completed!")
            print("📧 Check your inbox for the test email")
        else:
            print("❌ Email test failed")
            
    except Exception as e:
        print(f"❌ Error testing email: {e}")

def main():
    """Main setup function"""
    print("🏠 Real Estate AI Engine - Email Setup")
    print("=" * 60)
    
    # Check current setup
    if check_current_setup():
        response = input("\nSMTP already configured. Reconfigure? (y/n): ").lower()
        if response != 'y':
            print("Setup cancelled.")
            return
    
    # Setup Gmail
    print("\nChoose your email provider:")
    print("1. Gmail (recommended)")
    print("2. Other SMTP (manual configuration)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        result = setup_gmail()
        if not result:
            return
        email, password = result
        
        # Save configuration
        create_env_file(email, password)
        
        # Test configuration
        test_config = input("\nTest email configuration now? (y/n): ").lower()
        if test_config == 'y':
            test_configuration()
            
    elif choice == "2":
        print("\nFor manual SMTP configuration, add these to your .env file:")
        print("SMTP_USERNAME=your-email@yourdomain.com")
        print("SMTP_PASSWORD=your-smtp-password")
        print("\nThen restart your application.")
        
    else:
        print("Invalid choice. Setup cancelled.")
        return
    
    print("\n🎉 Email setup complete!")
    print("Your property subscription emails will now be sent automatically.")

if __name__ == "__main__":
    main()
