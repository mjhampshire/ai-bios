"""FastAPI application entry point for AI Bio service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bios.api import router as bio_router

app = FastAPI(
    title="TWC AI Bios",
    description="AI-powered customer bio generation service for retail clienteling",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "twc-ai-bios"}


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with service info."""
    return {
        "service": "TWC AI Bios",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Include routers
app.include_router(bio_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
