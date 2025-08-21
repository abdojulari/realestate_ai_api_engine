# Real Estate AI Engine API

A comprehensive real estate management API with AI-powered search, authentication, and full CRUD operations for properties, users, agents, and related entities.

## Features

### 🔐 Authentication & Authorization
- JWT token-based authentication
- Role-based access control (Customer, Client, Agent, Admin)
- Secure password hashing with bcrypt
- User registration and profile management

### 🏠 Property Management
- Full CRUD operations for properties
- Advanced filtering and search capabilities
- Property amenities and views management
- Image and media handling
- Property view tracking and analytics

### 👥 User Management
- Multi-role user system
- User preferences and saved searches
- Property favorites and bookmarks
- User activity tracking

### 🏢 Agent & Listing Management
- Agent profiles and management
- Property listings with MLS integration
- Listing types and status tracking
- Agent performance analytics

### 🔍 Advanced Search & AI
- Natural language property search
- AI-powered property recommendations
- Saved search alerts and notifications
- Embedding-based similarity matching

### 📊 Analytics & Reporting
- Property view analytics
- User behavior tracking
- Market insights and trends
- Performance metrics

## 🚀 Quick Start Guide

### **🎯 Get Properties in 3 Steps**

#### **Step 1: Start the API**
```bash
cd realestate_ai_engine
source venv/bin/activate
uvicorn main:app --reload
```

#### **Step 2: Access Properties**
```bash
# Option A: Get ALL properties from your local database
curl "http://localhost:8000/api/v1/properties/"

# Option B: Search specific properties  
curl "http://localhost:8000/api/v1/properties/search?q=Calgary"

# Option C: Filter by province
curl "http://localhost:8000/api/v1/properties/?province=Alberta&limit=10"
```

#### **Step 3: Import Fresh CREA Data (Optional)**
```bash
# Import ALL Alberta properties from CREA (5000+)
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Alberta"

# Or any other province
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Ontario"
```

### **📖 Interactive API Documentation**
Visit: **http://localhost:8000/docs** 
- Try all endpoints directly in your browser
- View request/response examples
- Test CREA integration features

---

## 🏗️ CREA Integration - Complete Guide

### **🎯 What You Get**
- ✅ **20,000+ Properties** across all Canadian provinces  
- ✅ **Real Agent Data** with contact information and performance metrics
- ✅ **Live Market Data** with Active, Pending, and Sold status tracking
- ✅ **Daily Auto-Sync** to keep your database current
- ✅ **Production Ready** pagination that handles large datasets

### **🚀 Essential Endpoints**

#### **1. 📊 Get Live CREA Data**
```bash
# Get ALL properties for any province (handles 5000+ properties)
curl "http://localhost:8000/api/v1/crea/properties/search-all/Alberta"
curl "http://localhost:8000/api/v1/crea/properties/search-all/Ontario" 
curl "http://localhost:8000/api/v1/crea/properties/search-all/British Columbia"

# Filter by status
curl "http://localhost:8000/api/v1/crea/properties/search-all/Alberta?status_filter=Sold"
curl "http://localhost:8000/api/v1/crea/properties/search-all/Alberta?status_filter=Pending"
```

#### **2. 💾 Import to Local Database**
```bash
# Import ALL properties from a province (creates local copies)
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Alberta"

# Import with limits for testing  
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Alberta&max_properties=100"
```

#### **3. 🔄 Daily Synchronization** 
```bash
# Sync single province (updates existing + adds new)
curl -X POST "http://localhost:8000/api/v1/crea/sync/province/Alberta"

# Sync ALL major provinces
curl -X POST "http://localhost:8000/api/v1/crea/sync/all-provinces"
```

#### **4. 📈 Market Reports**
```bash
# Daily market overview across Canada
curl "http://localhost:8000/api/v1/crea/market/daily-report"

# Province-specific market data
curl "http://localhost:8000/api/v1/crea/market/province/Alberta"

# Agent performance metrics
curl "http://localhost:8000/api/v1/crea/market/agent-performance/{agent_id}"
```

### **🏠 Access Your Properties**

#### **Once Data is Imported:**
```bash
# All your properties (CREA + manual entries)
curl "http://localhost:8000/api/v1/properties/"

# Search by city/address
curl "http://localhost:8000/api/v1/properties/search?q=Calgary downtown"

# Filter by criteria
curl "http://localhost:8000/api/v1/properties/?province=Alberta&min_price=300000&max_price=500000"

# Get property details + agent info
curl "http://localhost:8000/api/v1/properties/{property_id}"

# Property images
curl "http://localhost:8000/api/v1/properties/{property_id}/images"
```

### **🤖 Automated Daily Updates**

#### **Setup Cron Job:**
```bash
# Edit crontab
crontab -e

# Add this line for daily 6am sync
0 6 * * * cd /path/to/realestate_ai_engine && ./cron_daily_sync_local.sh
```

#### **Manual Daily Sync:**
```bash
cd realestate_ai_engine
./cron_daily_sync_local.sh AB  # Alberta only
./cron_daily_sync_local.sh     # All provinces
```

### **📋 Complete Province List**
```bash
# Major Provinces (High Volume)
Alberta, Ontario, British Columbia, Quebec

# All Provinces Supported  
Alberta, British Columbia, Ontario, Quebec, Manitoba, 
Saskatchewan, Nova Scotia, New Brunswick, 
Prince Edward Island, Newfoundland and Labrador,
Northwest Territories, Yukon, Nunavut
```

### **🎯 Sample Workflow**
```bash
# 1. Import Alberta market (5000+ properties)
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Alberta"

# 2. View your properties
curl "http://localhost:8000/api/v1/properties/?province=Alberta&limit=5"

# 3. Search Calgary properties  
curl "http://localhost:8000/api/v1/properties/search?q=Calgary"

# 4. Daily market report
curl "http://localhost:8000/api/v1/crea/market/daily-report"

# 5. Setup automated daily sync
echo "0 6 * * * cd $(pwd) && ./cron_daily_sync_local.sh" | crontab -
```

### **🚨 Troubleshooting**

#### **No Properties Found?**
```bash
# Check if database is empty
curl "http://localhost:8000/api/v1/properties/" 

# If empty, import some data
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Alberta&max_properties=100"
```

#### **CREA API Issues?**
```bash
# Check token status
curl "http://localhost:8000/api/v1/crea/token/status"

# Refresh token if needed  
curl -X POST "http://localhost:8000/api/v1/crea/token/refresh"

# Test basic API connectivity
curl "http://localhost:8000/api/v1/crea/api-info"
```

#### **Performance Issues?**
```bash
# Use smaller batches for testing
curl -X POST "http://localhost:8000/api/v1/crea/bulk/import-all-province?province=Alberta&max_properties=50"

# Check specific province data
curl "http://localhost:8000/api/v1/crea/properties/search-all/Alberta?max_results=10"
```

#### **Need Help?**
- 📖 **Interactive Docs**: Visit `http://localhost:8000/docs`
- 🔍 **Check Logs**: Look at terminal output for detailed error messages
- 🧪 **Test Environment**: Start with small data samples before full imports

---

## Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Virtual environment (recommended)

### Installation

1. **Clone and Setup**
   ```bash
   cd realestate_ai_engine
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Database Setup**
   ```bash
   # Create PostgreSQL database
   createdb realestate_db
   
   # Copy environment template
   cp .env.template .env
   
   # Edit .env with your database credentials
   nano .env
   ```

3. **Initialize Database**
   ```bash
   python init_db.py
   ```

4. **Run the Application**
   ```bash
   python main.py
   # or
   uvicorn main:app --reload
   ```

5. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

## API Endpoints

### Authentication
- `POST /api/v1/users/signup` - User registration
- `POST /api/v1/users/login` - User login
- `GET /api/v1/users/me` - Get current user
- `PUT /api/v1/users/me` - Update current user

### Properties
- `GET /api/v1/properties` - List properties with filters
- `POST /api/v1/properties` - Create property (Agent/Admin)
- `GET /api/v1/properties/{id}` - Get property details
- `PUT /api/v1/properties/{id}` - Update property
- `DELETE /api/v1/properties/{id}` - Delete property
- `POST /api/v1/properties/{id}/save` - Save to favorites
- `GET /api/v1/properties/search` - Text search

### Agent Profiles & Discovery
- `GET /api/v1/agents/` - **Discover agents** (enhanced profiles with social media, ratings, etc.)
- `GET /api/v1/agents/{agent_id}` - Get specific agent's public profile
- `GET /api/v1/agent-profiles/` - List all enhanced agent profiles with filters
- `GET /api/v1/agent-profiles/{agent_id}` - Get public agent profile by ID

### Agent Profile Management (For Agents)
- `GET /api/v1/agent-profiles/my-profile` - Get current agent's profile
- `POST /api/v1/agent-profiles/my-profile` - Create agent profile
- `PUT /api/v1/agent-profiles/my-profile` - Update agent profile
- `DELETE /api/v1/agent-profiles/my-profile` - Delete agent profile

### Property Relationships
- `GET /api/v1/amenities` - List amenities
- `POST /api/v1/amenities` - Create amenity (Admin)
- `GET /api/v1/views` - List property views

### User Features
- `GET /api/v1/saved-searches` - User's saved searches
- `POST /api/v1/saved-searches` - Create saved search
- `PUT /api/v1/saved-searches/{id}` - Update saved search
- `DELETE /api/v1/saved-searches/{id}` - Delete saved search

### Legacy AI Endpoints
- `POST /parse` - Parse natural language to filters
- `POST /subscribe` - Subscribe to property alerts

## User Roles & Permissions

### Customer (Default)
- Browse and search properties
- Save properties and searches
- View property details
- Manage personal profile

### Client
- All customer permissions
- Enhanced search features
- Priority support features

### Agent
- All client permissions
- Create and manage properties
- Manage listings
- Access to agent tools

### Admin
- All permissions
- User management
- System configuration
- Analytics and reporting

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/db_name

# Security
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Frontend Configuration (required for password reset links)
FRONTEND_BASE_URL=http://localhost:5173

# CREA API (Optional)
CREA_CLIENT_ID=your_client_id
CREA_CLIENT_SECRET=your_client_secret

# Features
DEBUG=False
LOG_LEVEL=INFO
```

### Database Schema

The application uses PostgreSQL with a clean, unified architecture:

## 💡 Advanced Features

### **🔍 AI-Powered Search**
- Natural language property queries
- Semantic similarity matching  
- Intelligent filtering and recommendations
- Saved search alerts with notifications

### **📊 Analytics & Insights**
- Property view tracking and heatmaps
- User behavior analytics
- Market trend analysis
- Agent performance metrics

### **🏢 Agent Tools**
- Comprehensive agent profiles
- Listing management with MLS integration
- Client relationship tracking
- Performance dashboard and reporting

## 🏗️ Architecture

### **Unified Agent System**
- **Enhanced Agent Profiles**: User-based system with comprehensive professional data
- **Consistent API**: All endpoints return the same rich agent data structure
- **Role-Based Access**: Customer → Client → Agent → Admin hierarchy
- **Relationship Management**: Complete client-agent relationship tracking

### **Database Structure**
```
👤 USERS (Single source of truth)
├── user_id (UUID) - Primary Key
├── role (customer/client/agent/admin)
└── Core user information

📊 AGENT_PROFILES (Extended agent data)
├── profile_id (UUID) - Primary Key
├── user_id → REFERENCES users.user_id
├── Professional info (aka, specialization, experience)
├── Performance metrics (rating, total_sales)
├── Social media links (JSON)
└── Location & service areas

🏠 PROPERTIES + 📋 LISTINGS + 🤝 RELATIONSHIPS
├── Full property management
├── Client-agent relationships
└── Property interests tracking
```

### **Main Entities**
- **Users** (with roles and agent profiles)
- **Properties** (with full details and listings)
- **Agent Profiles** (enhanced professional data)
- **Client-Agent Relationships**
- **Amenities, Views, and Property Interests**

## Development

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=.
```

### Adding New Features

1. Create new models in `db_models.py`
2. Add schemas in `schemas.py`
3. Create router in `routers/`
4. Add router to `main.py`
5. Update database with `init_db.py`

## Production Deployment

1. **Security**
   - Change default admin password
   - Use strong SECRET_KEY
   - Configure CORS properly
   - Enable HTTPS

2. **Database**
   - Use production PostgreSQL
   - Set up backups
   - Configure connection pooling

3. **Performance**
   - Use Gunicorn or similar WSGI server
   - Set up Redis for caching
   - Configure CDN for media files

4. **Monitoring**
   - Set up logging
   - Configure health checks
   - Monitor API performance

## API Examples

### Create User
```bash
curl -X POST "http://localhost:8000/api/v1/users/signup" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword",
    "first_name": "John",
    "last_name": "Doe",
    "role": "customer"
  }'
```

### Login
```bash
curl -X POST "http://localhost:8000/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword"
  }'
```

### Search Properties
```bash
curl -X GET "http://localhost:8000/api/v1/properties?city=Toronto&min_bedrooms=2&max_price=500000" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Create Property (Agent/Admin)
```bash
curl -X POST "http://localhost:8000/api/v1/properties" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Beautiful Family Home",
    "description": "Spacious 3-bedroom home in great neighborhood",
    "address": "123 Main St",
    "city": "Toronto",
    "province": "ON",
    "price": 450000,
    "bedrooms": 3,
    "bathrooms": 2,
    "square_feet": 1800
  }'
```

## Support

For questions, issues, or contributions:
1. Check the API documentation at `/docs`
2. Review the database schema
3. Check environment configuration
4. Ensure all dependencies are installed

## License

This project is licensed under the MIT License. 

## **✅ Yes, there ARE comprehensive relationships between UserID, AgentID, and CustomerID!**

Here's the relationship structure I've implemented:

### **🔗 Relationship Architecture:**

```
👤 USERS TABLE (Single source of truth)
├── user_id (UUID) - Primary Key
├── role ("customer", "client", "agent", "admin")
├── email, name, phone, etc.
└── Relationships to other entities

📊 CLIENT_AGENT_RELATIONSHIPS TABLE
├── relationship_id (UUID) - Primary Key
├── client_id (UUID) → REFERENCES users.user_id (where role = "customer"/"client") 
├── agent_id (UUID) → REFERENCES users.user_id (where role = "agent")
├── status ("pending", "active", "inactive", "terminated")
├── requested_by ("client" or "agent")
├── property_id (UUID) → Property that triggered the relationship
└── timestamps (created_at, activated_at, terminated_at)
```

### **🎯 Key Relationships:**

1. **Customer/Client ↔ Agent Relationships:**
   ```sql
   -- A customer can have multiple agent relationships
   User (role='customer') → ClientAgentRelationship.client_id
   
   -- An agent can have multiple client relationships  
   User (role='agent') → ClientAgentRelationship.agent_id
   ```

2. **Property Interest Tracking:**
   ```sql
   -- Users can express interest in properties
   User → PropertyInterest.user_id
   Property → PropertyInterest.property_id
   Agent → PropertyInterest.agent_id (optional - assigned agent)
   ```

3. **Notification System:**
   ```sql
   -- All notifications are user-specific
   User → Notification.user_id
   ```

### **📋 Example Relationships:**

**Customer requests Agent representation:**
```javascript
<code_block_to_apply_changes_from>
```

**Agent manages multiple clients:**
```javascript
// Agent can see all their client relationships
GET /api/v1/agents/my-clients
// Returns all ClientAgentRelationship records where agent_id = current_user.user_id
```

**Customer expresses property interest:**
```javascript
{
  "user_id": "customer-user-uuid",       // The customer
  "property_id": "property-uuid",        // Property of interest
  "agent_id": "agent-user-uuid",         // Assigned/requested agent
  "interest_level": "very_interested"
}
```

### **🔍 Query Examples:**

**Find all clients for an agent:**
```sql
SELECT u.* FROM users u
JOIN client_agent_relationships car ON u.user_id = car.client_id  
WHERE car.agent_id = 'agent-uuid' AND car.status = 'active'
```

**Find customer's current agent:**
```sql
SELECT u.* FROM users u
JOIN client_agent_relationships car ON u.user_id = car.agent_id
WHERE car.client_id = 'customer-uuid' AND car.status = 'active'
```

**Check if customer has representation:**
```sql
SELECT COUNT(*) FROM client_agent_relationships 
WHERE client_id = 'customer-uuid' AND status = 'active'
```

### **🚀 API Endpoints for Relationships:**

- `GET /api/v1/agents/` - Discover available agents
- `POST /api/v1/agents/request-representation` - Customer requests agent
- `GET /api/v1/agents/my-clients` - Agent sees their clients
- `PUT /api/v1/agents/client-relationship/{id}` - Agent accepts/rejects client
- `GET /api/v1/property-interests/client/{client_id}` - Agent sees client's interests

This structure ensures **complete relationship tracking** while maintaining data integrity and supporting all the business logic you described! 🎯 

## How to Test via FastAPI Docs:
- Visit: `http://localhost:8000/docs`
- Look for the "CREA API Testing" section
- Start with: `/api/v1/crea/test/connection` to verify everything works
- Check token: `/api/v1/crea/token/status` to see current token info
- Search properties: `/api/v1/crea/properties/search` with filters like:
  - top=5 (limit results)
  - min_price=100000
  - max_price=500000
  - bedrooms=2

## 💾 Token Storage:
- Current: Tokens are stored in server memory (session-based)
- Automatic refresh: Happens when token expires
Thread-safe: Single global instance handles all requests
Secure: Only token preview shown in responses