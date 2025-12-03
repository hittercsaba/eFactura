# eFactura Gateway

A containerized SaaS application for Romanian accountants and business owners to connect their ANAF (National Tax Agency) accounts via OAuth, manage multiple companies, sync invoices, and provide API access.

## Features

- OAuth integration with ANAF
- Multi-company support (1 User → Many Companies)
- Automatic invoice synchronization from ANAF
- XML to JSON invoice parsing
- Company-scoped API keys
- Modern dashboard with Volt-style UI
- RESTful API for programmatic access

## Quick Start

1. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```

2. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

3. Access the application at `http://localhost:8008`

4. Create an admin user:
   ```bash
   docker exec -it anaf_efactura-web-1 python set_admin.py
   ```

## Project Structure

- `app/` - Main application code
- `migrations/` - Database migrations
- `Dockerfile` - Container definition
- `docker-compose.yml` - Multi-container setup
- `entrypoint.sh` - Startup script with DB wait and migrations

## Database Models

- **User**: Account holders with admin approval system
- **AnafOAuthConfig**: System-wide OAuth credentials (admin-managed)
- **AnafToken**: ANAF access/refresh tokens per user
- **Company**: Companies (CUIs) linked to users
- **ApiKey**: Company-scoped API keys
- **Invoice**: Synced invoices with XML and JSON content

## API Endpoints

The API follows RESTful conventions and uses API key authentication.

### Base URL
```
http://localhost:8008/api/v1
```

### Authentication

All API requests require an `X-API-KEY` header with a valid API key.

```http
X-API-KEY: your-api-key-here
```

API keys are company-scoped and can be generated from the API Settings page in the web interface.

### Endpoints

#### Health Check

```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-12-03T12:00:00.000000",
  "version": "1.0.0"
}
```

#### List Invoices

```http
GET /api/v1/invoices
```

**Query Parameters:**
- `page` (int, optional): Page number (default: 1)
- `per_page` (int, optional): Items per page (default: 50, max: 100)
- `supplier_cif` (string, optional): Filter by supplier CIF
- `date_from` (string, optional): Filter invoices from date (ISO format: YYYY-MM-DD)
- `date_to` (string, optional): Filter invoices to date (ISO format: YYYY-MM-DD)

**Example Request:**
```bash
curl -X GET "http://localhost:8008/api/v1/invoices?page=1&per_page=50&date_from=2025-01-01" \
  -H "X-API-KEY: your-api-key-here"
```

**Response:**
```json
{
  "data": [
    {
      "id": 1,
      "anaf_id": "1234567890",
      "supplier_name": "Supplier Name SRL",
      "supplier_cif": "12345678",
      "invoice_date": "2025-01-15",
      "total_amount": 1000.50,
      "synced_at": "2025-01-16T10:30:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 100,
    "pages": 2,
    "has_next": true,
    "has_prev": false
  },
  "meta": {
    "company_id": 1,
    "company_cif": "51331025"
  }
}
```

#### Get Invoice by ID

```http
GET /api/v1/invoices/{invoice_id}
```

**Path Parameters:**
- `invoice_id` (int, required): Invoice ID

**Example Request:**
```bash
curl -X GET "http://localhost:8008/api/v1/invoices/1" \
  -H "X-API-KEY: your-api-key-here"
```

**Response:**
```json
{
  "data": {
    "id": 1,
    "anaf_id": "1234567890",
    "supplier_name": "Supplier Name SRL",
    "supplier_cif": "12345678",
    "invoice_date": "2025-01-15",
    "total_amount": 1000.50,
    "synced_at": "2025-01-16T10:30:00",
    "details": {
      // Full invoice JSON content
    }
  }
}
```

### Error Responses

All errors follow a consistent format:

```json
{
  "error": "Error Type",
  "message": "Human-readable error message",
  "code": "ERROR_CODE"
}
```

**HTTP Status Codes:**
- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing or invalid API key)
- `404` - Not Found (resource doesn't exist or not accessible)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error
- `503` - Service Unavailable

**Error Examples:**

Missing API Key:
```json
{
  "error": "Unauthorized",
  "message": "Missing X-API-KEY header",
  "code": "MISSING_API_KEY"
}
```

Invalid API Key:
```json
{
  "error": "Unauthorized",
  "message": "Invalid API key",
  "code": "INVALID_API_KEY"
}
```

Invoice Not Found:
```json
{
  "error": "Not Found",
  "message": "Invoice not found or not accessible",
  "code": "INVOICE_NOT_FOUND"
}
```

Rate Limit Exceeded:
```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Please try again later.",
  "code": "RATE_LIMIT_EXCEEDED"
}
```

### Rate Limiting

API endpoints are rate-limited:
- `/api/v1/invoices`: 100 requests per hour per IP
- Other endpoints: 200 requests per day, 50 per hour per IP

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum number of requests
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets

## Security

### Authentication & Authorization
- API keys are hashed using Werkzeug's password hashing
- API keys are company-scoped (access only to invoices for that company)
- Rate limiting prevents abuse
- CSRF protection on web forms
- Secure password hashing (Werkzeug)

### Data Protection
- Client secrets encrypted at rest using Fernet (symmetric encryption)
- Passwords never stored in plain text
- API keys hashed before storage
- HTTPS recommended for production (configure reverse proxy)

### Input Validation
- All user inputs validated and sanitized
- SQL injection prevention via SQLAlchemy ORM
- XSS protection via Flask-WTF CSRF tokens
- Email format validation
- Password strength requirements (minimum 8 characters)

### Security Headers
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- Content Security Policy (CSP) configured

## Development

### Run Migrations

```bash
# Create a new migration
docker-compose exec web flask db migrate -m "Description"

# Apply migrations
docker-compose exec web flask db upgrade
```

### Database Access

```bash
# Connect to PostgreSQL
docker exec -it anaf_efactura-db-1 psql -U efactura_user -d efactura_db
```

### Environment Variables

Key environment variables (set in `.env` or `docker-compose.yml`):
- `SECRET_KEY`: Flask secret key (required for encryption)
- `DATABASE_URL`: PostgreSQL connection string
- `ANAF_API_BASE_URL`: ANAF API base URL (default: https://api.anaf.ro)
- `FLASK_ENV`: Flask environment (development/production)

## OAuth Configuration

1. Register your application at https://www.anaf.ro/InregOauth
2. Select service: **E-Factura** (critical!)
3. Set callback URL: `https://your-domain.com/anaf/callback`
4. Copy Client ID and Client Secret
5. Configure in admin panel: `/admin/anaf-oauth`
6. Users authenticate via `/anaf/status`

## License

Proprietary
