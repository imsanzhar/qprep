import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

router = APIRouter(prefix="/api/v1/speaking", tags=["Speaking"])

UPLOAD_DIR = "uploads/speaking"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/submit")
async def submit_speaking(
    file: UploadFile = File(...),
    task_id: int = Form(...),
):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Файл должен быть аудиоформата")
    file_extension = file.filename.split(".")[-1]
    unique_filename = f"task_{task_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Қате: {str(e)}")
    return {
        "status": "success",
        "message": "Аудио сәтті сақталды",
        "file_path": file_path
    }