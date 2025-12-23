"""
API routes for folder-based PDF upload
Folder name = Course name
Each PDF = One Assessment
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import List, Dict, Any
from pathlib import Path
import shutil
import os
from app.services.folder_processor import folder_processor
from app.utils.logger import logger

router = APIRouter(prefix="/api/folder", tags=["Folder Upload"])


@router.post("/upload")
async def upload_folder(
    folder_name: str,
    files: List[UploadFile] = File(...)
):
    """
    Upload a course folder with PDF files
    
    Args:
        folder_name: Course name (folder name)
        files: List of PDF files to upload
    
    Returns:
        Processing results
    """
    try:
        if not folder_name or not folder_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Folder name (course name) is required"
            )
        
        # Normalize folder name
        course_name = folder_name.strip()
        
        # Filter only PDF files
        pdf_files = [f for f in files if f.filename and f.filename.endswith('.pdf')]
        
        if not pdf_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No PDF files provided"
            )
        
        logger.info(f"📁 Uploading course folder: {course_name} with {len(pdf_files)} PDF file(s)")
        
        # Create course folder in uploads directory
        uploads_dir = Path("app/uploads")
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        course_folder = uploads_dir / course_name
        course_folder.mkdir(parents=True, exist_ok=True)
        
        # Save PDF files to course folder
        uploaded_files = []
        for pdf_file in pdf_files:
            file_path = course_folder / pdf_file.filename
            try:
                with open(file_path, 'wb') as f:
                    content = await pdf_file.read()
                    f.write(content)
                uploaded_files.append(file_path)
                logger.info(f"  ✅ Saved: {pdf_file.filename}")
            except Exception as e:
                logger.error(f"  ❌ Error saving {pdf_file.filename}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error saving file {pdf_file.filename}: {str(e)}"
                )
        
        # Process the course folder
        logger.info(f"🔄 Processing course folder: {course_name}")
        result = folder_processor.process_course_folder(course_folder)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to process course folder")
            )
        
        return {
            "success": True,
            "course_name": course_name,
            "course_id": result.get("course_id"),
            "pdfs_uploaded": len(uploaded_files),
            "assessments_created": result.get("assessments_created", 0),
            "assessments_skipped": result.get("assessments_skipped", 0),
            "assessments": result.get("assessments", []),
            "errors": result.get("errors", []),
            "message": f"Successfully processed course '{course_name}': {result.get('assessments_created', 0)} assessments created, {result.get('assessments_skipped', 0)} skipped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading folder: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading folder: {str(e)}"
        )


@router.post("/process-all")
async def process_all_folders():
    """
    Process all course folders in app/uploads/
    
    This endpoint:
    1. Scans app/uploads/ for course folders
    2. For each folder (course):
       - Gets or creates course
       - Processes each PDF in folder
       - Creates assessments linked to course
    3. Enforces strict isolation (no mixing)
    
    Returns:
        Overall processing results
    """
    try:
        logger.info("🔄 Processing all course folders in app/uploads/")
        
        result = folder_processor.process_all_folders()
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to process folders")
            )
        
        return {
            "success": True,
            "courses_processed": result.get("courses_processed", 0),
            "total_assessments_created": result.get("total_assessments_created", 0),
            "total_assessments_skipped": result.get("total_assessments_skipped", 0),
            "courses": result.get("courses", []),
            "errors": result.get("errors", []),
            "message": f"Processed {result.get('courses_processed', 0)} course(s): {result.get('total_assessments_created', 0)} assessments created, {result.get('total_assessments_skipped', 0)} skipped"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing all folders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing folders: {str(e)}"
        )


@router.get("/list")
async def list_course_folders():
    """
    List all course folders in app/uploads/
    
    Returns:
        List of course folders with PDF counts
    """
    try:
        uploads_dir = Path("app/uploads")
        
        if not uploads_dir.exists():
            return {
                "success": True,
                "folders": [],
                "message": "Uploads directory does not exist"
            }
        
        folders = []
        for folder in uploads_dir.iterdir():
            if folder.is_dir():
                pdf_files = list(folder.glob("*.pdf"))
                folders.append({
                    "name": folder.name,
                    "path": str(folder.relative_to(uploads_dir)),
                    "pdf_count": len(pdf_files),
                    "pdfs": [f.name for f in pdf_files]
                })
        
        return {
            "success": True,
            "folders": folders,
            "total_folders": len(folders)
        }
        
    except Exception as e:
        logger.error(f"Error listing folders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing folders: {str(e)}"
        )

