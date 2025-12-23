"""
Folder-based PDF Processing Service
Processes course folders where:
- Folder name = Course name
- Each PDF = One Assessment
- Strict isolation and duplicate prevention
"""

import os
import uuid
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from app.services.supabase_service import supabase_service
from app.services.pdf_processor import pdf_processor
from app.services.assessment_generator import assessment_generator
from app.utils.logger import logger


class FolderProcessor:
    """Service for processing course folders and PDFs"""
    
    def __init__(self):
        """Initialize folder processor"""
        self.client = None
        self.uploads_dir = Path("app/uploads")
        self._initialize_client()
        self._ensure_uploads_directory()
    
    def _initialize_client(self):
        """Initialize Supabase client"""
        self.client = supabase_service.get_client(use_service_key=True)
        if not self.client:
            logger.warning("Service key client not available, falling back to anon key")
            self.client = supabase_service.get_client(use_service_key=False)
    
    def _ensure_uploads_directory(self):
        """Ensure uploads directory exists"""
        try:
            self.uploads_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[OK] Uploads directory ready: {self.uploads_dir.absolute()}")
        except Exception as e:
            logger.error(f"Error creating uploads directory: {str(e)}")
            raise
    
    def get_or_create_course(self, course_name: str) -> Optional[str]:
        """
        Get or create course by name (enforces uniqueness)
        
        Args:
            course_name: Course name (from folder name)
        
        Returns:
            Course ID (UUID string) or None
        """
        try:
            if not self.client:
                logger.error("Supabase client not available")
                return None
            
            # Normalize course name
            course_name = course_name.strip()
            if not course_name:
                logger.error("Course name cannot be empty")
                return None
            
            # Check if course exists (case-insensitive, exact match)
            # Use ilike for case-insensitive search, but also check exact match
            response = self.client.table("courses")\
                .select("id, name")\
                .ilike("name", course_name)\
                .limit(10)\
                .execute()
            
            # Find exact match (case-insensitive)
            if response.data:
                for course in response.data:
                    if course.get("name", "").strip().lower() == course_name.lower():
                        course_id = str(course["id"])
                        logger.info(f"[OK] Found existing course: {course.get('name')} (ID: {course_id})")
                        return course_id
            
            # Create new course
            logger.info(f"[INFO] Creating new course: {course_name}")
            create_response = self.client.table("courses")\
                .insert({
                    "name": course_name,
                    "description": f"Course: {course_name}"
                })\
                .execute()
            
            if create_response.data and len(create_response.data) > 0:
                course_id = str(create_response.data[0]["id"])
                logger.info(f"[OK] Created course: {course_name} (ID: {course_id})")
                return course_id
            else:
                logger.error(f"[FAILED] Failed to create course: {course_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting/creating course {course_name}: {str(e)}")
            return None
    
    def _calculate_file_hash(self, pdf_path: Path, hash_algo='sha256', chunk_size=8192) -> str:
        """
        Calculate the SHA256 hash of a file in a memory-efficient way.
        Reads the file in chunks to avoid loading the entire file into memory.
        
        Args:
            pdf_path: Path to the PDF file
            hash_algo: Hash algorithm to use (default: 'sha256')
            chunk_size: Size of chunks to read (default: 8KB)
        
        Returns:
            Hexadecimal hash string, or empty string on error
        """
        hasher = hashlib.sha256()
        try:
            with open(pdf_path, 'rb') as file:
                while chunk := file.read(chunk_size):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating hash for {pdf_path}: {str(e)}")
            return ""
    
    def check_assessment_exists(self, course_id: str, assessment_title: str) -> Optional[str]:
        """
        Check if assessment already exists for a course (enforces uniqueness)
        
        Args:
            course_id: Course ID
            assessment_title: Assessment title (from PDF filename)
        
        Returns:
            Existing assessment ID if found, None otherwise
        """
        try:
            if not self.client:
                return None
            
            # Normalize assessment title for comparison
            normalized_title = assessment_title.strip().lower()
            
            # Check if assessment exists for this course
            response = self.client.table("assessments")\
                .select("id, title")\
                .eq("course_id", course_id)\
                .execute()
            
            if response.data:
                for assessment in response.data:
                    # Case-insensitive comparison
                    if assessment.get("title", "").strip().lower() == normalized_title:
                        assessment_id = str(assessment.get("id"))
                        logger.info(f"[SKIP] Assessment already exists: {assessment_title} in course {course_id}")
                        return assessment_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking assessment existence: {str(e)}")
            return None
    
    def process_pdf_file(
        self,
        pdf_path: Path,
        course_id: str,
        course_name: str
    ) -> Dict[str, Any]:
        """
        Process a single PDF file into an assessment
        
        Args:
            pdf_path: Path to PDF file
            course_id: Course ID to link assessment
            course_name: Course name (for logging)
        
        Returns:
            Dictionary with processing result
        """
        try:
            # Extract assessment title from filename (without extension)
            assessment_title = pdf_path.stem  # filename without .pdf
            
            logger.info(f"[INFO] Processing PDF: {assessment_title} (Course: {course_name})")
            
            # Check if assessment already exists (duplicate prevention)
            existing_assessment_id = self.check_assessment_exists(course_id, assessment_title)
            if existing_assessment_id:
                return {
                    "success": True,
                    "skipped": True,
                    "assessment_id": existing_assessment_id,
                    "title": assessment_title,
                    "message": f"Assessment '{assessment_title}' already exists in course '{course_name}'"
                }
            
            # OPTIMIZATION: Read PDF file only once, get size for metadata
            # Don't keep entire file in memory - we only need it for size calculation
            pdf_file_size = pdf_path.stat().st_size
            
            # Calculate file hash for duplicate detection (more reliable than title matching)
            # Use SHA256 hash of file content to detect exact duplicates
            logger.info(f"  [INFO] Calculating file hash for duplicate detection...")
            file_hash = self._calculate_file_hash(pdf_path)
            
            # Check if PDF document already exists by file hash (prevent duplicate embeddings)
            try:
                # First check by file hash (most reliable)
                existing_pdf_response = self.client.table("pdf_documents")\
                    .select("id, title, status, file_hash")\
                    .eq("file_hash", file_hash)\
                    .limit(1)\
                    .execute()
                
                if existing_pdf_response.data and len(existing_pdf_response.data) > 0:
                    existing_pdf = existing_pdf_response.data[0]
                    existing_pdf_id = existing_pdf.get("id")
                    
                    # Check if embeddings exist for this PDF
                    embeddings_check = self.client.table("pdf_embeddings")\
                        .select("id")\
                        .eq("pdf_id", existing_pdf_id)\
                        .limit(1)\
                        .execute()
                    
                    if embeddings_check.data and len(embeddings_check.data) > 0:
                        logger.info(f"[SKIP] PDF '{assessment_title}' already processed with embeddings (file hash match) - skipping")
                        return {
                            "success": True,
                            "skipped": True,
                            "title": assessment_title,
                            "message": f"PDF '{assessment_title}' already processed - embeddings exist (same file hash)"
                        }
                    else:
                        logger.warning(f"[WARN] PDF with same hash exists but has no embeddings. Will process new copy.")
                
                # Fallback: Also check by title and file size (for PDFs without hash stored)
                existing_by_title = self.client.table("pdf_documents")\
                    .select("id, title, status, file_size")\
                    .ilike("title", assessment_title)\
                    .eq("file_size", pdf_file_size)\
                    .limit(5)\
                    .execute()
                
                if existing_by_title.data:
                    for existing in existing_by_title.data:
                        existing_pdf_id = existing.get("id")
                        embeddings_check = self.client.table("pdf_embeddings")\
                            .select("id")\
                            .eq("pdf_id", existing_pdf_id)\
                            .limit(1)\
                            .execute()
                        
                        if embeddings_check.data and len(embeddings_check.data) > 0:
                            logger.info(f"[SKIP] PDF '{assessment_title}' already processed with embeddings (title+size match) - skipping")
                            return {
                                "success": True,
                                "skipped": True,
                                "title": assessment_title,
                                "message": f"PDF '{assessment_title}' already processed - embeddings exist"
                            }
            except Exception as e:
                logger.warning(f"Error checking existing PDF: {str(e)} - continuing with processing")
            
            # Generate unique PDF ID
            pdf_id = str(uuid.uuid4())
            
            # ADD THIS CHECK BEFORE PROCESSING
            if not pdf_processor.openai_client:
                error_msg = "OpenAI client not initialized. Please configure OPENAI_API_KEY in your .env file."
                logger.error(f"  [FAILED] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Step 1: Store PDF document first
            logger.info(f"  [INFO] Storing PDF document...")
            pdf_doc_data = {
                "id": pdf_id,
                "title": assessment_title,
                "file_url": f"file://{pdf_path.absolute()}",
                "file_size": pdf_file_size,  # Use pre-calculated size
                "status": "processing"
            }
            
            # Only include file_hash if it was successfully calculated
            # (and if the column exists in the database schema)
            if file_hash:
                pdf_doc_data["file_hash"] = file_hash
            
            try:
                doc_response = self.client.table("pdf_documents").insert(pdf_doc_data).execute()
                if not doc_response.data:
                    return {
                        "success": False,
                        "error": "Failed to create pdf_documents record"
                    }
            except Exception as e:
                error_str = str(e)
                # If file_hash column doesn't exist, try without it
                if "file_hash" in error_str.lower() and file_hash:
                    logger.warning(f"[WARN] file_hash column not found, retrying without it...")
                    pdf_doc_data.pop("file_hash", None)
                    try:
                        doc_response = self.client.table("pdf_documents").insert(pdf_doc_data).execute()
                        if not doc_response.data:
                            return {
                                "success": False,
                                "error": "Failed to create pdf_documents record"
                            }
                    except Exception as retry_error:
                        logger.error(f"Error creating pdf_documents record: {str(retry_error)}")
                        return {
                            "success": False,
                            "error": f"Database error: {str(retry_error)}"
                        }
                else:
                    logger.error(f"Error creating pdf_documents record: {str(e)}")
                    return {
                        "success": False,
                        "error": f"Database error: {str(e)}"
                    }
            
            # Step 2: Process PDF page-by-page with batched embeddings (MEMORY-SAFE)
            # This method processes pages one at a time, chunks each page immediately,
            # generates embeddings in batches, and stores them immediately.
            # This prevents MemoryError for large PDFs by never accumulating all chunks in memory.
            logger.info(f"  [INFO] Processing PDF page-by-page with batched embeddings (memory-safe)...")
            try:
                result = pdf_processor.process_pdf_with_batched_embeddings(
                    pdf_file_path=str(pdf_path),
                    pdf_id=pdf_id,
                    pdf_title=assessment_title,
                    batch_size=100  # Process 100 chunks at a time (increased for better performance)
                )
                
                if not result.get("success"):
                    error_msg = result.get("error", "Failed to process PDF with batched embeddings")
                    logger.error(f"  [FAILED] {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg
                    }
                
                chunks_stored = result.get("chunks_stored", 0)
                total_chunks = result.get("total_chunks", 0)
                
                if chunks_stored == 0:
                    error_msg = "No embeddings were generated. Check OpenAI API key configuration or network connectivity."
                    logger.error(f"  [FAILED] {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg
                    }
                
                logger.info(f"  [OK] Processed {total_chunks} chunks, stored {chunks_stored} embeddings successfully")
                
                # Update PDF status to processed immediately after successful embedding storage
                try:
                    self.client.table("pdf_documents").update({"status": "processed"}).eq("id", pdf_id).execute()
                    logger.info(f"  [OK] Updated PDF status to 'processed'")
                except Exception as e:
                    logger.warning(f"  [WARN] Failed to update PDF status: {str(e)}")
                
            except Exception as e:
                # Check for specific error types
                error_type = type(e).__name__
                error_str = str(e).lower()
                
                if "timeout" in error_str or "timeout" in error_type.lower():
                    error_msg = f"Timeout error during PDF processing: {str(e)}. Network may be slow or batch too large."
                    logger.error(f"  [FAILED] {error_msg}")
                elif "connection" in error_str or "connection" in error_type.lower():
                    error_msg = f"Connection error during PDF processing: {str(e)}. Check internet connectivity."
                    logger.error(f"  [FAILED] {error_msg}")
                elif "rate limit" in error_str or "ratelimit" in error_type.lower():
                    error_msg = f"Rate limit error during PDF processing: {str(e)}. Wait before retrying."
                    logger.error(f"  [FAILED] {error_msg}")
                else:
                    error_msg = f"Unexpected error during PDF processing: {str(e)}"
                    logger.error(f"  [FAILED] {error_msg}")
                
                import traceback
                logger.error(f"Error type: {error_type}")
                logger.error(f"Full traceback:\n{traceback.format_exc()}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Step 3: Generate questions from PDF
            logger.info(f"  [INFO] Generating questions from PDF content...")
            result = assessment_generator.generate_questions_for_source(
                pdf_id=pdf_id,
                pdf_name=assessment_title,
                num_questions=10
            )
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "Failed to generate questions")
                }
            
            question_ids = result.get("question_ids", [])
            if not question_ids:
                return {
                    "success": False,
                    "error": "No questions generated"
                }
            
            # Step 4: Create assessment linked to course (with course_id)
            logger.info(f"  [INFO] Creating assessment linked to course '{course_name}'...")
            assessment = assessment_generator.create_assessment_from_questions(
                topic=course_name,  # Use course name as topic/skill_domain
                source_name=assessment_title,
                question_ids=question_ids,
                difficulty=result.get("difficulty", "medium"),
                question_count=len(result.get("questions", [])),
                course_id=course_id,  # Link to course directly
                assessment_title=assessment_title  # Use PDF filename as assessment title
            )
            
            if not assessment:
                return {
                    "success": False,
                    "error": "Failed to create assessment"
                }
            
            assessment_id = assessment.get("id")
            
            # Ensure PDF status is set to processed (in case it wasn't updated earlier)
            try:
                self.client.table("pdf_documents").update({"status": "processed"}).eq("id", pdf_id).execute()
            except Exception as e:
                logger.warning(f"Failed to update PDF status at end: {str(e)}")
            
            logger.info(f"[OK] Successfully created assessment: {assessment_title} in course: {course_name}")
            
            return {
                "success": True,
                "skipped": False,
                "assessment_id": str(assessment_id),
                "title": assessment_title,
                "course_id": course_id,
                "course_name": course_name,
                "question_count": len(question_ids),
                "message": f"Assessment '{assessment_title}' created in course '{course_name}'"
            }
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"[FAILED] Error processing PDF {pdf_path}: {str(e)}")
            logger.error(f"Full traceback:\n{error_trace}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_course_folder(self, folder_path: Path) -> Dict[str, Any]:
        """
        Process a course folder (folder name = course name)
        
        Args:
            folder_path: Path to course folder
        
        Returns:
            Dictionary with processing results
        """
        try:
            course_name = folder_path.name.strip()
            
            if not course_name:
                return {
                    "success": False,
                    "error": "Folder name cannot be empty"
                }
            
            logger.info(f"[INFO] Processing course folder: {course_name}")
            
            # Step 1: Get or create course
            course_id = self.get_or_create_course(course_name)
            if not course_id:
                return {
                    "success": False,
                    "error": f"Failed to get/create course: {course_name}"
                }
            
            # Step 2: Find all PDF files in folder
            pdf_files = list(folder_path.glob("*.pdf"))
            
            if not pdf_files:
                logger.warning(f"[WARN] No PDF files found in folder: {course_name}")
                return {
                    "success": True,
                    "course_name": course_name,
                    "course_id": course_id,
                    "pdfs_processed": 0,
                    "assessments_created": 0,
                    "assessments_skipped": 0,
                    "message": f"No PDF files found in folder: {course_name}"
                }
            
            logger.info(f"  Found {len(pdf_files)} PDF file(s) in folder: {course_name}")
            
            # Step 3: Process each PDF
            results = {
                "success": True,
                "course_name": course_name,
                "course_id": course_id,
                "pdfs_processed": 0,
                "assessments_created": 0,
                "assessments_skipped": 0,
                "assessments": [],
                "errors": []
            }
            
            for pdf_file in pdf_files:
                pdf_result = self.process_pdf_file(
                    pdf_path=pdf_file,
                    course_id=course_id,
                    course_name=course_name
                )
                
                results["pdfs_processed"] += 1
                
                if pdf_result.get("success"):
                    if pdf_result.get("skipped"):
                        results["assessments_skipped"] += 1
                    else:
                        results["assessments_created"] += 1
                    
                    results["assessments"].append({
                        "title": pdf_result.get("title"),
                        "assessment_id": pdf_result.get("assessment_id"),
                        "skipped": pdf_result.get("skipped", False)
                    })
                else:
                    results["errors"].append({
                        "pdf": pdf_file.name,
                        "error": pdf_result.get("error")
                    })
            
            logger.info(f"[OK] Completed processing folder '{course_name}': "
                       f"{results['assessments_created']} created, "
                       f"{results['assessments_skipped']} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing course folder {folder_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_all_folders(self) -> Dict[str, Any]:
        """
        Process all course folders in app/uploads/
        
        Returns:
            Dictionary with overall processing results
        """
        try:
            if not self.uploads_dir.exists():
                return {
                    "success": False,
                    "error": f"Uploads directory does not exist: {self.uploads_dir}"
                }
            
            # Find all folders (not files) in uploads directory
            folders = [f for f in self.uploads_dir.iterdir() if f.is_dir()]
            
            if not folders:
                logger.warning(f"[WARN] No course folders found in: {self.uploads_dir}")
                return {
                    "success": True,
                    "courses_processed": 0,
                    "message": "No course folders found"
                }
            
            logger.info(f"[INFO] Found {len(folders)} course folder(s) to process")
            
            results = {
                "success": True,
                "courses_processed": 0,
                "total_assessments_created": 0,
                "total_assessments_skipped": 0,
                "courses": [],
                "errors": []
            }
            
            for folder in folders:
                folder_result = self.process_course_folder(folder)
                
                if folder_result.get("success"):
                    results["courses_processed"] += 1
                    results["total_assessments_created"] += folder_result.get("assessments_created", 0)
                    results["total_assessments_skipped"] += folder_result.get("assessments_skipped", 0)
                    results["courses"].append(folder_result)
                else:
                    results["errors"].append({
                        "folder": folder.name,
                        "error": folder_result.get("error")
                    })
            
            logger.info(f"[OK] Completed processing: "
                       f"{results['courses_processed']} courses, "
                       f"{results['total_assessments_created']} assessments created, "
                       f"{results['total_assessments_skipped']} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing all folders: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


# Global service instance
folder_processor = FolderProcessor()

