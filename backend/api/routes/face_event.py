from fastapi import APIRouter, UploadFile, File, Form
import os

router = APIRouter()

@router.post("/api/face_event")
async def receive_face_event(
    timestamp: str = Form(...),
    confidence: float = Form(...),
    image: UploadFile = File(...)
):
    os.makedirs("backend/received_faces", exist_ok=True)
    file_location = f"backend/received_faces/face_{timestamp}.jpg"
    with open(file_location, "wb") as f:
        f.write(await image.read())
    return {"status": "success", "file": file_location} 