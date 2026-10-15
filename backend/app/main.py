from datetime import datetime
from typing import Optional
import httpx
from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from .config import settings
from .database import Base, engine, get_db
from .models import User, Event, Booking, Wishlist, EventUpdate
from .schemas import RegisterIn, TokenOut, ProfilePatch, EventUpdateIn, ChatIn
from .security import hash_password, verify_password, create_access_token, get_current_user, require_staff
from .realtime import hub

Base.metadata.create_all(bind=engine)
app = FastAPI(title="SmartEvent Phase 4 API", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"project": "SmartEvent", "phase": 4, "docs": "/docs"}

@app.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Email already registered")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email}

@app.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}

@app.get("/events")
def search_events(
    category: Optional[str] = None, location: Optional[str] = None,
    min_price: int = Query(0, ge=0), max_price: Optional[int] = Query(None, ge=0),
    start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
    sort_by: str = Query("date", pattern="^(date|price|popularity)$"),
    q: Optional[str] = None, db: Session = Depends(get_db)
):
    stmt = select(Event).where(Event.is_active == True)
    if category: stmt = stmt.where(Event.category.ilike(f"%{category}%"))
    if location: stmt = stmt.where(Event.location.ilike(f"%{location}%"))
    if max_price is not None: stmt = stmt.where(Event.price.between(min_price, max_price))
    elif min_price: stmt = stmt.where(Event.price >= min_price)
    if start_date: stmt = stmt.where(Event.event_date >= start_date)
    if end_date: stmt = stmt.where(Event.event_date <= end_date)
    if q: stmt = stmt.where(Event.title.ilike(f"%{q}%"))
    stmt = stmt.order_by({"date": Event.event_date, "price": Event.price, "popularity": Event.popularity.desc()}[sort_by] if sort_by == "popularity" else {"date": Event.event_date.asc(), "price": Event.price.asc()}[sort_by])
    return [{"id": e.id, "title": e.title, "description": e.description, "category": e.category,
             "location": e.location, "price": e.price, "total_tickets": e.total_tickets,
             "available_tickets": e.available_tickets, "popularity": e.popularity,
             "event_date": e.event_date.isoformat()} for e in db.scalars(stmt).all()]

@app.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.get(Event, event_id)
    if not event: raise HTTPException(404, "Event not found")
    return {"id": event.id, "title": event.title, "description": event.description, "category": event.category,
            "location": event.location, "price": event.price, "available_tickets": event.available_tickets,
            "event_date": event.event_date.isoformat()}

@app.post("/events/{event_id}/book")
async def book_event(event_id: int, quantity: int = Query(1, ge=1, le=10),
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Atomic conditional update prevents two requests from selling the same final ticket.
    result = db.execute(update(Event).where(Event.id == event_id, Event.is_active == True,
                    Event.available_tickets >= quantity).values(
                    available_tickets=Event.available_tickets - quantity,
                    popularity=Event.popularity + 1))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Event not found or insufficient tickets available")
    booking = Booking(user_id=user.id, event_id=event_id, quantity=quantity, status="CONFIRMED")
    db.add(booking); db.commit()
    event = db.get(Event, event_id)
    await hub.broadcast(event_id, event.available_tickets)
    return {"booking_id": booking.id, "event_id": event_id, "quantity": quantity,
            "status": booking.status, "available_tickets": event.available_tickets}

@app.websocket("/ws/events/{event_id}/availability")
async def availability_socket(websocket: WebSocket, event_id: int):
    await hub.connect(event_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # client can send ping/keepalive
    except WebSocketDisconnect:
        hub.disconnect(event_id, websocket)

@app.get("/recommendations")
def recommendations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booked_ids = select(Booking.event_id).where(Booking.user_id == user.id)
    stmt = select(Event).where(Event.is_active == True, Event.id.not_in(booked_ids))
    events = db.scalars(stmt).all()
    def score(e):
        return (5 if user.preferred_category and e.category.lower() == user.preferred_category.lower() else 0) + \
               (3 if user.location and user.location.lower() in e.location.lower() else 0) + e.popularity
    return {"recommended_for_you": [event_json(e) for e in sorted(events, key=score, reverse=True)[:10]],
            "trending_events": [event_json(e) for e in sorted(events, key=lambda e: e.popularity, reverse=True)[:10]]}

def event_json(e):
    return {"id": e.id, "title": e.title, "description": e.description, "category": e.category,
            "location": e.location, "price": e.price, "available_tickets": e.available_tickets,
            "popularity": e.popularity, "event_date": e.event_date.isoformat()}

@app.get("/wishlist")
def get_wishlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Wishlist).where(Wishlist.user_id == user.id).order_by(Wishlist.created_at.desc())).all()
    return [{"id": w.id, "event": event_json(db.get(Event, w.event_id)), "created_at": w.created_at.isoformat()} for w in rows if db.get(Event, w.event_id)]

@app.post("/wishlist/{event_id}", status_code=201)
def add_wishlist(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.get(Event, event_id): raise HTTPException(404, "Event not found")
    exists = db.scalar(select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.event_id == event_id))
    if exists: return {"message": "Already saved"}
    db.add(Wishlist(user_id=user.id, event_id=event_id)); db.commit()
    return {"message": "Event saved to wishlist"}

@app.delete("/wishlist/{event_id}")
def remove_wishlist(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(Wishlist).where(Wishlist.user_id == user.id, Wishlist.event_id == event_id))
    if not row: raise HTTPException(404, "Wishlist item not found")
    db.delete(row); db.commit()
    return {"message": "Removed from wishlist"}

@app.get("/events/{event_id}/updates")
def get_updates(event_id: int, db: Session = Depends(get_db)):
    if not db.get(Event, event_id): raise HTTPException(404, "Event not found")
    rows = db.scalars(select(EventUpdate).where(EventUpdate.event_id == event_id).order_by(EventUpdate.created_at.desc())).all()
    return [{"id": r.id, "message": r.message, "important": r.important, "created_at": r.created_at.isoformat()} for r in rows]

@app.post("/events/{event_id}/updates", status_code=201)
def post_update(event_id: int, data: EventUpdateIn, user: User = Depends(require_staff), db: Session = Depends(get_db)):
    if not db.get(Event, event_id): raise HTTPException(404, "Event not found")
    row = EventUpdate(event_id=event_id, message=data.message.strip(), important=data.important)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "event_id": row.event_id, "message": row.message, "important": row.important,
            "created_at": row.created_at.isoformat()}

@app.get("/profile")
def get_profile(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "location": user.location,
            "preferred_category": user.preferred_category, "profile_picture_url": user.profile_picture_url, "role": user.role}

@app.patch("/profile")
def update_profile(data: ProfilePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit(); db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "location": user.location,
            "preferred_category": user.preferred_category, "profile_picture_url": user.profile_picture_url}

@app.get("/profile/bookings")
def profile_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())).all()
    return [{"booking_id": b.id, "event_id": b.event_id, "event_title": (db.get(Event, b.event_id).title if db.get(Event, b.event_id) else "Deleted event"),
             "quantity": b.quantity, "status": b.status, "created_at": b.created_at.isoformat()} for b in rows]

@app.post("/chat")
async def chat(data: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    message = data.message.strip()
    low = message.lower()
    if any(x in low for x in ("my bookings", "my tickets", "show my booking")):
        bookings = profile_bookings(user, db)
        return {"reply": f"You have {len(bookings)} booking record(s).", "bookings": bookings}
    if "wishlist" in low:
        saved = get_wishlist(user, db)
        return {"reply": f"You have {len(saved)} saved event(s).", "wishlist": saved}
    stmt = select(Event).where(Event.is_active == True)
    if any(x in low for x in ("music", "concert", "band")): stmt = stmt.where(Event.category.ilike("%music%"))
    if user.location and any(x in low for x in ("near me", "nearby", "local")): stmt = stmt.where(Event.location.ilike(f"%{user.location}%"))
    if any(x in low for x in ("trending", "popular")): stmt = stmt.order_by(Event.popularity.desc())
    else: stmt = stmt.order_by(Event.event_date.asc())
    found = db.scalars(stmt.limit(5)).all()
    if found:
        return {"reply": "Here are some events that may help. You can open an event to view details and availability.",
                "events": [event_json(e) for e in found]}
    # Optional Ollama fallback for FAQ-style questions; works without Ollama too.
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json={"model": settings.ollama_model, "prompt": f"Answer briefly as a ticketing platform support assistant. Do not claim to perform actions. User: {message}", "stream": False})
            resp.raise_for_status()
            answer = resp.json().get("response", "")
            if answer: return {"reply": answer}
    except Exception:
        pass
    return {"reply": "I can help find events, show your bookings, explain wishlist features, and guide you through ticket issues. Try “trending events”, “music events”, or “show my bookings”."}

@app.get("/health")
def health():
    return {"status": "ok"}
