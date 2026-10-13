# ChatHub

ChatHub is a full-stack real-time messaging platform built with a Python FastAPI backend and a Next.js frontend. The application is designed around secure communication, JWT-based authentication, and live collaboration features such as direct messaging, group chat, file uploads, and socket-driven updates.

The project is structured as a monorepo with separate backend and frontend services, making it easy to develop, deploy, and scale each layer independently.

## Overview

This repository combines:

- A Python backend for APIs, authentication, real-time socket events, data persistence, and file serving
- A modern React/Next.js client for the user interface and client-side state management
- Support for secure message exchange, active user tracking, and session-based communication patterns

The backend is centered around FastAPI and Socket.IO, while the frontend uses Next.js, TypeScript, Tailwind CSS, and React components to deliver a responsive UI.

## Architecture

The application follows a classic modular service architecture:

- Backend handles server-side authentication, persistence, real-time messaging, file handling, and API endpoints
- Frontend consumes the API and socket events to render the chat experience and manage local state
- Environment variables define secret keys, database configuration, and deployment settings

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- Socket.IO
- SQLAlchemy
- PostgreSQL-compatible database access
- JWT for authentication
- Cryptography utilities for secure message handling
- Uvicorn for ASGI deployment

### Frontend
- Next.js
- React 19
- TypeScript
- Tailwind CSS
- Framer Motion
- Zustand for state management
- Socket.IO client
- Lucide icons and Radix UI primitives

## Repository Structure

```text
ChatHub/
├── backend/
│   ├── auth_utils2.py
│   ├── config/
│   ├── crypto_utils2.py
│   ├── db/
│   ├── logs/
│   ├── main_new.py
│   ├── requirements.txt
│   ├── rest_api.py
│   ├── routes/
│   ├── socket_events.py
│   ├── uploads/
│   ├── utils.py
│   └── venv/
├── frontend/
│   └── chat-app/
│       ├── app/
│       ├── components/
│       ├── hooks/
│       ├── lib/
│       ├── public/
│       ├── styles/
│       ├── package.json
│       ├── next.config.mjs
│       ├── next.config.ts
│       ├── tsconfig.json
│       └── ...
├── .gitignore
├── README.md
└── ...
```

## Backend Responsibilities

The backend directory contains the server-side runtime and business logic. Key responsibilities include:

- JWT validation and user authentication
- REST API endpoint registration
- Real-time Socket.IO event handling
- Database connectivity and query orchestration
- Secure encryption utilities
- File upload handling and static serving
- Health monitoring and operational logging

### Main backend files

- `backend/main_new.py`: application bootstrap, CORS settings, static filesystem mount, and ASGI startup configuration
- `backend/rest_api.py`: REST endpoint definitions and API route wiring
- `backend/socket_events.py`: WebSocket and real-time event registration
- `backend/auth_utils2.py`: authentication helper logic for validating tokens and user sessions
- `backend/crypto_utils2.py`: cryptographic helpers used for secure handling of secrets and payloads
- `backend/db/`: database connection and persistence logic
- `backend/routes/`: route modules and endpoint registration structure
- `backend/uploads/`: file storage for uploaded assets

## Frontend Responsibilities

The frontend application is a Next.js app focused on UI, state flow, and real-time interaction with the backend. It includes:

- app routing and layout composition
- reusable UI components
- shared client-side utilities and hooks
- socket connection management
- state synchronization with backend events
- chat views, message rendering, and interactive actions

### Main frontend files

- `frontend/chat-app/app/`: Next.js pages and application shell
- `frontend/chat-app/components/`: reusable UI building blocks
- `frontend/chat-app/lib/`: shared logic and helper functions
- `frontend/chat-app/hooks/`: custom hooks for client behavior
- `frontend/chat-app/styles/`: global CSS and Tailwind-based design tokens

## Core Features

- Real-time messaging using Socket.IO
- Direct messaging and group chat support
- JWT-based user authentication
- Secure encrypted message workflows
- File upload and file serving support
- Active user tracking and session management
- REST API documentation via FastAPI Swagger UI
- Responsive web interface built with modern frontend tooling

## Authentication Model

The backend is designed to validate a JWT token supplied by the frontend. In the current implementation, the server expects a token from the external identity provider, and the frontend passes it during socket connection or HTTP request authorization.

Typical flow:

1. User authenticates through the identity provider
2. Frontend receives JWT token
3. Client sends token in auth payload or Authorization header
4. Backend validates token and authorizes user actions

This pattern allows secure session-based access while keeping the API surface protected from unauthorized use.

## Security Notes

This project includes security-aware patterns, including:

- environment variable storage for sensitive configuration
- JWT-based request validation
- CORS configuration for restricted frontend origins
- secure handling of cryptographic material
- file uploads stored under controlled backend directories

Important production guidance:

- Never commit `.env` files
- Store secrets in a secure deployment environment
- Restrict CORS origins in production
- Use HTTPS and a reverse proxy in live deployments
- Rotate JWT and encryption secrets regularly

## Environment Variables

Create environment files for the backend and frontend as required by your deployment environment.

Example backend `.env` values:

```env
PORT=8000
SUPABASE_JWT_SECRET=your_jwt_secret
DATABASE_URL=postgresql://username:password@localhost:5432/chatdb
```

Example frontend environment values may include:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SOCKET_URL=http://localhost:8000
```

## Getting Started

### Prerequisites

Before running the project, ensure you have:

- Python 3.11 or newer
- Node.js 18+ and npm
- Access to PostgreSQL or a compatible database service
- A configured JWT provider such as Supabase

### 1. Backend setup

```bash
cd backend
python -m venv venv
```

On Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend:

```bash
python main_new.py
```

The backend will typically be available at:

- http://localhost:8000
- http://localhost:8000/docs
- http://localhost:8000/health
- ws://localhost:8000/socket.io

### 2. Frontend setup

```bash
cd frontend/chat-app
npm install
npm run dev
```

The frontend typically runs at:

- http://localhost:3000

## Available API Endpoints

The backend exposes a FastAPI-based API surface. At minimum, the application includes:

- `/` — API metadata
- `/health` — service health check
- `/docs` — Swagger documentation
- `/redoc` — Redoc documentation
- `/uploads` — uploaded content serving endpoint
- Socket.IO path: `/socket.io`

## Socket.IO Event Model

The real-time backend is configured to handle live communication events such as:

- `connect`
- `disconnect`
- `create_room`
- `join_request`
- `enter_chat`
- `leave_chat`
- `send_message`
- `load_messages`
- administrative chat member actions

These events allow clients to enter rooms, send encrypted messages, receive updates, and maintain presence state in real time.

## Recommended Development Workflow

1. Start the backend service
2. Start the frontend application
3. Configure environment variables securely
4. Use the FastAPI docs to validate APIs
5. Use browser tools to inspect real-time socket behavior
6. Keep secrets and generated artifacts out of version control

## Production Considerations

For deployment, consider the following:

- Set secure environment variables in the hosting environment
- Use a production-grade Postgres instance
- Put the backend behind a reverse proxy and TLS layer
- Run the frontend in a production build with optimized caching
- Keep uploads and logs in isolated, monitored storage locations
- Validate database migrations and authentication flow in staging before production rollout

## Git Hygiene

This repository includes `.gitignore` rules for common generated artifacts such as:

- `.env` files
- Python caches
- Node modules
- `.next` build output
- `venv` directories
- logs and local editor metadata

## Contributing

When contributing to the project:

- keep backend and frontend changes logically separated
- document environment requirements when adding new dependencies
- validate API and UI behavior before merging
- avoid committing secrets, local virtual environments, or generated build output

## Summary

ChatHub is a secure, real-time chat platform built from a modular backend and a modern frontend. It demonstrates core architectural practices for full-stack application development, including API-driven backend services, Socket.IO communication, JWT-based security, and modern UI development with Next.js.

This project is suitable for learning full-stack integration, real-time messaging systems, and secure chat-service design.

