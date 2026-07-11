from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api import chat, knowledge, memory, skill, voice
from app.config import get_settings

settings = get_settings()
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(skill.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(knowledge.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(voice.router, prefix="/api", dependencies=[Depends(verify_token)])
app.include_router(memory.router, prefix="/api", dependencies=[Depends(verify_token)])


@app.get("/health")
def health():
    return {"ok": True}