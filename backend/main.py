from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from backend.api.routes import attendance, auth, assistant
from backend.config import settings
from backend.api.routes import face_event
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.models import AttendanceRecord, SessionLocal
from pydantic import BaseModel

class RecordAttendanceRequest(BaseModel):
    user_id: str
    confidence: float

app = FastAPI(
    title="AI Attendance System",
    description="An AI-powered attendance system with facial recognition and personal assistant",
    version="1.0.0"
)

print("CORS_ORIGINS:", settings.CORS_ORIGINS)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["AI Assistant"])
app.include_router(face_event.router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return {"message": "Welcome to AI Attendance System API"}

# Add new endpoint for attendance cleanup
@app.get("/api/attendance/cleanup")
async def cleanup_attendance():
    db = SessionLocal()
    try:
        # Get all attendance records ordered by user and timestamp
        records = db.query(AttendanceRecord).order_by(
            AttendanceRecord.user_id,
            AttendanceRecord.timestamp
        ).all()
        
        # Group records by user_id and 5-minute window
        windows = {}
        for record in records:
            user_id = record.user_id
            timestamp = record.timestamp
            window_key = (user_id, timestamp.replace(second=0, microsecond=0) - timedelta(minutes=timestamp.minute % 5))
            if window_key not in windows:
                windows[window_key] = []
            windows[window_key].append(record)
        
        # Keep only the first record in each window and delete the rest
        deleted_count = 0
        for window_records in windows.values():
            if len(window_records) > 1:
                # Keep the first record, delete the rest
                for record in window_records[1:]:
                    db.delete(record)
                    deleted_count += 1
        
        db.commit()
        return {"message": f"Cleaned up {deleted_count} duplicate attendance records"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# Add helper function for cleaning up duplicates for a specific user
async def cleanup_user_attendance(db: Session, user_id: int, timestamp: datetime):
    try:
        # Define the time window (5 minutes before and after the given timestamp)
        window_start = timestamp.replace(second=0, microsecond=0) - timedelta(minutes=timestamp.minute % 5)
        window_end = window_start + timedelta(minutes=5)
        
        # Get all records for this user in the time window
        records = db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id,
            AttendanceRecord.timestamp >= window_start,
            AttendanceRecord.timestamp < window_end
        ).order_by(AttendanceRecord.timestamp).all()
        
        # If there are multiple records, keep only the first one
        if len(records) > 1:
            for record in records[1:]:
                db.delete(record)
            db.commit()
            return len(records) - 1
        return 0
    except Exception as e:
        db.rollback()
        raise e

# Modify the record attendance endpoint to use the cleanup function
@app.post("/api/attendance/record")
async def record_attendance_endpoint(request: RecordAttendanceRequest):
    """Record attendance for a recognized user and clean up any duplicates"""
    db = SessionLocal()
    try:
        # Convert user_id to integer
        user_id = int(request.user_id)
        
        # Record the new attendance
        now = datetime.now()
        new_record = AttendanceRecord(
            user_id=user_id,
            confidence=request.confidence,
            timestamp=now
        )
        db.add(new_record)
        db.commit()
        
        # Clean up any duplicates for this user in the same time window
        cleaned_count = await cleanup_user_attendance(db, user_id, now)
        
        message = f"Attendance recorded for user {user_id}"
        if cleaned_count > 0:
            message += f" (cleaned up {cleaned_count} duplicate records)"
        
        return {"status": "success", "message": message}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format. Must be an integer.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 