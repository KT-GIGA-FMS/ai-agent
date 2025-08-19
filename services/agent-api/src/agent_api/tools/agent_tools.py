import json, os, datetime as dt
from langchain.tools import tool

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
with open(os.path.join(DATA_DIR, "car_models.json")) as f:
    MODELS = {m["id"]: m for m in json.load(f)}
with open(os.path.join(DATA_DIR, "cars.json")) as f:
    CARS = json.load(f)

# 메모리 내 임시 예약 저장
RESV: list[dict] = []

def _overlap(a1, a2, b1, b2):
    return not (a2 <= b1 or b2 <= a1)  # [start,end)

def _join_car(car: dict) -> dict:
    m = MODELS.get(car["car_model_id"])
    return {
        **car,
        "car_model_id": m["id"],
        "car_model_name": m["name"],
        "car_model_url": m.get("url"),
        "car_model_fuel_type": m.get("fuel_type"),
        "car_model_fuel_efficiency": m.get("fuel_efficiency"),
    }

@tool
def check_availability(from_time: str, to_time: str, fuel_type: str|None=None, car_type: str|None=None) -> list:
    """로컬 JSON에서 차량 가용성 확인 (ISO8601)."""
    s = dt.datetime.fromisoformat(from_time.replace("Z","+00:00"))
    e = dt.datetime.fromisoformat(to_time.replace("Z","+00:00"))
    cand = [c for c in CARS if c["status"]=="available"]
    if fuel_type: cand = [c for c in cand if (c.get("fuel_type") or "").lower()==fuel_type.lower()]
    if car_type: cand = [c for c in cand if (c.get("car_type") or "").lower()==car_type.lower()]
    free = []
    for c in cand:
        conflict = any(r["status"] in ("confirmed","in_progress")
                       and r["vehicle_id"]==c["id"]
                       and _overlap(s,e,r["start_at"],r["end_at"]) for r in RESV)
        if not conflict:
            free.append(_join_car(c))
    return free

@tool
def create_reservation(user_id: str, vehicle_id: str, from_time: str, to_time: str, idem_key: str|None=None) -> dict:
    """로컬 메모리에 예약 생성."""
    s = dt.datetime.fromisoformat(from_time.replace("Z","+00:00"))
    e = dt.datetime.fromisoformat(to_time.replace("Z","+00:00"))
    if idem_key:
        ex = next((r for r in RESV if r["id"]==idem_key), None)
        if ex: return ex
    # vehicle 존재/상태 체크
    car = next((c for c in CARS if c["id"]==vehicle_id), None)
    if not car: return {"error":"not_found"}
    if car["status"]!="available": return {"error":"not_available"}
    # 겹침 체크
    for r in RESV:
        if r["vehicle_id"]==vehicle_id and r["status"] in ("confirmed","in_progress") and _overlap(s,e,r["start_at"],r["end_at"]):
            return {"error":"conflict"}
    rid = idem_key or f"r_{len(RESV)+1}"
    res = {
        "id": rid, "vehicle_id": vehicle_id, "user_id": user_id,
        "start_at": s, "end_at": e, "status":"confirmed", "created_at": dt.datetime.utcnow()
    }
    RESV.append(res)
    # 직렬화-friendly로 변환
    out = {**res, "start_at": res["start_at"].isoformat(), "end_at": res["end_at"].isoformat(),
           "created_at": res["created_at"].isoformat()}
    return out
