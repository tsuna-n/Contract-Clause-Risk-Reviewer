"""HTTP layer — one module per group of endpoints.

``api_router`` collects them all so ``app/main.py`` mounts a single router,
the same way an Express app mounts ``routes/index.js``.
"""

from fastapi import APIRouter

from app.routes import auth, contracts, evaluate, health, playbook

api_router = APIRouter()

for module in (health, auth, contracts, playbook, evaluate):
    api_router.include_router(module.router)

__all__ = ["api_router"]
