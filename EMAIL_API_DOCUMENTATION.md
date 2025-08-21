# 📧 Standalone Email API Documentation

This is a completely separate email service API that's independent of the subscription system (`/api/v1/ai/subscribe`).

## 🚀 Base URL
```
http://localhost:8000/api/v1/emails
```

## 📋 Available Endpoints

### 1. **Check Email Configuration**
```http
GET /api/v1/emails/test
```

**Response:**
```json
{
  "message": "Email configuration status",
  "config": {
    "smtp_configured": true,
    "smtp_hostname": "smtp.gmail.com",
    "smtp_port": "587",
    "smtp_username": "your-email@gmail.com"
  },
  "ready_to_send": true
}
```

### 2. **Send Single Email**
```http
POST /api/v1/emails/send
```

**Request Body:**
```json
{
  "to_email": "recipient@example.com",
  "subject": "Your Subject Here",
  "body": "<h1>HTML or plain text content</h1>",
  "is_html": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Email sent successfully to recipient@example.com",
  "sent_count": 1
}
```

### 3. **Send Bulk Emails**
```http
POST /api/v1/emails/send-bulk
```

**Request Body:**
```json
{
  "to_emails": ["user1@example.com", "user2@example.com"],
  "subject": "Bulk Email Subject",
  "body": "<h1>Same content for all recipients</h1>",
  "is_html": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Bulk email completed. Sent: 2, Failed: 0",
  "sent_count": 2,
  "failed_count": 0,
  "failed_emails": null
}
```

### 4. **Send Template Email**
```http
POST /api/v1/emails/send-template
```

**Request Body:**
```json
{
  "to_email": "user@example.com",
  "template_name": "welcome",
  "template_data": {
    "name": "John Doe"
  },
  "subject": "Welcome to Our Platform!"
}
```

**Available Templates:**
- `welcome` - Welcome new users (requires: `name`)
- `notification` - General notifications (requires: `name`, `message`)
- `alert` - Important alerts (requires: `name`, `alert_message`)
- `marketing` - Marketing content (requires: `name`, `title`, `content`, `call_to_action`)

**Response:**
```json
{
  "success": true,
  "message": "Template email 'welcome' sent successfully to user@example.com",
  "sent_count": 1
}
```

## 🛠 Usage Examples

### Python Example
```python
import requests

# Send a simple email
response = requests.post('http://localhost:8000/api/v1/emails/send', json={
    "to_email": "customer@example.com",
    "subject": "Order Confirmation",
    "body": "<h2>Thank you for your order!</h2><p>Your order has been confirmed.</p>",
    "is_html": True
})

print(response.json())
```

### JavaScript Example
```javascript
// Send a template email
fetch('http://localhost:8000/api/v1/emails/send-template', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        to_email: 'newuser@example.com',
        template_name: 'welcome',
        template_data: {
            name: 'Alice Smith'
        },
        subject: 'Welcome to Real Estate AI!'
    })
})
.then(response => response.json())
.then(data => console.log(data));
```

### cURL Example
```bash
# Send bulk emails
curl -X POST "http://localhost:8000/api/v1/emails/send-bulk" \
  -H "Content-Type: application/json" \
  -d '{
    "to_emails": ["user1@example.com", "user2@example.com"],
    "subject": "Newsletter",
    "body": "<h1>Monthly Newsletter</h1><p>Check out our latest updates!</p>",
    "is_html": true
  }'
```

## 🔧 Configuration

The email system uses the same SMTP configuration as the subscription system:

```bash
# Environment variables in .env file
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_HOSTNAME=smtp.gmail.com  # Optional, defaults to Gmail
SMTP_PORT=587                 # Optional, defaults to 587
SMTP_SENDER=noreply@yourdomain.com  # Optional, defaults to noreply@realestate-ai.com
```

## 🚦 Error Handling

All endpoints return proper HTTP status codes:

- `200` - Success
- `400` - Bad request (invalid email, missing template data, etc.)
- `422` - Validation error (invalid email format, missing fields)
- `500` - Server error (SMTP failure, etc.)

**Error Response Example:**
```json
{
  "detail": "Failed to send email: SMTP authentication failed"
}
```

## 📊 Use Cases

This standalone email API is perfect for:

1. **Transactional Emails** - Order confirmations, receipts, etc.
2. **Notifications** - System alerts, status updates
3. **Marketing Campaigns** - Newsletters, promotional emails
4. **User Communications** - Welcome emails, password resets
5. **Bulk Operations** - Announcements to multiple users
6. **System Integration** - Email from other services/systems

## 🔒 Security Notes

- All endpoints support optional authentication
- Email addresses are validated using Pydantic's EmailStr
- SMTP credentials are securely stored in environment variables
- Failed email attempts are logged for monitoring

## 🆚 Difference from Subscription System

| Feature | Subscription API (`/api/v1/ai/subscribe`) | Standalone Email API (`/api/v1/emails/*`) |
|---------|-------------------------------------------|-------------------------------------------|
| Purpose | Property alerts based on search criteria | General-purpose email sending |
| Scheduling | Automatic (hourly/daily) | On-demand only |
| Content | AI-generated property recommendations | Custom content/templates |
| Recipients | Single user per subscription | Single or bulk recipients |
| Trigger | Scheduled background jobs | API calls |
| Use Case | Property subscription service | General email communications |

Both systems are completely independent and can be used together or separately.
