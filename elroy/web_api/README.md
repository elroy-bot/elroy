# Elroy Web API

This is a web-accessible API for Elroy, providing similar functionality to the Python API in `elroy.api`.

## Features

- RESTful API endpoints for all Elroy functionality
- Authentication with JWT tokens
- Streaming responses for message processing
- File upload for document ingestion
- OpenAPI documentation

## Installation

### Option 1: Direct Installation

1. Install the required dependencies:

```bash
# Using pip
pip install -r elroy/web_api/requirements.txt

# Using uv (recommended)
uv pip install -e ".[web-api]"
```

2. Generate a secret key and set up environment variables:

```bash
# Generate a secret key
./elroy/web_api/generate_secret_key.py

# Set the environment variable
export ELROY_API_SECRET_KEY="your-generated-secret-key"  # For JWT token generation

# Alternatively, you can create a .env file
./elroy/web_api/generate_secret_key.py --env > .env
```

You can also copy the .env.example file and modify it:

```bash
cp elroy/web_api/.env.example elroy/web_api/.env
# Then edit the .env file with your preferred settings
```

### Option 2: Using Docker

1. Build and run using Docker Compose:

```bash
cd elroy/web_api
docker-compose up --build
```

This will start both the API server and a PostgreSQL database with the pgvector extension.

### Option 3: Install as a Package

1. Install the package with the web-api dependencies:

```bash
# Using pip
pip install -e ".[web-api]"

# Using uv (recommended)
uv pip install -e ".[web-api]"
```

2. Run the server using the installed command:

```bash
# Using the dedicated command
elroy_web_api

# Or using the Elroy CLI
elroy web-api run
```

## Running the API Server

### Option 1: Using the run.py script

You can run the API server using the provided run.py script:

```bash
python -m elroy.web_api.run
```

Or directly:

```bash
./elroy/web_api/run.py
```

### Option 2: Using the Elroy CLI

The API server can be run using the Elroy CLI:

```bash
elroy web-api run
```

This command is available after installing Elroy.

### Command Line Options

- `--host`: Host to bind the server to (default: 127.0.0.1)
- `--port`: Port to bind the server to (default: 8000)
- `--reload`: Enable auto-reload on code changes
- `--debug`: Enable debug mode
- `--workers`: Number of worker processes (default: 1)

Example:

```bash
python -m elroy.web_api.run --host 0.0.0.0 --port 8080 --debug
```

## API Documentation

Once the server is running, you can access the OpenAPI documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Authentication

1. Create a user:

```bash
curl -X POST "http://localhost:8000/users" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "password123"}'
```

2. Get an access token:

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=password123"
```

3. Use the token in subsequent requests:

```bash
curl -X GET "http://localhost:8000/goals" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## API Endpoints

### Goals

- `POST /goals`: Create a new goal
- `GET /goals`: Get all active goal names
- `GET /goals/{goal_name}`: Get a goal by name
- `POST /goals/{goal_name}/status`: Add a status update to a goal
- `POST /goals/{goal_name}/complete`: Mark a goal as completed

### Memories

- `POST /memories`: Create a new memory
- `POST /memories/query`: Query memories using semantic search
- `POST /memories/remember`: Alias for create_memory

### Messages

- `POST /messages`: Send a message to the assistant and get a response
- `POST /messages/stream`: Send a message to the assistant and stream the response
- `POST /messages/record`: Record a message into context without generating a reply
- `POST /messages/context/refresh`: Compress context messages and record a memory
- `GET /messages/context/refresh-if-needed`: Check if context refresh is needed and perform it if necessary
- `GET /messages/persona`: Get the current persona

### Documents

- `POST /documents/ingest`: Ingest a document into the assistant's memory
- `POST /documents/ingest-dir`: Ingest a directory of documents into the assistant's memory
- `POST /documents/upload`: Upload a file and ingest it into the assistant's memory

## Example Usage

### Creating a Goal

```bash
curl -X POST "http://localhost:8000/goals" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "goal_name": "Learn FastAPI",
    "strategy": "Study the documentation and build a sample project",
    "description": "Learn how to use FastAPI to build web APIs",
    "end_condition": "Complete a working API project",
    "time_to_completion": "7 DAYS",
    "priority": 1
  }'
```

### Sending a Message

```bash
curl -X POST "http://localhost:8000/messages" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Tell me about FastAPI",
    "enable_tools": true
  }'
```

### Ingesting a Document

```bash
curl -X POST "http://localhost:8000/documents/ingest" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "/path/to/document.txt",
    "force_refresh": false
  }'
```

## Security Considerations

In a production environment, make sure to:

1. Set a strong `ELROY_API_SECRET_KEY` environment variable
2. Use HTTPS for all communications
3. Implement proper user management and authentication
4. Consider rate limiting to prevent abuse
5. Regularly update dependencies to address security vulnerabilities
