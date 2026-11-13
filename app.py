# Google Flights를 스크래핑해 최저가 항공편을 조회하는 API (fast-flights 기반)
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query as Q
from fastapi.middleware.cors import CORSMiddleware
from fast_flights import FlightQuery, Passengers, create_query, get_flights
from fast_flights.exceptions import FlightsNotFound
import fast_flights.parser as _ffp


def _patched_parse_js(js: str):
    # ponytail: fast-flights 3.1.0 업스트림 버그 우회. 가격 미확정 itinerary는
    # 구글이 k[1][0]을 빈 리스트로 주는데 원본 코드가 그대로 k[1][0][1]을 인덱싱해
    # IndexError가 난다. 이 한 줄만 고친 사본. 업스트림이 고치면 이 함수 통째로 제거.
    data = js.split("data:", 1)[1].rsplit(",", 1)[0]
    if data.endswith("errorHasStatus: true"):
        raise _ffp.FlightsNotFound("no flights found; received error")

    payload = json.loads(data)
    alliances, airlines_meta = [], []
    alliances_data, airlines_data = payload[7][1][0], payload[7][1][1]
    for code, name in alliances_data:
        alliances.append(_ffp.Alliance(code=code, name=name))
    for code, name in airlines_data:
        airlines_meta.append(_ffp.Airline(code=code, name=name))
    meta = _ffp.JsMetadata(alliances=alliances, airlines=airlines_meta)

    flights = _ffp.ResultList()
    if payload[3][0] is None:
        return flights

    for k in payload[3][0]:
        flight = k[0]
        price = k[1][0][1] if k[1] and k[1][0] else None

        typ = flight[0]
        flight_airlines = flight[1]

        sg_flights = []
        for single_flight in flight[2]:
            from_airport = _ffp.Airport(code=single_flight[3], name=single_flight[4])
            to_airport = _ffp.Airport(code=single_flight[6], name=single_flight[5])
            departure = _ffp.SimpleDatetime(
                date=tuple(single_flight[20]), time=_ffp._parse_time(single_flight[8])
            )
            arrival = _ffp.SimpleDatetime(
                date=tuple(single_flight[21]), time=_ffp._parse_time(single_flight[10])
            )
            sg_flights.append(
                _ffp.SingleFlight(
                    from_airport=from_airport,
                    to_airport=to_airport,
                    departure=departure,
                    arrival=arrival,
                    duration=single_flight[11],
                    plane_type=single_flight[17],
                )
            )

        extras = flight[22]
        flights.append(
            _ffp.Flights(
                type=typ,
                price=price,
                airlines=flight_airlines,
                flights=sg_flights,
                carbon=_ffp.CarbonEmission(
                    typical_on_route=extras[8], emission=extras[7]
                ),
            )
        )

    flights.metadata = meta
    return flights


_ffp.parse_js = _patched_parse_js

app = FastAPI(title="Flight Search API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://choijc79.github.io"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _dt(d: tuple, t: tuple) -> str:
    y, mo, day = d
    h, mi = t
    return f"{y:04d}-{mo:02d}-{day:02d} {h:02d}:{mi:02d}"


def _leg(f) -> dict:
    return {
        "from": f.from_airport.code,
        "to": f.to_airport.code,
        "departure": _dt(f.departure.date, f.departure.time),
        "arrival": _dt(f.arrival.date, f.arrival.time),
        "duration_min": f.duration,
        "plane": f.plane_type,
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/search")
def search(
    origin: str = Q(..., min_length=3, max_length=3),
    destination: str = Q(..., min_length=3, max_length=3),
    date: str = Q(..., description="YYYY-MM-DD"),
    return_date: Optional[str] = Q(None, description="YYYY-MM-DD, round-trip 때만"),
    trip: str = Q("one-way", pattern="^(one-way|round-trip)$"),
    seat: str = Q("economy", pattern="^(economy|premium-economy|business|first)$"),
    adults: int = Q(1, ge=1, le=9),
    currency: str = "KRW",
):
    origin = origin.upper()
    destination = destination.upper()

    if trip == "round-trip" and not return_date:
        raise HTTPException(400, "round-trip은 return_date가 필요합니다")

    legs = [FlightQuery(date=date, from_airport=origin, to_airport=destination)]
    if trip == "round-trip":
        legs.append(FlightQuery(date=return_date, from_airport=destination, to_airport=origin))

    query = create_query(
        flights=legs,
        seat=seat,
        trip=trip,
        passengers=Passengers(adults=adults),
        currency=currency,
    )

    try:
        result = get_flights(query)
    except FlightsNotFound:
        return {"flights": []}
    except Exception as e:
        raise HTTPException(502, f"구글 플라이츠 조회 실패: {e}")

    ranked = sorted(result, key=lambda f: (f.price is None, f.price or 0))[:20]

    return {
        "flights": [
            {
                "price": f.price,
                "currency": currency,
                "airlines": f.airlines,
                "stops": max(len(f.flights) - 1, 0),
                "legs": [_leg(leg) for leg in f.flights],
            }
            for f in ranked
        ]
    }
