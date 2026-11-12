
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.shopping_sessions import (
    router as shopping_sessions_router,
)
from app.api.routes.products import router as products_router
from app.api.routes.recommendations import (
    router as recommendations_router,
)
from app.api.routes.comparison import router as comparison_router
from app.api.routes.intelligence import router as intelligence_router

from app.db.database import engine


app = FastAPI(
    title="SpendPilot AI API",
    description="AI-powered intelligent shopping assistant",
    version="0.1.0",
)


# Allow the local SpendPilot frontend to access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# Register API routers.
app.include_router(shopping_sessions_router)
app.include_router(products_router)
app.include_router(recommendations_router)
app.include_router(comparison_router)
app.include_router(intelligence_router)


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "SpendPilot AI API",
        "version": "0.1.0",
    }


@app.get("/ready", tags=["System"])
def readiness_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "database": "connected",
        }

    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "unavailable",
            },
        )
