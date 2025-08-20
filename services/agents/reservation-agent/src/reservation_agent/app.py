from fastapi import FastAPI, Response
from reservation_agent.core.db import healthcheck as db_ok
from reservation_agent.core.redis_client import healthcheck as redis_ok
from reservation_agent.core.config import settings

app = FastAPI(title="Reservation Agent API", version="0.1.0")

@app.get("/")
def root():
    return {"status": "ok", "service": "reservation-agent"}

@app.get("/livez")
def livez():
    return {"status": "alive"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/readyz")
def readyz(response: Response):
    missing_env = [k for k in ["DATABASE_URL", "REDIS_URL"] if not getattr(settings, k)]
    ok_db = db_ok()
    ok_redis = redis_ok()
    if missing_env or not (ok_db and ok_redis):
        response.status_code = 503
        return {"status": "not_ready", "missing_env": missing_env, "db_ok": ok_db, "redis_ok": ok_redis}
    return {"status": "ready"}