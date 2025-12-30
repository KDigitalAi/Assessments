"""
API routes for PDF upload and processing
"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import Dict, Any
from app.services.pdf_processor import pdf_processor
from app.services.supabase_service import supabase_service
from app.utils.logger import logger
import uuid
from datetime import datetime

router = APIRouter(prefix="/api/pdf", tags=["PDF Processing"])


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    title: str = None
):
    """
    Upload PDF file and initiate processing pipeline
    
    Steps:
    1. Upload file to Supabase Storage
    2. Create pdf_documents record
    3. Create pdf_processing_log record
    4. Start background processing (extract → chunk → embed)
    
    Returns:
        PDF document metadata
    """
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are supported"
            )
        
        # Read file content
        logger.info(f"Reading PDF file: {file.filename}")
        file_content = await file.read()
        file_size = len(file_content)
        logger.debug(f"File read completed: {file_size} bytes")
        
        # Generate unique PDF ID
        pdf_id = str(uuid.uuid4())
        
        # Use provided title or filename
        pdf_title = title or file.filename.replace('.pdf', '')
        
        # Upload to Supabase Storage
        client = supabase_service.get_client(use_service_key=True)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service unavailable"
            )
        
        # Upload file to storage bucket 'pdfs'
        storage_path = f"{pdf_id}/{file.filename}"
        logger.info(f"Uploading file to Supabase Storage: {storage_path}")
        try:
            storage_response = client.storage.from_("pdfs").upload(
                path=storage_path,
                file=file_content,
                file_options={"content-type": "application/pdf"}
            )
            file_url = client.storage.from_("pdfs").get_public_url(storage_path)
        except Exception as e:
            logger.error(f"Error uploading to storage: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file to storage: {str(e)}"
            )
        
        # Create pdf_documents record
        pdf_doc_data = {
            "id": pdf_id,
            "title": pdf_title,
            "file_url": file_url,
            "file_size": file_size,
            "status": "uploaded"
        }
        
        logger.debug(f"Creating pdf_documents record for PDF: {pdf_id}")
        try:
            doc_response = client.table("pdf_documents").insert(pdf_doc_data).execute()
            if not doc_response.data:
                raise Exception("Failed to create pdf_documents record")
        except Exception as e:
            logger.error(f"Error creating pdf_documents record: {str(e)}")
            # Try to clean up storage
            try:
                client.storage.from_("pdfs").remove([storage_path])
                logger.debug(f"Cleaned up storage file: {storage_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up storage file {storage_path}: {str(cleanup_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create document record: {str(e)}"
            )
        
        # Create processing log
        log_data = {
            "pdf_id": pdf_id,
            "status": "uploaded",
            "chunks_created": 0
        }
        
        try:
            client.table("pdf_processing_log").insert(log_data).execute()
        except Exception as e:
            logger.warning(f"Error creating processing log: {str(e)}")
        
        # Start background processing (async)
        # In production, use a task queue (Celery, etc.)
        # For now, we'll process synchronously
        try:
            logger.info(f"Starting background processing for PDF: {pdf_id}")
            await process_pdf_background(pdf_id, file_content)
            logger.info(f"Background processing completed successfully for PDF: {pdf_id}")
        except Exception as e:
            logger.exception(f"Background PDF processing failed for PDF {pdf_id}: {str(e)}")
            # Update status to error
            try:
                client.table("pdf_documents").update({
                    "status": "error",
                    "error_message": str(e)
                }).eq("id", pdf_id).execute()
            except Exception as update_error:
                logger.error(f"Failed to update PDF status to error: {str(update_error)}")
            # Re-raise to ensure caller knows processing failed
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF processing failed: {str(e)}"
            )
        
        return {
            "success": True,
            "pdf_id": pdf_id,
            "title": pdf_title,
            "file_url": file_url,
            "file_size": file_size,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading PDF: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading PDF: {str(e)}"
        )


async def process_pdf_background(pdf_id: str, file_content: bytes):
    """
    Background processing: Extract → Chunk → Embed → Store
    
    Args:
        pdf_id: PDF document ID
        file_content: PDF file bytes
    """
    try:
        client = supabase_service.get_client(use_service_key=True)
        
        # Update status to processing
        client.table("pdf_documents").update({"status": "processing"}).eq("id", pdf_id).execute()
        pdf_processor.update_processing_log(pdf_id, "extracting")
        
        # Get PDF title
        pdf_doc = client.table("pdf_documents").select("title").eq("id", pdf_id).execute()
        if not pdf_doc.data or len(pdf_doc.data) == 0:
            logger.error(f"PDF metadata not found for pdf_id: {pdf_id}")
            raise ValueError(f"Invalid pdf_id: {pdf_id}")
        
        pdf_title = pdf_doc.data[0]["title"]
        
        # Extract text from PDF
        import io
        pdf_file = io.BytesIO(file_content)
        pages = pdf_processor.extract_text_from_pdf(pdf_file)
        
        if not pages:
            raise Exception("No text extracted from PDF")
        
        pdf_processor.update_processing_log(pdf_id, "chunking")
        
        # Process into chunks
        chunks = pdf_processor.process_pdf_pages(pages)
        
        if not chunks:
            raise Exception("No chunks created from PDF")
        
        pdf_processor.update_processing_log(pdf_id, "embedding", chunks_created=len(chunks))
        
        # Generate embeddings
        chunks_with_embeddings = pdf_processor.generate_embeddings_for_chunks(chunks)
        
        if not chunks_with_embeddings:
            raise Exception("No embeddings generated")
        
        # Store embeddings
        success = pdf_processor.store_pdf_embeddings(pdf_id, pdf_title, chunks_with_embeddings)
        
        if not success:
            raise Exception("Failed to store embeddings")
        
        # Update status to processed
        client.table("pdf_documents").update({"status": "processed"}).eq("id", pdf_id).execute()
        pdf_processor.update_processing_log(pdf_id, "completed", chunks_created=len(chunks_with_embeddings))
        
        logger.info(f"Successfully processed PDF {pdf_id}: {len(chunks_with_embeddings)} chunks")
        
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_id}: {str(e)}")
        client = supabase_service.get_client(use_service_key=True)
        client.table("pdf_documents").update({
            "status": "error",
            "error_message": str(e)
        }).eq("id", pdf_id).execute()
        pdf_processor.update_processing_log(pdf_id, "error", error_message=str(e))
        raise


@router.get("/list")
async def list_pdfs():
    """
    List all uploaded PDFs with their processing status
    
    Returns:
        List of PDF documents
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        response = client.table("pdf_documents")\
            .select("*")\
            .order("upload_date", desc=True)\
            .execute()
        
        return {
            "success": True,
            "pdfs": response.data if response.data else []
        }
        
    except Exception as e:
        logger.error(f"Error listing PDFs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing PDFs: {str(e)}"
        )


@router.get("/{pdf_id}/status")
async def get_pdf_status(pdf_id: str):
    """
    Get PDF processing status
    
    Returns:
        PDF document and processing log
    """
    try:
        client = supabase_service.get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service unavailable"
            )
        
        # Get PDF document
        pdf_response = client.table("pdf_documents")\
            .select("*")\
            .eq("id", pdf_id)\
            .execute()
        
        if not pdf_response.data or len(pdf_response.data) == 0:
            logger.warning(f"PDF not found: {pdf_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF not found"
            )
        
        logger.debug(f"Retrieved PDF data for pdf_id: {pdf_id}")
        
        # Get processing log
        log_response = client.table("pdf_processing_log")\
            .select("*")\
            .eq("pdf_id", pdf_id)\
            .execute()
        
        return {
            "success": True,
            "pdf": pdf_response.data[0],
            "processing_log": log_response.data[0] if log_response.data and len(log_response.data) > 0 else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PDF status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting PDF status: {str(e)}"
        )

