"""
FastAPI Application Entry Point.

- CORS middleware for frontend communication
- Static file serving for frontend (local dev only)
- Router registration (auth, admin, teacher, student)
- Health check endpoint
- Railway deployment ready
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse
import os

from app.routers import auth, admin, teacher, student
from app.database import engine, Base

# Create all database tables (development convenience)
# In production, use Alembic migrations instead
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not create tables on startup: {e}")

# ── APP INSTANCE ──

app = FastAPI(
    title="Attendance Management System",
    description="A role-based REST API for managing attendance with Admin, Teacher, and Student roles.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS MIDDLEWARE ──
# Allow frontend to communicate with the API
# Set ALLOWED_ORIGINS env var in Railway dashboard (comma-separated)
# Example: https://your-frontend.netlify.app,https://yourdomain.com
_allowed_origins = os.environ.get("ALLOWED_ORIGINS", "*")
if _allowed_origins == "*":
    _origins_list = ["*"]
    _allow_creds = False  # credentials=True is invalid with origin=*
else:
    _origins_list = [o.strip() for o in _allowed_origins.split(",") if o.strip()]
    _allow_creds = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins_list,
    allow_credentials=_allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REGISTER ROUTERS ──

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teacher.router)
app.include_router(student.router)

# ── SERVE FRONTEND STATIC FILES ──
# Mount CSS/JS assets so HTML pages can reference them
# On Railway (backend-only deploy), frontend folder won't exist — that's OK

frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "frontend")
frontend_path = os.path.normpath(frontend_path)
_frontend_exists = os.path.exists(frontend_path)

if _frontend_exists:
    # Mount CSS and JS subdirectories as static
    css_path = os.path.join(frontend_path, "css")
    js_path = os.path.join(frontend_path, "js")
    if os.path.exists(css_path):
        app.mount("/css", StaticFiles(directory=css_path), name="css")
    if os.path.exists(js_path):
        app.mount("/js", StaticFiles(directory=js_path), name="js")


# ── ROOT ENDPOINT ──
@app.get("/", tags=["General"])
def root():
    """Serve frontend homepage if available, otherwise return API info."""
    if _frontend_exists:
        index_file = os.path.join(frontend_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file, media_type="text/html")
    return {
        "message": "AMS API is running",
        "docs": "/docs",
        "health": "/health",
        "version": "2.0.0",
    }


# ── SERVE FRONTEND HTML PAGES ──
# Each HTML file is served at its own clean URL
# Only registered if frontend folder exists (local dev)

def _serve_html(filename: str):
    """Helper: serve an HTML file from the frontend folder."""
    file_path = os.path.join(frontend_path, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")
    return {"error": "Page not found", "detail": f"{filename} is not available on this server."}

if _frontend_exists:
    @app.get("/index.html", tags=["Frontend"], include_in_schema=False)
    def serve_index():
        return _serve_html("index.html")

    @app.get("/login.html", tags=["Frontend"], include_in_schema=False)
    def serve_login():
        return _serve_html("login.html")

    @app.get("/signup.html", tags=["Frontend"], include_in_schema=False)
    def serve_signup():
        return _serve_html("signup.html")

    @app.get("/about.html", tags=["Frontend"], include_in_schema=False)
    def serve_about():
        return _serve_html("about.html")

    @app.get("/admin-dashboard.html", tags=["Frontend"], include_in_schema=False)
    def serve_admin_dashboard():
        return _serve_html("admin-dashboard.html")

    @app.get("/teacher-dashboard.html", tags=["Frontend"], include_in_schema=False)
    def serve_teacher_dashboard():
        return _serve_html("teacher-dashboard.html")

    @app.get("/student-dashboard.html", tags=["Frontend"], include_in_schema=False)
    def serve_student_dashboard():
        return _serve_html("student-dashboard.html")

    @app.get("/static/{filename}", tags=["Frontend"], include_in_schema=False)
    def serve_static_html(filename: str):
        """Backward-compatible: /static/page.html → serve page.html"""
        file_path = os.path.join(frontend_path, filename)
        if os.path.exists(file_path) and filename.endswith(".html"):
            return FileResponse(file_path, media_type="text/html")
        return RedirectResponse(url=f"/{filename}")


# ── HEALTH CHECK ──

@app.get("/health", tags=["General"])
def health_check():
    """Health check endpoint — useful for deployment monitoring."""
    return {
        "status": "healthy",
        "service": "Attendance Management System API",
        "version": "2.0.0",
    }
