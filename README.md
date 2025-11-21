# eFactura Gateway

A containerized SaaS application for Romanian accountants and business owners to connect their ANAF (National Tax Agency) accounts via OAuth, manage multiple companies, sync invoices, and provide API access.

## Features

- OAuth integration with ANAF
- Multi-company support (1 User → Many Companies)
- Automatic invoice synchronization from ANAF
- XML to JSON invoice parsing
- Company-scoped API keys
- Modern dashboard with Volt-style UI

## Quick Start

1. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```

2. Build and run with Docker Compose:
   ```bash
   docker-compose up --build
   ```

3. Access the application at `http://localhost:8000`

## Project Structure

- `app/` - Main application code
- `migrations/` - Database migrations
- `Dockerfile` - Container definition
- `docker-compose.yml` - Multi-container setup
- `entrypoint.sh` - Startup script with DB wait and migrations

## Database Models

- **User**: Account holders
- **AnafOAuthConfig**: OAuth credentials per user
- **AnafToken**: ANAF access/refresh tokens
- **Company**: Companies (CUIs) linked to users
- **ApiKey**: Company-scoped API keys
- **Invoice**: Synced invoices with XML and JSON content

## API Endpoints

- `GET /api/v1/invoices` - Retrieve invoices (requires `X-API-KEY` header)

## Development

Run migrations manually:
```bash
docker-compose exec web flask db migrate -m "Description"
docker-compose exec web flask db upgrade
```

## License

Proprietary

