from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from backend.core.config import settings
from backend.core.logging import setup_logging, logger
from backend.db.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger.info("finagent.startup", env=settings.app_env, llm=settings.llm_provider)
    await create_tables()
    logger.info("finagent.db_ready")
    yield
    # Shutdown
    logger.info("finagent.shutdown")


app = FastAPI(
    title="FinAgent API",
    description="Autonomous Finance Operations — Multi-Agent Invoice Processing Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
from backend.api.routes.invoices import router as invoices_router
from backend.api.routes.vendors import router as vendors_router
from backend.api.routes.reports import router as reports_router

app.include_router(invoices_router, prefix="/api/v1/invoices", tags=["Invoices"])
app.include_router(vendors_router, prefix="/api/v1/vendors", tags=["Vendors"])
app.include_router(reports_router, prefix="/api/v1/reports", tags=["Reports"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "FinAgent",
        "status": "running",
        "version": "0.1.0",
        "llm_provider": settings.llm_provider,
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}