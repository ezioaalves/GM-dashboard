"""Campaign workflow route package."""
from fastapi import APIRouter

from .arcs import router as arcs_router
from .context import router as context_router
from .ideas.router import router as ideas_router
from .proposals import router as proposals_router
from .truths import router as truths_router

router = APIRouter()
router.include_router(arcs_router)
router.include_router(ideas_router)
router.include_router(truths_router)
router.include_router(context_router)
router.include_router(proposals_router)
