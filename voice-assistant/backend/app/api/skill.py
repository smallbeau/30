from fastapi import APIRouter

from app.api.deps import get_engine

router = APIRouter(tags=["skill"])


@router.get("/skills")
def list_skills():
    engine = get_engine()
    return [
        {"name": s.name, "triggers": s.triggers, "description": s.description}
        for s in engine.matcher.skills
    ]