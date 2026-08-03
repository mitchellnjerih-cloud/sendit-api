# SendIt API

A RESTful backend API built with FastAPI for secure document management. The API allows users to register, authenticate, upload documents, search documents, enrich documents with weather information, and manage webhooks.

## Features

- User registration and login
- JWT authentication and authorization
- Role-based access control (Staff, Manager, Admin)
- Secure document upload
- Document versioning
- Search documents by filters
- Weather data enrichment using an external API
- Retrieve weather information for uploaded documents
- Register webhooks
- PostgreSQL database integration
- Rate limiting for API protection

## Technologies Used

- Python 3.12
- FastAPI
- SQLModel
- PostgreSQL
- SQLAlchemy
- JWT Authentication
- Passlib (bcrypt)
- HTTPX
- Aiofiles
- Docker Compose

## Project Structure

```
sendit-api/
├── database/
├── docs/
├── models/
├── screenshot/
├── services/
├── uploads/
├── auth.py
├── main.py
├── seeds.py
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

## Installation

1. Clone the repository:

```bash
git clone https://github.com/mitchellnjerih-cloud/sendit-api.git
cd sendit-api
```

2. Create and activate a virtual environment.

3. Install dependencies:

```bash
pip install -r requirements.txt
```

or

```bash
uv sync
```

4. Configure environment variables by creating a `.env` file.

Example:

```
DATABASE_URL=your_database_url
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
WEATHER_API_KEY=your_weather_api_key
```

5. Start PostgreSQL.

6. Run the application:

```bash
uvicorn main:app --reload
```

The API will be available at:

```
http://127.0.0.1:8000
```

Swagger documentation:

```
http://127.0.0.1:8000/docs
```

## API Endpoints

### Authentication

- POST `/register`
- POST `/login`

### Documents

- POST `/documents/upload`
- GET `/documents`
- GET `/documents/{document_id}`
- DELETE `/documents/{document_id}`
- POST `/documents/{document_id}/enrich`
- GET `/documents/{document_id}/weather`
- GET `/documents/search`

### Webhooks

- POST `/webhooks/register`

## Testing

The API was tested using the interactive Swagger UI available at:

```
/docs
```

Screenshots of successful endpoint tests are included in the `screenshot` folder.

## Documentation

Project documentation is available in the `docs` folder.

## Author

Mitchell Njeri