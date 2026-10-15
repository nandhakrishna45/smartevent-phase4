# SmartEvent — Phase 4 Repository Files

Phase 4 modules: 18–24 (real-time ticket availability, recommendations, wishlist, live event updates, profile, advanced search, chatbot).

## Project structure
- `backend/`: FastAPI + SQLAlchemy + JWT authentication
- `frontend/`: React + Vite interface for Phase 4 features
- `.env.example`: environment variable template
- `.gitignore`: excludes secrets, virtual environments, build output and local databases

## Important integration note
This is a runnable Phase 4 starter repository. If your Phase 1–3 project already has models/routes, merge the Phase 4 modules into those existing files rather than replacing the project wholesale. The starter defines compact `User`, `Event`, and `Booking` models to make the modules runnable on their own.

## Requirements
- Python 3.10+
- Node.js 18+

## Run backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload
```
API docs: http://127.0.0.1:8000/docs

The starter creates a local SQLite database automatically. For real deployments, set a strong `SECRET_KEY`, configure a production database, and use HTTPS.

## Run frontend
In a second terminal:
```bash
cd frontend
npm install
npm run dev
```
Open the URL printed by Vite. Set `VITE_API_URL` if the backend is not at `http://127.0.0.1:8000`.

## Demo authentication
Create an account using `POST /auth/register`, then sign in using `POST /auth/login` (OAuth2 form fields: `username` and `password`). Add a bearer token in Swagger's Authorize dialog.
The React starter includes a minimal login form and persists the token in session storage for local development only.

## Phase 4 endpoints
- `GET /events` — multi-filter search, sorting and live availability fields
- `GET /recommendations` — category/location/popularity recommendations
- `GET /wishlist` — current user's saved events
- `POST /wishlist/{event_id}` and `DELETE /wishlist/{event_id}`
- `GET /events/{event_id}/updates`
- `POST /events/{event_id}/updates` — admin/organizer role required
- `GET /profile`, `PATCH /profile`, `GET /profile/bookings`
- `POST /chat` — event discovery, booking summary and FAQ assistance
- `WS /ws/events/{event_id}/availability` — live availability notifications

## Real-time / concurrency notes
Booking uses a database transaction and conditional ticket-count update to prevent overselling. SQLite is suitable for local evaluation; use PostgreSQL and an appropriate isolation/locking strategy for production multi-worker deployments. The WebSocket broadcast in this starter is process-local, so a multi-worker deployment should use Redis pub/sub or another shared message broker.

## GitHub manual upload
Upload the extracted contents of this folder to your repository root. Do not upload `.env`, `.venv/`, `node_modules/`, `__pycache__/`, or a local `.db` file.
