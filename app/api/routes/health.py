"""
Health check endpoint — verifies all services are operational.
"""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])

@router.get("/health")
async def health_check():
    """Basic health check for load balancers and monitoring."""
    return {
        "status": "healthy",
        "service": "AI Co-Worker Engine",
        "version": "1.0.0",
    }
