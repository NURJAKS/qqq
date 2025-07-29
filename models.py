from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # "student", "organizer", "admin"
    total_hours = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    organized_events = relationship("Event", back_populates="organizer")
    participations = relationship("Participation", back_populates="user")

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    date = Column(DateTime, nullable=False)
    duration = Column(Float, nullable=False)  # hours
    organizer_id = Column(Integer, ForeignKey("users.id"))
    qr_code_data = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    organizer = relationship("User", back_populates="organized_events")
    participations = relationship("Participation", back_populates="event")

class Participation(Base):
    __tablename__ = "participation"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    hours_awarded = Column(Float, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="participations")
    event = relationship("Event", back_populates="participations")
