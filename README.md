# flight-search-api

[fast-flights](https://github.com/AWeirdDev/flights)로 Google Flights를 스크래핑하는 최저가 항공권 검색 API. API 키 없음.

- `GET /search?origin=ICN&destination=NRT&date=2026-12-20` — 편도
- `GET /search?origin=ICN&destination=NRT&date=2026-12-20&return_date=2026-12-23&trip=round-trip` — 왕복(참고용 추정가, 구글 정식 왕복 결합가와 다를 수 있음)
- `GET /health`

`app.py` 상단의 `_patched_parse_js`는 fast-flights 3.1.0의 가격 미확정 itinerary 파싱 버그를 우회하는 패치다. 업스트림이 고치면 지워도 된다.

## Render 배포

1. [render.com](https://render.com) 가입 (GitHub 계정으로 로그인 가능)
2. **New +** → **Web Service** → 이 저장소 선택
3. 설정값
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
   - Instance Type: Free
4. 배포 완료 후 나오는 URL(`https://xxxx.onrender.com`)을 `choijc79.github.io`의 `flights.html`에 있는 `API_BASE` 값에 넣는다.

무료 플랜은 15분간 요청이 없으면 슬립 상태가 되어 첫 요청이 느릴 수 있다(콜드 스타트).
