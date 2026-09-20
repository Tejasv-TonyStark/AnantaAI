from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import admin, agents, auth, users, web
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=3, socket_timeout=3
    )
    yield
    app.state.redis.close()
    engine.dispose()


app = FastAPI(title="Sudarshan", version="0.1.0", lifespan=lifespan)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(agents.router, prefix="/agents", tags=["agents"])
app.include_router(web.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Default validation errors echo input, which may contain a password.
    errors = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


@app.get("/health")
def health_check(request: Request) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        request.app.state.redis.ping()
    except (SQLAlchemyError, RedisError):
        raise HTTPException(status_code=503, detail="A required service is unavailable") from None
    return {"status": "healthy", "service": "Sudarshan"}
