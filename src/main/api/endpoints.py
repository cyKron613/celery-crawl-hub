import fastapi

from src.main.api.crawler.crawler_router import router as crawler_router
from src.main.api.logs.logs_router import router as logs_router
# from src.main.api.redis_cache.redis_router import router as redis_router

router = fastapi.APIRouter()

# router.include_router(router=redis_router)
router.include_router(router=crawler_router)
router.include_router(router=logs_router)

