from fastapi import APIRouter, Depends, HTTPException, WebSocket, Body, Query
from fastapi.security import OAuth2PasswordBearer
from typing import List
import json
from datetime import datetime, date, timedelta
from ...services.attendance import AttendanceService
from ...services.face_recognition import FaceRecognitionService
from ...config import settings
from backend.models import SessionLocal, User, FaceEmbedding, AttendanceRecord
import numpy as np
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Initialize services
face_recognition_service = FaceRecognitionService(
    settings.FACE_RECOGNITION_MODEL_PATH,
    settings.FACE_DETECTION_MODEL_PATH
)
attendance_service = AttendanceService()

class RegisterFaceRequest(BaseModel):
    student_id: int
    name: str
    image_data: str

class RecordAttendanceRequest(BaseModel):
    user_id: str
    confidence: float

@router.post("/register")
async def register_face(request: RegisterFaceRequest):
    """Register a new face for attendance"""
    student_id = request.student_id
    name = request.name
    image_data = request.image_data
    db = SessionLocal()
    try:
        # Check if user already exists
        user = db.query(User).filter(User.id == student_id).first()
        if not user:
            user = User(id=student_id, name=name)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update the name if it has changed
            if user.name != name:
                user.name = name
                db.commit()
        # Process image and get embedding
        embedding = face_recognition_service.get_face_embedding(image_data)
        # Convert embedding to binary (if it's a numpy array)
        if isinstance(embedding, np.ndarray):
            embedding_bytes = embedding.tobytes()
        else:
            embedding_bytes = bytes(embedding)
        # Store embedding
        face_embedding = FaceEmbedding(user_id=user.id, embedding=embedding_bytes)
        db.add(face_embedding)
        db.commit()
        return {"status": "success", "message": f"Face registered for {name}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.websocket("/ws/attendance")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time attendance"""
    await websocket.accept()
    try:
        while True:
            # Receive frame data
            data = await websocket.receive_text()
            frame_data = json.loads(data)
            
            # Process frame for face detection and recognition
            results = face_recognition_service.process_frame(frame_data)
            
            # Record attendance for recognized faces
            for identity, _, confidence in results:
                if identity and confidence > 0.7:
                    attendance_service.record_attendance(
                        identity,
                        datetime.now(),
                        confidence
                    )
            
            # Send results back to client
            await websocket.send_json({
                "recognized_faces": [
                    {
                        "name": identity,
                        "confidence": float(confidence)
                    }
                    for identity, _, confidence in results
                    if identity
                ]
            })
    except Exception as e:
        await websocket.close(code=1000, reason=str(e))

@router.get("/history/{user_id}")
async def get_attendance_history(
    user_id: str,
    start_date: datetime = None,
    end_date: datetime = None
):
    """Get attendance history for a user"""
    try:
        history = attendance_service.get_attendance_history(
            user_id,
            start_date,
            end_date
        )
        return {
            "status": "success",
            "data": history
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/stats")
async def get_attendance_stats():
    """Get attendance statistics"""
    try:
        stats = attendance_service.get_attendance_statistics()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/detect_faces")
async def detect_faces(image_base64: str = Body(..., embed=True)):
    """Detect faces in a base64-encoded image and return bounding boxes"""
    try:
        boxes = face_recognition_service.detect_faces(image_base64)
        return {"boxes": boxes}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/all")
async def get_all_attendance():
    """Get all attendance records for all users"""
    db = SessionLocal()
    try:
        # Join AttendanceRecord and User tables
        records = db.execute(
            text("""
            SELECT ar.id, ar.user_id, u.name, ar.timestamp, ar.confidence
            FROM attendance_records ar
            JOIN users u ON ar.user_id = u.id
            ORDER BY ar.timestamp DESC
            """)
        ).fetchall()
        result = []
        for r in records:
            # Determine status based on confidence or other logic
            status = "PRESENT" if r.confidence >= 0.9 else ("LATE" if r.confidence >= 0.7 else "ABSENT")
            # Fix: parse string timestamp to datetime if needed
            if r.timestamp:
                if isinstance(r.timestamp, str):
                    try:
                        dt = datetime.fromisoformat(r.timestamp)
                    except ValueError:
                        dt = datetime.strptime(r.timestamp, "%Y-%m-%d %H:%M:%S.%f")
                else:
                    dt = r.timestamp
                time_str = dt.strftime("%H:%M:%S")
                date_str = dt.strftime("%Y-%m-%d")
            else:
                time_str = "-"
                date_str = "-"
            result.append({
                "id": r.id,
                "studentId": r.user_id,
                "name": r.name,
                "date": date_str,
                "time": time_str,
                "status": status
            })
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.post("/record")
async def record_attendance_endpoint(request: RecordAttendanceRequest):
    """Record attendance for a recognized user"""
    try:
        # The existing attendance_service.record_attendance uses datetime.now() internally
        attendance_service.record_attendance(user_id=int(request.user_id), confidence=request.confidence)
        return {"status": "success", "message": f"Attendance recorded for user {request.user_id}"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format. Must be an integer.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/students")
async def get_all_students():
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.name.asc()).all()
        result = []
        for user in users:
            result.append({
                "id": user.id,
                "name": user.name
            })
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.get("/dashboard_stats")
async def get_dashboard_stats():
    db = SessionLocal()
    try:
        total_students = db.query(User).count()
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Get all attendance records for today
        records_today = db.query(AttendanceRecord).filter(
            AttendanceRecord.timestamp >= today_start,
            AttendanceRecord.timestamp <= today_end
        ).all()

        present_ids = set()
        late_ids = set()
        for record in records_today:
            if record.confidence >= 0.9:
                present_ids.add(record.user_id)
            elif record.confidence >= 0.7:
                late_ids.add(record.user_id)

        present_today = len(present_ids)
        late_today = len(late_ids)
        absent_today = total_students - present_today

        return {
            "status": "success",
            "data": {
                "total_students": total_students,
                "present_today": present_today,
                "absent_today": absent_today,
                "late_today": late_today,
                "attendance_rate": (present_today / total_students * 100) if total_students else 0,
                "late_rate": (late_today / total_students * 100) if total_students else 0,
                "absent_rate": (absent_today / total_students * 100) if total_students else 0,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.get("/attendance_report")
async def attendance_report(
    period: str = Query("month", description="Period: 'month', 'week', or 'all'")
):
    db = SessionLocal()
    try:
        today = date.today()
        if period == "month":
            start_date = today.replace(day=1)
        elif period == "week":
            start_date = today - timedelta(days=today.weekday())
        else:
            start_date = date(1970, 1, 1)  # all time

        records = db.query(AttendanceRecord).filter(
            AttendanceRecord.timestamp >= start_date
        ).all()

        total_students = db.query(User).count()
        present_ids = set()
        late_ids = set()
        # For trends
        trends = {}

        for record in records:
            day = record.timestamp.date().isoformat()
            if day not in trends:
                trends[day] = {"present": 0, "late": 0, "absent": 0}
            if record.confidence >= 0.9:
                present_ids.add(record.user_id)
                trends[day]["present"] += 1
            elif record.confidence >= 0.7:
                late_ids.add(record.user_id)
                trends[day]["late"] += 1
            else:
                trends[day]["absent"] += 1

        present = len(present_ids)
        late = len(late_ids)
        absent = total_students - present
        total_attendance = (present / total_students * 100) if total_students else 0

        return {
            "status": "success",
            "data": {
                "total_attendance": total_attendance,
                "present": present,
                "absent": absent,
                "late": late,
                "trends": trends
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.get("/recent")
async def get_recent_attendance(limit: int = 10):
    db = SessionLocal()
    try:
        records = db.execute(
            text("""
            SELECT ar.id, ar.user_id, u.name, ar.timestamp, ar.confidence
            FROM attendance_records ar
            JOIN users u ON ar.user_id = u.id
            ORDER BY ar.timestamp DESC
            LIMIT :limit
            """),
            {"limit": limit}
        ).fetchall()
        result = []
        for r in records:
            status = "PRESENT" if r.confidence >= 0.9 else ("LATE" if r.confidence >= 0.7 else "ABSENT")
            result.append({
                "id": r.id,
                "studentId": r.user_id,
                "name": r.name,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(r.timestamp, 'strftime') else str(r.timestamp),
                "status": status
            })
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()

@router.post("/reset_cache")
async def reset_attendance_cache():
    """Reset the attendance cache when face recognition starts"""
    try:
        attendance_service.reset_cache()
        return {
            "status": "success",
            "message": "Attendance cache reset successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 