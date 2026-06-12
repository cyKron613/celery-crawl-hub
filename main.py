import os
import sys
import pathlib

def _check_env_file():
    """检查 .env 文件是否存在或关键环境变量已注入（Docker Compose 场景）。"""
    project_root = pathlib.Path(__file__).resolve().parent
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    # 如果 .env 文件存在，直接通过
    if env_file.exists():
        return
    
    # Docker Compose 通过 env_file 指令注入环境变量，容器内没有物理 .env 文件
    # 检查关键环境变量是否已注入
    critical_vars = ["POSTGRES_HOST", "CELERY_BROKER_URL", "BACKEND_SERVER_HOST"]
    if all(os.getenv(var) for var in critical_vars):
        return  # 环境变量已注入（Docker Compose 场景）
    
    # 既没有 .env 文件，也没有关键环境变量
    print("=" * 60)
    print("❌ 未找到 .env 文件，应用无法启动。")
    print()
    print("请先复制环境变量模板：")
    print(f"  cp .env.example .env")
    print()
    if env_example.exists():
        print(f"模板文件位于: {env_example}")
    print("按需修改后重新启动即可。")
    print("=" * 60)
    sys.exit(1)

_check_env_file()

import fastapi
import fastapi_cdn_host
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse, HTMLResponse
from fastapi import Request

from src.main.api.endpoints import router as api_endpoint_router
from src.main.config.handler.life_circle_handler import (
    execute_backend_server_event_handler, terminate_backend_server_event_handler,
    execute_another_db_connection_event_handler, terminate_another_db_connection_event_handler
)
from src.main.config.manager import settings
from src.main.config.handler.global_exception_handler import register_exception
from src.main.config.handler.api_access_handler import register_middleware


def initialize_backend_application() -> fastapi.FastAPI:
    """
    初始化后台应用
    :return:
    """

    app = fastapi.FastAPI(**settings.gset_backend_app_attributes)  # type: ignore

    register_exception(app)
    register_middleware(app)


    # # 添加Redis缓存中间件（在其他中间件之前）
    # from src.main.config.middleware.redis_cache_middleware import add_redis_cache_middleware
    # add_redis_cache_middleware(
    #     app=app, 
    #     cache_time=1800,  # 默认缓存30分钟
    #     exclude_paths=[
    #         "/api-doc.html", "/api-redoc.html", "/api.json", "/health", "/api-redoc.html", 
    #         "/login", "/download-openapi-json", "/download-openapi-endpoint-json", "/ai-empower-api-doc.html", "/ai-empower-api.json", "/ai-empower-api-redoc.html"
    #         "/api/v1/oauth2", "/api/v1", "/ai-empower-api-doc.html"
    #     ],  # 排除不需要缓存的路径
    #     exclude_methods=["PUT", "DELETE", "PATCH"]  # 明确指定排除的方法，保留GET和POST
    # )

    from src.main.config.middleware.redis_cache_middleware import add_redis_cache_middleware

    add_redis_cache_middleware(
        app=app, 
        cache_time=1800,  # 默认缓存30分钟
        include_paths=[
            "/api/v1/algorithm/test"
        ],  # 只缓存指定的路径
        exclude_methods=["PUT", "DELETE", "PATCH"]  # 明确指定排除的方法，保留GET和POST
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.ALLOWED_METHODS,
        allow_headers=settings.ALLOWED_HEADERS,
    )

    app.add_event_handler(
        "startup",
        execute_backend_server_event_handler(backend_app=app),
    )
    app.add_event_handler(
        "shutdown",
        terminate_backend_server_event_handler(backend_app=app),
    )

    # # # # # 如果有其他数据库连接 需要维护新的持久化连接层
    # app.add_event_handler(
    #     "startup",
    #     execute_another_db_connection_event_handler(backend_app=app),
    # )
    # app.add_event_handler(
    #     "shutdown",
    #     terminate_another_db_connection_event_handler(backend_app=app),
    # )

    app.include_router(router=api_endpoint_router, prefix=settings.API_PREFIX)


    import login_html
    # Redirect root to login page
    LOGIN_HTML = login_html.LOGIN_HTML

    @app.get("/login", tags=["Auth FOR DOCS"])
    async def login_page():
        return HTMLResponse(content=LOGIN_HTML)

    # Login form submission handler
    @app.post("/login", tags=["Auth FOR DOCS"])
    async def login(request: Request):
        form_data = await request.form()
        username = form_data.get("username")
        password = form_data.get("password")
        # Authentication credentials (using the values from the environment settings)
        USERNAME = settings.DOCS_AUTH_USERNAME
        PASSWORD = settings.DOCS_AUTH_PASSWORD
        
        if username == USERNAME and password == PASSWORD:
            response = RedirectResponse(url=settings.DOCS_URL, status_code=303)
            response.set_cookie(key="auth", value="approved", httponly=True)
            return response
        else:
            # Return login page with an error message
            error_html = LOGIN_HTML.replace(
                '<form action="/login" method="post" id="loginForm">',
                '<div class="error-message">❌ 用户名或密码错误，请重试</div><form action="/login" method="post" id="loginForm">'
            )
            return HTMLResponse(content=error_html)

    # Redirect root to login page
    @app.get("/", tags=["Auth FOR DOCS"])
    async def root():
        return RedirectResponse(url="/login")

    # 修改Swagger UI的HTML模板，添加下载功能
    original_swagger_ui = app.routes[-1].endpoint

    async def custom_swagger_ui_html(*args, **kwargs):
        response = await original_swagger_ui(*args, **kwargs)
        if isinstance(response, HTMLResponse):
            html_content = response.body.decode('utf-8')
            return HTMLResponse(content=html_content)
        return response

    # 替换原来的Swagger UI路由
    for route in app.routes:
        if route.path == settings.DOCS_URL:
            route.endpoint = custom_swagger_ui_html
            break

    # 打补丁到FastAPI的文档页面
    fastapi_cdn_host.patch_docs(app)

    return app


backend_app: fastapi.FastAPI = initialize_backend_application()

if __name__ == "__main__":

    uvicorn.run(
        app="main:backend_app",
        host=settings.BACKEND_SERVER_HOST,
        port=settings.BACKEND_SERVER_PORT,
        reload=settings.DEBUG,
        workers=settings.BACKEND_SERVER_WORKERS,
        log_level=settings.LOGGING_LEVEL,
        lifespan="on"
    )
