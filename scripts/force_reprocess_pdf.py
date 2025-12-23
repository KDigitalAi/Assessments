#!/usr/bin/env python3
"""
Force re-process a PDF by deleting the old assessment and PDF document
This allows re-processing even if assessment already exists
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase_service import supabase_service
from app.utils.logger import setup_logger, logger
import argparse

setup_logger("skill_assessment")


def force_reprocess_pdf(pdf_title: str, course_name: str, dry_run: bool = True):
    """
    Delete assessment and PDF document to force re-processing
    
    Args:
        pdf_title: Title of the PDF (assessment title)
        course_name: Course name
        dry_run: If True, only show what would be deleted
    """
    client = supabase_service.get_client(use_service_key=True)
    
    if not client:
        print("Supabase client not available")
        return
    
    print("=" * 80)
    print("FORCE RE-PROCESS PDF")
    print("=" * 80)
    print()
    
    if dry_run:
        print("[DRY RUN] No changes will be made")
        print()
    
    # Find course
    course_response = client.table("courses")\
        .select("id, name")\
        .ilike("name", course_name)\
        .execute()
    
    course_id = None
    if course_response.data:
        for course in course_response.data:
            if course.get("name", "").strip().lower() == course_name.lower():
                course_id = course.get("id")
                print(f"Found course: {course.get('name')} (ID: {course_id})")
                break
    
    if not course_id:
        print(f"[ERROR] Course '{course_name}' not found")
        return
    
    # Find assessment
    assessment_response = client.table("assessments")\
        .select("id, title, course_id")\
        .eq("course_id", course_id)\
        .ilike("title", pdf_title)\
        .execute()
    
    assessment_id = None
    if assessment_response.data:
        for assessment in assessment_response.data:
            if assessment.get("title", "").strip().lower() == pdf_title.lower():
                assessment_id = assessment.get("id")
                print(f"Found assessment: {assessment.get('title')} (ID: {assessment_id})")
                break
    
    if not assessment_id:
        print(f"[INFO] Assessment '{pdf_title}' not found - nothing to delete")
        return
    
    # Find PDF documents with this title
    pdf_response = client.table("pdf_documents")\
        .select("id, title, status")\
        .ilike("title", pdf_title)\
        .execute()
    
    pdf_ids = []
    if pdf_response.data:
        for pdf in pdf_response.data:
            if pdf.get("title", "").strip().lower() == pdf_title.lower():
                pdf_id = pdf.get("id")
                pdf_ids.append(pdf_id)
                print(f"Found PDF: {pdf.get('title')} (ID: {pdf_id}, Status: {pdf.get('status')})")
    
    # Count embeddings for each PDF
    total_embeddings = 0
    for pdf_id in pdf_ids:
        emb_count = client.table("pdf_embeddings")\
            .select("id", count="exact")\
            .eq("pdf_id", pdf_id)\
            .execute()
        count = emb_count.count if hasattr(emb_count, 'count') else len(emb_count.data) if emb_count.data else 0
        total_embeddings += count
        print(f"  PDF {pdf_id[:20]}... has {count} embeddings")
    
    print()
    print(f"Summary:")
    print(f"  - Assessment ID: {assessment_id}")
    print(f"  - PDF documents: {len(pdf_ids)}")
    print(f"  - Total embeddings: {total_embeddings}")
    print()
    
    if not dry_run:
        print("Deleting in order:")
        print("  1. Questions linked to assessment...")
        try:
            # Delete questions
            questions_response = client.table("skill_assessment_questions")\
                .select("id")\
                .eq("assessment_id", assessment_id)\
                .execute()
            
            if questions_response.data:
                question_ids = [q["id"] for q in questions_response.data]
                # Delete in batches
                batch_size = 100
                for i in range(0, len(question_ids), batch_size):
                    batch = question_ids[i:i + batch_size]
                    client.table("skill_assessment_questions").delete().in_("id", batch).execute()
                print(f"     Deleted {len(question_ids)} questions")
            else:
                print("     No questions found")
        except Exception as e:
            logger.error(f"Error deleting questions: {str(e)}")
        
        print("  2. Embeddings for each PDF...")
        for pdf_id in pdf_ids:
            try:
                # Delete embeddings in batches
                batch_size = 500
                deleted = 0
                while True:
                    batch_response = client.table("pdf_embeddings")\
                        .select("id")\
                        .eq("pdf_id", pdf_id)\
                        .limit(batch_size)\
                        .execute()
                    
                    if not batch_response.data or len(batch_response.data) == 0:
                        break
                    
                    batch_ids = [emb["id"] for emb in batch_response.data]
                    client.table("pdf_embeddings").delete().in_("id", batch_ids).execute()
                    deleted += len(batch_ids)
                    print(f"     Deleted {deleted} embeddings for PDF {pdf_id[:20]}...")
                
            except Exception as e:
                logger.error(f"Error deleting embeddings for PDF {pdf_id}: {str(e)}")
        
        print("  3. PDF documents...")
        for pdf_id in pdf_ids:
            try:
                client.table("pdf_documents").delete().eq("id", pdf_id).execute()
                print(f"     Deleted PDF document {pdf_id[:20]}...")
            except Exception as e:
                logger.error(f"Error deleting PDF document {pdf_id}: {str(e)}")
        
        print("  4. Assessment...")
        try:
            client.table("assessments").delete().eq("id", assessment_id).execute()
            print(f"     Deleted assessment {assessment_id}")
        except Exception as e:
            logger.error(f"Error deleting assessment: {str(e)}")
        
        print()
        print("[OK] Cleanup complete! You can now re-process the PDF:")
        print(f"  python scripts/process_uploads.py --course '{course_name}'")
    else:
        print("[DRY RUN] Would delete:")
        print(f"  - Assessment: {assessment_id}")
        print(f"  - PDF documents: {len(pdf_ids)}")
        print(f"  - Total embeddings: {total_embeddings}")
        print()
        print("Run with --execute to actually delete them")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Force re-process a PDF by deleting old data")
    parser.add_argument(
        "--pdf-title",
        type=str,
        required=True,
        help="PDF/Assessment title to re-process"
    )
    parser.add_argument(
        "--course",
        type=str,
        required=True,
        help="Course name"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the deletion (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    try:
        force_reprocess_pdf(
            pdf_title=args.pdf_title,
            course_name=args.course,
            dry_run=not args.execute
        )
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        sys.exit(1)

