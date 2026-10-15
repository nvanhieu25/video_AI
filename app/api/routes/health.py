from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": request.app.title}


@router.get("/ready")
def ready(request: Request) -> dict[str, str]:
    session = request.app.state.session_factory()
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database is not ready") from exc
    finally:
        session.close()
    return {"status": "ready"}
