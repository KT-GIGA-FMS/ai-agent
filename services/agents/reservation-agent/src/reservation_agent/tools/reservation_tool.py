import datetime as dt
import json
import os

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


def _find_car_by_name_or_id(identifier: str) -> dict | None:
    """차량 이름 또는 ID로 차량 찾기"""
    identifier = identifier.lower().strip()

    # ID로 직접 매칭
    for car in CARS:
        if car["id"].lower() == identifier:
            return car

    # 차량 이름으로 매칭
    for car in CARS:
        model = MODELS.get(car["car_model_id"])
        if model and model["name"].lower() == identifier:
            return car

    # 부분 매칭 (예: "avante" -> "Hyundai Avante")
    for car in CARS:
        model = MODELS.get(car["car_model_id"])
        if model and identifier in model["name"].lower():
            return car

    return None


@tool
def check_availability(
    from_time: str,
    to_time: str,
    fuel_type: str | None = None,
    car_type: str | None = None,
) -> list:
    """로컬 JSON에서 차량 가용성 확인 (ISO8601)."""
    try:
        s = dt.datetime.fromisoformat(from_time.replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(to_time.replace("Z", "+00:00"))

        if s >= e:
            return {"error": "시작 시간이 종료 시간보다 늦을 수 없습니다."}

        cand = [c for c in CARS if c["status"] == "available"]
        if fuel_type:
            cand = [
                c
                for c in cand
                if (c.get("fuel_type") or "").lower() == fuel_type.lower()
            ]
        if car_type:
            cand = [
                c for c in cand if (c.get("car_type") or "").lower() == car_type.lower()
            ]

        free = []
        for c in cand:
            conflict = any(
                r["status"] in ("confirmed", "in_progress")
                and r["vehicle_id"] == c["id"]
                and _overlap(s, e, r["start_at"], r["end_at"])
                for r in RESV
            )
            if not conflict:
                free.append(_join_car(c))

        return {
            "available_cars": free,
            "count": len(free),
            "time_range": f"{from_time} ~ {to_time}",
        }
    except ValueError as e:
        return {"error": f"시간 형식 오류: {str(e)}"}
    except Exception as e:
        return {"error": f"가용성 확인 중 오류 발생: {str(e)}"}


@tool
def create_reservation(
    user_id: str,
    vehicle_id: str,
    from_time: str,
    to_time: str,
    idem_key: str | None = None,
) -> dict:
    """로컬 메모리에 예약 생성."""
    try:
        # 차량 찾기 (ID 또는 이름으로)
        car = _find_car_by_name_or_id(vehicle_id)
        if not car:
            return {
                "error": "차량을 찾을 수 없습니다",
                "available_vehicles": [
                    {
                        "id": c["id"],
                        "name": MODELS.get(c["car_model_id"], {}).get(
                            "name", "Unknown"
                        ),
                    }
                    for c in CARS[:5]
                ],
            }

        # 실제 차량 ID 사용
        actual_vehicle_id = car["id"]

        s = dt.datetime.fromisoformat(from_time.replace("Z", "+00:00"))
        e = dt.datetime.fromisoformat(to_time.replace("Z", "+00:00"))

        if s >= e:
            return {"error": "시작 시간이 종료 시간보다 늦을 수 없습니다."}

        # 중복 예약 체크
        if idem_key:
            ex = next((r for r in RESV if r["id"] == idem_key), None)
            if ex:
                return {
                    "success": True,
                    "reservation": ex,
                    "message": "이미 존재하는 예약입니다.",
                }

        # 차량 상태 체크
        if car["status"] != "available":
            return {"error": f"차량이 현재 사용 불가능합니다. 상태: {car['status']}"}

        # 시간 충돌 체크
        for r in RESV:
            if (
                r["vehicle_id"] == actual_vehicle_id
                and r["status"] in ("confirmed", "in_progress")
                and _overlap(s, e, r["start_at"], r["end_at"])
            ):
                return {"error": "해당 시간에 이미 예약이 있습니다."}

        # 예약 생성
        rid = idem_key or f"r_{len(RESV)+1}"
        res = {
            "id": rid,
            "vehicle_id": actual_vehicle_id,
            "user_id": user_id,
            "start_at": s,
            "end_at": e,
            "status": "confirmed",
            "created_at": dt.datetime.utcnow(),
            "vehicle_name": MODELS.get(car["car_model_id"], {}).get("name", "Unknown"),
        }
        RESV.append(res)

        # 직렬화-friendly로 변환
        out = {
            **res,
            "start_at": res["start_at"].isoformat(),
            "end_at": res["end_at"].isoformat(),
            "created_at": res["created_at"].isoformat(),
        }

        return {
            "success": True,
            "reservation": out,
            "message": f"예약이 성공적으로 완료되었습니다. 차량: {res['vehicle_name']}",
        }

    except ValueError as e:
        return {"error": f"시간 형식 오류: {str(e)}"}
    except Exception as e:
        return {"error": f"예약 생성 중 오류 발생: {str(e)}"}


@tool
def list_available_cars() -> dict:
    """사용 가능한 모든 차량 목록 조회"""
    try:
        available_cars = []
        for car in CARS:
            if car["status"] == "available":
                model = MODELS.get(car["car_model_id"], {})
                available_cars.append(
                    {
                        "id": car["id"],
                        "name": model.get("name", "Unknown"),
                        "fuel_type": model.get("fuel_type", "Unknown"),
                        "fuel_efficiency": model.get("fuel_efficiency", "Unknown"),
                        "car_type": car.get("car_type", "Unknown"),
                    }
                )

        return {"available_cars": available_cars, "count": len(available_cars)}
    except Exception as e:
        return {"error": f"차량 목록 조회 중 오류 발생: {str(e)}"}
