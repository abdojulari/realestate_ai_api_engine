from jinja2 import Template
import aiosmtplib
import os
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

html_template = Template("""
<h2>New Property Matches</h2>
{% for p in listings %}
<div>
  <h3>{{ p.title }}</h3>
  <p>{{ p.description }}</p>
  <p><strong>${{ p.price }}</strong></p>
</div>
<hr>
{% endfor %}
""")

async def send_property_email(email, listings, subject=None, html_body=None):
    """
    Send property email with enhanced AI recommendations.
    Can use either the basic template or custom HTML body.
    """
    try:
        if html_body:
            # Use custom HTML body (for enhanced emails)
            final_subject = subject or "🏠 Your AI-Powered Property Recommendations"
            final_html = html_body
        else:
            # Use basic template (for backward compatibility)
            final_subject = subject or "Your Property Recommendations"
            final_html = html_template.render(listings=listings)
        
        # Print email content for debugging
        print(f"📧 SENDING PROPERTY EMAIL:")
        print(f"To: {email}")
        print(f"Subject: {final_subject}")
        print(f"Properties: {len(listings) if isinstance(listings, list) else 'Custom HTML'}")
        print("=" * 50)
        print(final_html[:500] + "..." if len(final_html) > 500 else final_html)
        print("=" * 50)
        
        # Check if SMTP is configured
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_hostname = os.getenv("SMTP_HOSTNAME", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_sender = os.getenv("SMTP_SENDER", "noreply@realestate-ai.com")
        
        if smtp_username and smtp_password:
            # Create email message
            message = MIMEMultipart('alternative')
            message['Subject'] = final_subject
            message['From'] = smtp_sender
            message['To'] = email
            
            # Add HTML content
            html_part = MIMEText(final_html, 'html')
            message.attach(html_part)
            
            # Send actual email
            await aiosmtplib.send(
                message,
                hostname=smtp_hostname,
                username=smtp_username,
                password=smtp_password,
                port=smtp_port,
                start_tls=True
            )
            print(f"✅ Email sent successfully to {email}")
        else:
            print("⚠️  SMTP not configured - email not sent (set SMTP_USERNAME and SMTP_PASSWORD)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to send property email to {email}: {e}")
        return False

async def send_email(to_email: str, subject: str, body: str, is_html: bool = True):
    """
    Generic email sending function for notifications.
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body content
        is_html: Whether body is HTML (True) or plain text (False)
    """
    try:
        message_args = {
            "sender": "noreply@realestate-ai.com",
            "recipients": [to_email],
            "subject": subject,
            "hostname": "smtp.gmail.com",  # You can change this to your SMTP server
            "port": 587,
            "start_tls": True
        }
        
        if is_html:
            message_args["html"] = body
        else:
            message_args["text"] = body
        
        # Check if SMTP is configured
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_hostname = os.getenv("SMTP_HOSTNAME", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_sender = os.getenv("SMTP_SENDER", "noreply@realestate-ai.com")
        
        # Print email content for debugging
        print(f"📧 SENDING EMAIL NOTIFICATION:")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        print("=" * 50)
        
        if smtp_username and smtp_password:
            # Create email message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = smtp_sender
            message['To'] = to_email
            
            # Add content based on type
            if is_html:
                content_part = MIMEText(body, 'html')
            else:
                content_part = MIMEText(body, 'plain')
            message.attach(content_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=smtp_hostname,
                username=smtp_username,
                password=smtp_password,
                port=smtp_port,
                start_tls=True
            )
            print(f"✅ Notification email sent successfully to {to_email}")
        else:
            print("⚠️  SMTP not configured - email not sent (set SMTP_USERNAME and SMTP_PASSWORD)")
        
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        # Don't raise the exception - we don't want email failures to break the API
