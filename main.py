from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
import uuid
from pydantic import BaseModel, EmailStr

from database import get_db, create_tables
from models import User, Event, Participation
from auth import (
    authenticate_user, create_access_token, get_password_hash, 
    verify_token, ACCESS_TOKEN_EXPIRE_MINUTES
)
from qr_utils import generate_qr_code, decode_qr_from_image, validate_qr_data
from pdf_generator import generate_certificate_pdf, send_certificate_email

app = FastAPI(title="Alumni Club Connect", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Pydantic models
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "student"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class EventCreate(BaseModel):
    name: str
    description: Optional[str] = None
    date: datetime
    duration: float

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    total_hours: float

class EventResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    date: datetime
    duration: float
    organizer_name: str

class ParticipationResponse(BaseModel):
    id: int
    event_name: str
    event_date: datetime
    hours_awarded: float
    timestamp: datetime

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    email = verify_token(token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# Initialize database
@app.on_event("startup")
async def startup_event():
    create_tables()

# Authentication endpoints
@app.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        name=user.name,
        email=user.email,
        password_hash=hashed_password,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=db_user.id,
        name=db_user.name,
        email=db_user.email,
        role=db_user.role,
        total_hours=db_user.total_hours
    )

@app.post("/login", response_model=Token)
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# User endpoints
@app.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=current_user.role,
        total_hours=current_user.total_hours
    )

@app.get("/my-participations", response_model=List[ParticipationResponse])
async def get_my_participations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    participations = db.query(Participation).filter(Participation.user_id == current_user.id).all()
    result = []
    for p in participations:
        event = db.query(Event).filter(Event.id == p.event_id).first()
        result.append(ParticipationResponse(
            id=p.id,
            event_name=event.name,
            event_date=event.date,
            hours_awarded=p.hours_awarded,
            timestamp=p.timestamp
        ))
    return result

# Event endpoints
@app.post("/events", response_model=dict)
async def create_event(
    event: EventCreate, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if current_user.role not in ["organizer", "admin"]:
        raise HTTPException(status_code=403, detail="Only organizers can create events")
    
    # Generate QR code
    temp_event_id = int(datetime.now().timestamp())
    qr_data, qr_image = generate_qr_code(temp_event_id)
    
    # Create event
    db_event = Event(
        name=event.name,
        description=event.description,
        date=event.date,
        duration=event.duration,
        organizer_id=current_user.id,
        qr_code_data=qr_data
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    return {
        "event_id": db_event.id,
        "qr_code": qr_image,
        "qr_data": qr_data,
        "message": "Event created successfully"
    }

@app.get("/events", response_model=List[EventResponse])
async def get_events(db: Session = Depends(get_db)):
    events = db.query(Event).all()
    result = []
    for event in events:
        organizer = db.query(User).filter(User.id == event.organizer_id).first()
        result.append(EventResponse(
            id=event.id,
            name=event.name,
            description=event.description,
            date=event.date,
            duration=event.duration,
            organizer_name=organizer.name
        ))
    return result

@app.get("/my-events", response_model=List[EventResponse])
async def get_my_events(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role not in ["organizer", "admin"]:
        raise HTTPException(status_code=403, detail="Only organizers can view their events")
    
    events = db.query(Event).filter(Event.organizer_id == current_user.id).all()
    result = []
    for event in events:
        result.append(EventResponse(
            id=event.id,
            name=event.name,
            description=event.description,
            date=event.date,
            duration=event.duration,
            organizer_name=current_user.name
        ))
    return result

@app.get("/events/{event_id}/participants")
async def get_event_participants(
    event_id: int, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Check if user is organizer of this event or admin
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if current_user.role != "admin" and event.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    participations = db.query(Participation).filter(Participation.event_id == event_id).all()
    participants = []
    for p in participations:
        user = db.query(User).filter(User.id == p.user_id).first()
        participants.append({
            "user_name": user.name,
            "user_email": user.email,
            "timestamp": p.timestamp,
            "hours_awarded": p.hours_awarded
        })
    
    return {"participants": participants, "total_participants": len(participants)}

# QR Code scanning endpoint
@app.post("/scan-qr")
async def scan_qr_code(
    qr_data: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can scan QR codes")
    
    # Validate QR data
    if not validate_qr_data(qr_data):
        raise HTTPException(status_code=400, detail="Invalid QR code")
    
    # Find event by QR data
    event = db.query(Event).filter(Event.qr_code_data == qr_data).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if user already participated
    existing_participation = db.query(Participation).filter(
        Participation.user_id == current_user.id,
        Participation.event_id == event.id
    ).first()
    
    if existing_participation:
        raise HTTPException(status_code=400, detail="You have already participated in this event")
    
    # Create participation record
    participation = Participation(
        user_id=current_user.id,
        event_id=event.id,
        hours_awarded=event.duration
    )
    db.add(participation)
    
    # Update user's total hours
    current_user.total_hours += event.duration
    db.commit()
    
    # Check if user reached 300 hours for certificate
    if current_user.total_hours >= 300:
        # Count events participated
        events_count = db.query(Participation).filter(Participation.user_id == current_user.id).count()
        
        # Generate and send certificate
        try:
            pdf_bytes = generate_certificate_pdf(current_user.name, current_user.total_hours, events_count)
            send_certificate_email(current_user.email, current_user.name, pdf_bytes)
            certificate_message = "Congratulations! You've reached 300 hours. Certificate sent to your email!"
        except Exception as e:
            certificate_message = "You've reached 300 hours, but there was an error sending the certificate."
    else:
        certificate_message = None
    
    return {
        "message": f"Successfully participated in {event.name}",
        "hours_awarded": event.duration,
        "total_hours": current_user.total_hours,
        "certificate_message": certificate_message
    }

@app.post("/scan-qr-image")
async def scan_qr_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can scan QR codes")
    
    # Read image file
    image_data = await file.read()
    
    # Decode QR from image
    qr_data = decode_qr_from_image(image_data)
    if not qr_data:
        raise HTTPException(status_code=400, detail="No valid QR code found in image")
    
    # Use the same logic as scan_qr_code
    return await scan_qr_code(qr_data, current_user, db)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
