"""API v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import auth, health
from app.domains.action.api import router as action_router
from app.domains.integration.api import router as integration_router
from app.domains.knowledge.api import router as knowledge_router
from app.domains.rca.api import router as rca_router
from app.domains.trigger.api import router as trigger_router
from app.domains.workflow.api import router as workflow_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(trigger_router)
api_router.include_router(workflow_router)
api_router.include_router(rca_router)
api_router.include_router(action_router)
api_router.include_router(integration_router)
api_router.include_router(knowledge_router)
