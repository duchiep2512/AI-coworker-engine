"""AI Co-Worker Engine — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import logger
from app.api.routes import chat, sessions, health
from app.db.postgres.connection import init_postgres, close_postgres
from app.db.postgres.seed import seed_all
from app.db.postgres.connection import AsyncSessionLocal

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — connect/disconnect databases."""
    logger.info("=" * 60)
    logger.info("AI Co-Worker Engine starting up...")
    logger.info(f"   Environment: {settings.APP_ENV}")
    logger.info(f"   LLM Model:   {settings.GEMINI_MODEL}")
    logger.info(f"   FAISS Index:  {settings.FAISS_INDEX_DIR}")
    logger.info("=" * 60)

    # Initialize PostgreSQL and seed agents
    try:
        await init_postgres()
        logger.info("PostgreSQL tables created")
        
        async with AsyncSessionLocal() as db:
            await seed_all(db)
        logger.info("PostgreSQL seeded with agents")
        
        from app.db.agent_loader import clear_agent_cache
        clear_agent_cache()
        logger.info("Agent cache cleared")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed: {e}")
        logger.warning("   Running in fallback mode (hardcoded prompts)")

    yield  # App is running

    # Cleanup
    logger.info("Shutting down AI Co-Worker Engine...")
    try:
        await close_postgres()
    except Exception:
        pass
    try:
        from app.db.mongodb.connection import close_mongo
        await close_mongo()
    except Exception:
        pass

app = FastAPI(
    title="AI Co-Worker Engine",
    description=(
        "Powers virtual AI colleagues (NPCs) inside Edtronaut's Job Simulation platform. "
        "Simulation Takers collaborate with a CEO, CHRO, and Regional Manager "
        "to solve real business problems at Gucci Group."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", tags=["Root"], include_in_schema=False)
async def root():
    """Serve the frontend index.html."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "service": "AI Co-Worker Engine",
        "version": "1.0.0",
        "docs": "/docs",
        "simulation": "Gucci Group — HRM Talent & Leadership Development 2.0",
        "agents": ["CEO", "CHRO", "RegionalManager"],
    }
