from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, LargeBinary, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from backend.config import settings
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    # Add more user fields as needed
    embeddings = relationship('FaceEmbedding', back_populates='user')
    attendance_records = relationship('AttendanceRecord', back_populates='user')

class FaceEmbedding(Base):
    __tablename__ = 'face_embeddings'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    embedding = Column(LargeBinary, nullable=False)  # Store as binary (could also use JSON or text)
    user = relationship('User', back_populates='embeddings')

class AttendanceRecord(Base):
    __tablename__ = 'attendance_records'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    confidence = Column(Float)
    user = relationship('User', back_populates='attendance_records')

# Database engine and session
engine = create_engine(settings.DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine) 