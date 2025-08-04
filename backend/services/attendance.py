from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from backend.models import SessionLocal, AttendanceRecord, User

class AttendanceService:
    def __init__(self):
        # Initialize the cache for present students
        self.present_students = {}  # Format: {date_str: set(user_ids)}
        self.reset_cache()  # Start with a clean cache
    
    def reset_cache(self):
        """Reset the entire cache. Call this when face recognizer starts."""
        self.present_students = {
            date.today().isoformat(): set()  # Start fresh with just today
        }
    
    def _reset_cache_if_new_day(self):
        """Reset the cache if it's a new day"""
        today = date.today().isoformat()
        if today not in self.present_students:
            # Keep last 7 days of data in cache, remove older entries
            week_ago = (date.today() - timedelta(days=7)).isoformat()
            self.present_students = {
                date_str: user_ids 
                for date_str, user_ids in self.present_students.items() 
                if date_str >= week_ago
            }
            # Initialize new day
            self.present_students[today] = set()

    def record_attendance(self, user_id: int, confidence: float):
        """Record attendance only if student hasn't been marked present today"""
        self._reset_cache_if_new_day()
        today = date.today().isoformat()
        
        # Check if student is already marked present today
        if user_id in self.present_students[today]:
            return {
                "status": "skipped", 
                "message": f"Student {user_id} already marked present today"
            }
        
        db = SessionLocal()
        try:
            # Record attendance in database
            record = AttendanceRecord(user_id=user_id, confidence=confidence)
            db.add(record)
            db.commit()
            
            # Add to cache
            self.present_students[today].add(user_id)
            
            return {
                "status": "success", 
                "message": f"Attendance recorded for student {user_id}"
            }
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def get_attendance_history(self, user_id: int, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == user_id)
            if start_date:
                query = query.filter(AttendanceRecord.timestamp >= start_date)
            if end_date:
                query = query.filter(AttendanceRecord.timestamp <= end_date)
            records = query.order_by(AttendanceRecord.timestamp.desc()).all()
            return [
                {
                    "timestamp": record.timestamp,
                    "confidence": record.confidence
                }
                for record in records
            ]
        finally:
            db.close()

    def get_attendance_statistics(self) -> Dict[str, Any]:
        """Get attendance statistics using cache for today's attendance"""
        self._reset_cache_if_new_day()
        today = date.today().isoformat()
        
        db = SessionLocal()
        try:
            total_users = db.query(User).count()
            # Use cache for today's attendance
            today_attendance = len(self.present_students[today])
            
            # For weekly attendance, combine cache and database data
            week_ago = (date.today() - timedelta(days=7)).isoformat()
            weekly_attendance = len({
                user_id
                for date_str, user_ids in self.present_students.items()
                for user_id in user_ids
                if date_str >= week_ago
            })
            
            return {
                "total_users": total_users,
                "today_attendance": today_attendance,
                "weekly_attendance": weekly_attendance,
                "attendance_rate": (weekly_attendance / total_users * 100) if total_users else 0
            }
        finally:
            db.close()

    def get_user_attendance_patterns(self, user_id: int) -> Dict[str, Any]:
        """Get attendance patterns for a user"""
        db = SessionLocal()
        try:
            # Get attendance by day of week
            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.user_id == user_id
            ).all()
            
            daily_patterns = {}
            for record in records:
                day_of_week = record.timestamp.strftime("%w")  # 0-6, Sunday is 0
                daily_patterns[day_of_week] = daily_patterns.get(day_of_week, 0) + 1
            
            # Calculate average attendance time
            total_hours = 0
            record_count = 0
            for record in records:
                hour = int(record.timestamp.strftime("%H"))
                total_hours += hour
                record_count += 1
            
            avg_hour = total_hours / record_count if record_count > 0 else 0
            
            return {
                "daily_patterns": daily_patterns,
                "average_time": avg_hour
            }
        finally:
            db.close() 