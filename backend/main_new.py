# main.py - Application Entry Point & Configuration
"""
CHAT APPLICATION ENTRY POINT
============================
This file initializes and runs the entire chat backend.

WHAT IT DOES:
1. Creates FastAPI app
2. Configures CORS for frontend connections
3. Imports Socket.IO server from socket_events.py
4. Wraps FastAPI with Socket.IO
5. Registers all event handlers and REST routes
6. Serves uploaded files
7. Starts the server

INTEGRATION WITH TEAMMATE'S LOGIN:
- Your teammate provides JWT tokens from Supabase after login
- This backend accepts those tokens via:
  * Socket.IO: auth={"token": jwt_token}
  * REST API: Authorization: Bearer {jwt_token}
"""
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

# Import our modular components
from socket_events import register_socket_events, sio, active_users
#rom rest_api import register_rest_routes
from utils import logger

# In main.py:
from rest_api import router as api_router

# ============================================================
# CONFIGURATION
# ============================================================

# Environment variables
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
PORT = int(os.getenv("PORT", 8000))

# File upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)




app = FastAPI(
    title="Chat Application API",
    description="Real-time E2E encrypted chat with Socket.IO",
    version="2.0.0",
    docs_url="/docs",      # Swagger UI: http://localhost:8000/docs
    redoc_url="/redoc"     # ReDoc: http://localhost:8000/redoc
)

# ============================================================
# CORS MIDDLEWARE

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # Development servers
        "http://localhost:3000",      # React (Create React App)
        "http://localhost:5173",      # Vite
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],      # Allows all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],      # Allows all headers (Authorization, etc.)
)

# ============================================================
# REGISTER REST API ROUTES
# ============================================================

app.include_router(api_router)
logger.info("[OK] REST API routes registered")

# DEBUG: Print all routes
print("\n=== REGISTERED ROUTES ===")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        print(f"  {route.methods} {route.path}")
print("=========================\n")

# ============================================================
# STATIC FILE SERVING
# ============================================================

# Serve uploaded files at /uploads
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
logger.info("[OK] Static file serving configured at /uploads")

# ============================================================
# SOCKET.IO INTEGRATION
# ============================================================

socket_app = socketio.ASGIApp(
    sio,                        # Socket.IO server from socket_events.py
    app,                        # FastAPI app
    socketio_path="/socket.io"  # WebSocket endpoint path
)

# ============================================================
# REGISTER SOCKET.IO EVENTS
# ============================================================

register_socket_events()
logger.info("[OK] Socket.IO events registered")

# ============================================================
# BASIC ENDPOINTS
# ============================================================

@app.get("/")
async def root():
    """
    Root endpoint - API information
    Access: http://localhost:8000/
    """
    return {
        "name": "Chat Application API",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",              # Swagger UI
            "redoc": "/redoc",            # Alternative docs
            "health": "/health",          # Health check
            "api": "/api",                # REST API base
            "socket_io": "/socket.io",    # WebSocket endpoint
            "uploads": "/uploads"         # Static files
        },
        "integration": {
            "authentication": "JWT Bearer tokens from Supabase",
            "socket_auth": "Pass token in auth object when connecting",
            "rest_auth": "Pass token in Authorization header"
        }
    }


@app.get("/health")
async def health():
    """
    Health check endpoint - shows server status
    Access: http://localhost:8000/health
    """
    return {
        "status": "healthy",
        "active_users": len(active_users),
        "total_sessions": sum(len(sids) for sids in active_users.values()),
        "upload_dir": str(UPLOAD_DIR),
        "upload_dir_exists": UPLOAD_DIR.exists()
    }


# ============================================================
# APPLICATION STARTUP
# ============================================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("="*60)
    logger.info("[OK] STARTING CHAT APPLICATION")
    logger.info("="*60)
    logger.info(f"[OK] Server: http://localhost:{PORT}")
    logger.info(f"[OK] Socket.IO: ws://localhost:{PORT}/socket.io")
    logger.info(f"[OK] API Docs: http://localhost:{PORT}/docs")
    logger.info(f"[OK] Health: http://localhost:{PORT}/health")
    logger.info(f"[OK] Uploads: {UPLOAD_DIR.absolute()}")
    logger.info("="*60)
    logger.info("[OK] Integration Guide:")
    logger.info("   1. Frontend gets JWT from Supabase login")
    logger.info("   2. Frontend connects with: io(url, { auth: { token } })")
    logger.info("   3. Backend validates token in connect() event")
    logger.info("="*60)
    
    # CRITICAL: Run socket_app (not app!)
    # socket_app = FastAPI + Socket.IO combined
    uvicorn.run(
        "main_new:socket_app",  # Must be socket_app!
        host="0.0.0.0",         # Listen on all interfaces
        port=PORT,
        reload=True,            # Auto-reload on code changes (dev only)
        log_level="info"
    )