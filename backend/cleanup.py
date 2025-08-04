import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models import SessionLocal, User, FaceEmbedding, AttendanceRecord

def cleanup_user(user_id: int):
    db = SessionLocal()
    try:
        # Delete attendance records
        db.query(AttendanceRecord).filter(AttendanceRecord.user_id == user_id).delete()
        
        # Delete face embeddings
        db.query(FaceEmbedding).filter(FaceEmbedding.user_id == user_id).delete()
        
        # Delete user
        db.query(User).filter(User.id == user_id).delete()
        
        # Commit changes
        db.commit()
        print(f"Successfully deleted user {user_id} and all associated data")
    except Exception as e:
        db.rollback()
        print(f"Error deleting user: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Yasser's ID
    user_id = 2104449
    cleanup_user(user_id) 