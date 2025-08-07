from jinja2 import Template
import aiosmtplib

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

async def send_property_email(email, listings):
    html = html_template.render(listings=listings)
    await aiosmtplib.send(
        sender="noreply@yourapp.com",
        recipients=[email],
        subject="Your Property Recommendations",
        html=html,
        hostname="smtp.yourapp.com",
        username="user",
        password="pass",
        port=587,
        start_tls=True
    )

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
        
        # For development/testing - you might want to add SMTP credentials from environment variables
        # message_args["username"] = os.getenv("SMTP_USERNAME")
        # message_args["password"] = os.getenv("SMTP_PASSWORD")
        
        # For now, we'll just print the email content for testing
        print(f"📧 EMAIL NOTIFICATION:")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        print("=" * 50)
        
        # Uncomment the following line when you have SMTP credentials configured
        # await aiosmtplib.send(**message_args)
        
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        # Don't raise the exception - we don't want email failures to break the API
