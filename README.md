# Wallet Service API

A FastAPI-based backend wallet service with Paystack payment integration, JWT authentication via Google Sign-In, and API key management for service-to-service access.

## Features

- **User Authentication**: Google Sign-In with JWT token generation
- **Wallet Management**: Create and manage user wallets with unique wallet numbers
- **Paystack Integration**: Initialize deposits and handle webhooks for payment confirmation
- **Wallet Transfers**: Transfer funds between user wallets atomically
- **Transaction History**: Track all deposit, transfer, and withdrawal transactions
- **API Keys**: Service-to-service access with permission-based control
  - Maximum 5 active keys per user
  - Expiry management (1H, 1D, 1M, 1Y)
  - Rollover for expired keys
  - Fine-grained permissions (deposit, transfer, read)

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: JWT (PyJWT) + Google OAuth
- **Async**: asyncpg for async database access
- **Validation**: Pydantic
- **Payment**: Paystack API

## Project Structure

```
wallet-service/
├── app/
│   ├── config/           # Configuration and database setup
│   │   ├── settings.py   # Application settings
│   │   └── database.py   # SQLAlchemy setup
│   ├── models/           # Database models
│   │   └── __init__.py   # User, Wallet, Transaction, APIKey, WebhookLog
│   ├── routes/           # API endpoints
│   │   ├── auth.py       # Google OAuth & JWT
│   │   ├── keys.py       # API key management
│   │   ├── wallet.py     # Wallet operations
│   │   └── paystack.py   # Webhook handler
│   ├── services/         # Business logic
│   │   ├── auth.py       # Authentication service
│   │   ├── wallet.py     # Wallet operations
│   │   └── paystack.py   # Paystack integration
│   ├── utils/            # Utilities
│   │   ├── security.py   # JWT, API key hashing, expiry parsing
│   │   ├── paystack.py   # Webhook signature verification
│   │   └── exceptions.py # Custom exceptions
│   ├── middleware/       # Request middleware
│   │   └── auth.py       # Authentication middleware
│   └── main.py           # FastAPI app initialization
│   ├── schemas           # Request/Response models
│   ├── utils             # Utilities
│   │   ├── security.py   # JWT, API key hashing, expiry parsing
│   │   ├── paystack.py   # Webhook signature verification
│   │   └── exceptions.py # Custom exceptions
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Setup Instructions

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 12+
- pip

### 2. Create Virtual Environment

```bash
git clone <repository-url> && cd wallet-service
python -m venv venv

# On Windows
venv\Scripts\activate

# On Unix/macOS
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy example file
cp .env.example .env

# Edit .env with your credentials:
# - DATABASE_URL: PostgreSQL connection string
# - GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET: From Google Cloud Console
# - PAYSTACK_SECRET_KEY & PAYSTACK_PUBLIC_KEY: From Paystack dashboard
# - JWT_SECRET_KEY: Any strong secret
```

### 5. Create Database

```bash
# Create PostgreSQL database
createdb wallet_service

# Database tables will be auto-created on first app run
```

### 6. Run the Application

```bash
python main.py
```

The API will be available at `http://localhost:8000`

## API Documentation

Once the server is running, interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Authentication

```
GET /auth/google - Redirect to Google OAuth
GET /auth/google/callback - Google OAuth callback (returns JWT)
```

### API Key Management

```
POST /keys/create - Create new API key
POST /keys/rollover - Rollover expired API key
GET /keys/list - List all API keys
POST /keys/revoke/{key_id} - Revoke an API key
```

### Wallet Operations

```
POST /wallet/deposit - Initiate Paystack deposit
GET /wallet/deposit/{reference}/status - Check deposit status
GET /wallet/balance - Get wallet balance
POST /wallet/transfer - Transfer funds to another wallet
GET /wallet/transactions - Get transaction history
```

### Paystack Webhook

```
POST /wallet/paystack/webhook - Paystack webhook handler (automatic)
```

## Authentication

All protected endpoints require either:

1. **JWT Token** (from Google Sign-In):
   ```
   Authorization: Bearer <jwt_token>
   ```

2. **API Key** (for service-to-service access):
   ```
   x-api-key: <api_key>
   ```

API keys can have specific permissions: `deposit`, `transfer`, `read`

## Key Design Decisions

### 1. API Key Security
- API keys are hashed with bcrypt before storage
- Raw key is returned only once at creation time
- Keys automatically expire based on configured duration
- Maximum 5 active keys per user

### 2. Webhook Idempotency
- Paystack webhooks are tracked in `paystack_webhook_logs` table
- Prevents double-crediting on webhook retries
- Signature verification ensures webhook authenticity

### 3. Transaction Atomicity
- Wallet transfers use database transactions
- Balance is updated atomically with transaction record creation
- Failed transfers trigger automatic rollback

### 4. Expiry Conversion
- User specifies expiry as: `1H`, `1D`, `1M`, `1Y`
- Converted to absolute UTC datetime on key creation
- Automatic expiry validation on every API key use

## Error Handling

All errors return appropriate HTTP status codes with descriptive messages:

```json
{
  "detail": "Insufficient balance for this operation"
}
```

Common error codes:
- `400`: Bad request (validation, insufficient balance, limit exceeded)
- `401`: Unauthorized (invalid JWT, expired API key)
- `403`: Forbidden (missing API key permission)
- `404`: Not found (wallet, user, transaction)
- `500`: Internal server error

## Testing

Example cURL commands:

### Create API Key
```bash
curl -X POST http://localhost:8000/keys/create \
  -H "Authorization: Bearer <jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "wallet-service",
    "permissions": ["deposit", "transfer", "read"],
    "expiry": "1M"
  }'
```

### Get Wallet Balance
```bash
curl http://localhost:8000/wallet/balance \
  -H "Authorization: Bearer <jwt_token>"
```

### Transfer Funds
```bash
curl -X POST http://localhost:8000/wallet/transfer \
  -H "x-api-key: <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_number": "1234567890123",
    "amount": 5000
  }'
```

## Security Considerations

1. **Change JWT_SECRET_KEY in production** - Use a strong, unique secret
2. **Set DEBUG=False in production** - Disable debug mode
3. **Use HTTPS in production** - Don't send sensitive data over HTTP
4. **Secure environment variables** - Use secrets management service
5. **Validate webhook signatures** - Always verify Paystack signatures
6. **Rate limiting** - Consider adding rate limiting middleware
7. **Logging** - Monitor logs for suspicious activity

## Future Enhancements

- [ ] Rate limiting per API key
- [ ] Advanced fraud detection
- [ ] Withdrawal functionality
- [ ] Transaction filtering and search
- [ ] API key usage analytics
- [ ] Webhook retry mechanism with exponential backoff
- [ ] Email notifications for transactions
- [ ] Two-factor authentication
- [ ] Mobile phone number based wallet lookup

## Support

For issues, questions, or contributions, please check the project repository or contact the development team.
