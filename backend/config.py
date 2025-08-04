from pydantic_settings import BaseSettings
from typing import List
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AI Attendance System"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Database
    DATABASE_URL: str = "sqlite:///./attendance.db"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # React frontend
        "http://localhost:3001",  # React frontend (alternative port)
        "http://localhost:8000",  # FastAPI backend
    ]
    
    # Face Recognition
    FACE_RECOGNITION_MODEL_PATH: str = "face_recognition/models/facenet_keras.h5"
    FACE_DETECTION_MODEL_PATH: str = "face_recognition/models/yolov8n-face.pt"
    
    # AI Assistant
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ASSISTANT_MODEL: str = "gpt-3.5-turbo"
    
    class Config:
        case_sensitive = True

settings = Settings() 