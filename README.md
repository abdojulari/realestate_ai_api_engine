# Real Estate - MLS-I

MLS Intelligence (MLS-I) is a real estate search platform. Listing data in the seed set is fictional. People describe what they want in everyday language, and the API turns that into database filters such as city, price, and bedrooms.

This project does not build, train, fine-tune, or evaluate a model, and it does not call a model API.

The API is running at `http://127.0.0.1:8000`.

## Commands

### Start

```bash
cd realestate_ai_engine
source venv/bin/activate
uvicorn main:app --host 127.0.0.1 --port 8000
```

`python main.py` starts the same app on `0.0.0.0:8000` with reload.

### Check it

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/docs
```

Interactive docs: http://127.0.0.1:8000/docs

### Setup

Requires Python 3.9 and PostgreSQL. This machine uses the `realestate_db` database on PostgreSQL 14 (`postgresql://postgres@localhost:5432/realestate_db`).

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python init_db.py
```

Fill `SMTP_USERNAME` and `SMTP_PASSWORD` in `.env` before sending email. The API starts without those values.

### Migration and seed data

```bash
source venv/bin/activate
alembic upgrade head
python seed_data.py
```

`alembic upgrade head` creates any missing tables. `seed_data.py` loads fictional records and can be run again. Every email address and password in this README is dummy data, not a real account. Every seed account uses the password `SeedPass123!`:

- `seed.admin@example.com`
- `seed.agent@example.com`
- `seed.customer@example.com`

Seed listings are in Seedville: `SEED-LISTING-001` and `SEED-LISTING-002`.

```bash
curl "http://127.0.0.1:8000/api/v1/properties/?city=Seedville&limit=5"

curl -X POST "http://127.0.0.1:8000/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"seed.customer@example.com","password":"SeedPass123!"}'
```

### Properties, agents, and market data

```bash
curl "http://127.0.0.1:8000/api/v1/properties/?limit=1"
curl "http://127.0.0.1:8000/api/v1/properties/search?q=Calgary"
curl "http://127.0.0.1:8000/api/v1/amenities/"
curl "http://127.0.0.1:8000/api/v1/agents/"
curl "http://127.0.0.1:8000/api/v1/market/health"
curl "http://127.0.0.1:8000/api/v1/market/statistics"
curl "http://127.0.0.1:8000/api/v1/dailytips/public"
```

### Auth

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/users/signup" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"securepassword","first_name":"Ada","last_name":"Lovelace","role":"customer"}'

curl -X POST "http://127.0.0.1:8000/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"securepassword"}'

curl "http://127.0.0.1:8000/api/v1/users/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

## Routes

| Area | Method | Path |
| --- | --- | --- |
| Health | GET | `/health` |
| Root | GET | `/` |
| Users | POST | `/api/v1/users/signup` |
| Users | POST | `/api/v1/users/login` |
| Users | POST | `/api/v1/users/logout` |
| Users | GET, PUT, DELETE | `/api/v1/users/me` |
| Users | POST | `/api/v1/users/change-password` |
| Users | POST | `/api/v1/users/request-password-reset` |
| Users | GET | `/api/v1/users/` |
| Users | GET, PUT, DELETE | `/api/v1/users/{user_id}` |
| Users | PUT | `/api/v1/users/{user_id}/role` |
| Properties | GET, POST | `/api/v1/properties/` |
| Properties | GET | `/api/v1/properties/search` |
| Properties | GET, PUT, DELETE | `/api/v1/properties/{property_id}` |
| Properties | POST, DELETE | `/api/v1/properties/{property_id}/save` |
| Properties | GET | `/api/v1/properties/{property_id}/amenities` |
| Properties | GET, POST | `/api/v1/properties/{property_id}/images` |
| Agents | GET | `/api/v1/agents/` |
| Agents | GET | `/api/v1/agents/{agent_id}` |
| Agents | GET | `/api/v1/agents/{agent_id}/properties` |
| Agents | GET | `/api/v1/agents/my-clients` |
| Agents | POST | `/api/v1/agents/request-representation` |
| Agent profiles | GET | `/api/v1/agent-profiles/` |
| Agent profiles | GET, POST, PUT, DELETE | `/api/v1/agent-profiles/my-profile` |
| Agent onboarding | POST | `/api/v1/agent-onboarding/claim-profile` |
| Agent onboarding | GET | `/api/v1/agent-onboarding/search-profile` |
| AI | POST | `/api/v1/ai/parse` |
| AI | POST | `/api/v1/ai/subscribe` |
| Search | POST | `/api/v1/ai/recommend-properties` |
| Search | POST | `/api/v1/ai/analyze-market` |
| Search | POST | `/api/v1/ai/generate-description` |
| Search | GET | `/api/v1/ai/similar-properties/{property_id}` |
| Market | GET | `/api/v1/market/health` |
| Market | GET | `/api/v1/market/statistics` |
| Market | GET | `/api/v1/market/trends` |
| Market | GET | `/api/v1/market/complete` |
| Market | POST | `/api/v1/market/sync` |
| Amenities | GET, POST | `/api/v1/amenities/` |
| Views | GET, POST | `/api/v1/views/` |
| Property types | GET, POST | `/api/v1/property-types/` |
| Saved searches | GET, POST | `/api/v1/saved-searches/` |
| Notifications | GET | `/api/v1/notifications/` |
| Property interests | GET, POST | `/api/v1/property-interests/` |
| Neighbourhoods | GET, POST | `/api/v1/neighbourhoods/` |
| Schools | GET, POST | `/api/v1/schools/` |
| Market insights | GET, POST | `/api/v1/market-insights/` |
| Daily tips | GET | `/api/v1/dailytips/public` |
| Emails | POST | `/api/v1/emails/send` |
| Legacy | POST | `/parse` |
| Legacy | POST | `/subscribe` |

The full list, including path parameters, is at http://127.0.0.1:8000/docs.

## TODO 

- [ ] Create a frontend UI 
- [ ] Let users find properties by describing what they want in everyday language. The parser uses rules and database filters, not a model.
- [ ] Create end-to-end, smoke and unit testings 
- [ ] Enable multi-factor authentication 
- [ ] redesign the architecture to allow tenant to be able to configure their respectful Data feed providers
- [ ] Support with in-app notification, tenant-based email notifications
- [ ] Create deployment script for production 
- [ ] Use opentelemetry for logging 
- [ ] Create a customer retention pipeline funnel to track engagement, improve loyalty and keep customers coming back
- [ ] Do not build, train, or fine-tune a custom model. Property matching uses database filters.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE). You may freely use, copy, modify, merge, publish, distribute, sublicense, and sell it. Redistribution must keep the copyright notice and this license.