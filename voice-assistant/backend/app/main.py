import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api import chat, knowledge, memory, skill, voice
from app.config import get_settings
from app.database.mysql import init_tables

settings = get_settings()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voice-assistant")

app = FastAPI(title=settings.app_name)

_bearer = HTTPBearer(auto_error=False)


def verify_token(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if settings.api_key:
        if cred is None or cred.credentials != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid api key",
            )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_server_header(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = time.monotonic() - start
    response.headers["X-Process-Time"] = f"{elapsed:.3f}"
    response.headers["Server"] = "voice-assistant/1.0"
    logger.info("%s %s %s %.3fs", request.method, request.url.path, response.status_code, elapsed)
    return response


app.include_router(chat.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(skill.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(knowledge.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(voice.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(memory.router, prefix="/api", dependencies=[Depends(verify_token)])


@app.on_event("startup")
def startup():
    init_tables()
    logger.info("MySQL tables initialized")


@app.get("/health")
def health():
    return {"ok": True, "version": "1.0.0", "service": settings.app_name}