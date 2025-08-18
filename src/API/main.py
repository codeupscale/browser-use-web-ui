from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import os
import uvicorn
from pathlib import Path

# Import API routers
from .Ai_Testing.routes import router as ai_testing_router
from src.websocket.websocket_manager import WebSocketManager

# Create FastAPI app
app = FastAPI(
    title="Browser Use AI Agent API",
    description="API for browser automation and AI agent tasks",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize WebSocket manager
manager = WebSocketManager()

# Set the WebSocket manager in the services
from .Ai_Testing.services import set_websocket_manager
set_websocket_manager(manager)

# Include API routers
app.include_router(ai_testing_router, prefix="/agent-api", tags=["AI Testing"])

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "browser-use-ai-agent"}

# Root endpoint that serves different content based on port
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # Get the port from the request
    port = request.url.port
    
    # If running on port 8000, redirect to Swagger docs
    if port == 8000:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Browser Use AI Agent - API Documentation</title>
            <meta http-equiv="refresh" content="0; url=/docs">
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; text-align: center; }
                .container { max-width: 800px; margin: 0 auto; }
                .button { display: inline-block; padding: 12px 24px; margin: 10px; 
                         background-color: #28a745; color: white; text-decoration: none; 
                         border-radius: 5px; }
                .button:hover { background-color: #1e7e34; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Browser Use AI Agent - API Documentation</h1>
                <p>Redirecting to Swagger documentation...</p>
                <a href="/docs" class="button">📚 Go to Swagger Docs</a>
                <a href="/redoc" class="button">📖 Go to ReDoc</a>
                <p><small>If you're not redirected automatically, click the links above.</small></p>
            </div>
        </body>
        </html>
        """
    
    # For port 7788, serve the browser testing interface
    else:
        index_path = static_path / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        else:
            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Browser Use AI Agent</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .container { max-width: 800px; margin: 0 auto; }
                    .button { display: inline-block; padding: 12px 24px; margin: 10px; 
                             background-color: #007bff; color: white; text-decoration: none; 
                             border-radius: 5px; }
                    .button:hover { background-color: #0056b3; }
                    .api-button { background-color: #28a745; }
                    .api-button:hover { background-color: #1e7e34; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 Browser Use AI Agent</h1>
                    <p>Welcome to the Browser Use AI Agent platform. Choose your interface:</p>
                    
                    <div>
                        <a href="http://localhost:7788" class="button">🎨 Web UI (Port 7788)</a>
                        <a href="http://localhost:8000/docs" class="button api-button">📚 API Documentation (Port 8000)</a>
                    </div>
                    
                    <h2>Available Services:</h2>
                    <ul>
                        <li><strong>Web UI:</strong> Interactive HTML interface for browser automation</li>
                        <li><strong>API:</strong> RESTful API endpoints for programmatic access</li>
                        <li><strong>Swagger Docs:</strong> Interactive API documentation</li>
                    </ul>
                </div>
            </body>
            </html>
            """

# API info endpoint
@app.get("/api/info")
async def api_info():
    return {
        "name": "Browser Use AI Agent API",
        "version": "1.0.0",
        "description": "API for browser automation and AI agent tasks",
        "endpoints": {
            "ui": "http://localhost:7788",
            "api_docs": "http://localhost:7788/docs",
            "health": "http://localhost:7788/health",
            "ai_testing": "http://localhost:7788/agent-api"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "src.API.main:app",
        host="0.0.0.0",
        port=7788,
        reload=True
    ) 