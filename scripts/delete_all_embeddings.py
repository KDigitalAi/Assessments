#!/usr/bin/env python3
"""
Delete ALL embeddings from Supabase for clean re-upload

This script will:
1. Delete all embeddings from pdf_embeddings table
2. Optionally delete PDF documents and assessments
3. Process in batches to avoid timeouts
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase_service import supabase_service
from app.utils.logger import setup_logger, logger
import argparse

setup_logger("skill_assessment")


def delete_all_embeddings(
    delete_pdfs: bool = False,
    delete_assessments: bool = False,
    dry_run: bool = True
):
    """
    Delete all embeddings (and optionally PDFs and assessments)
    
    Args:
        delete_pdfs: Also delete PDF documents
        delete_assessments: Also delete assessments
        dry_run: If True, only show what would be deleted
    """
    client = supabase_service.get_client(use_service_key=True)
    
    if not client:
        print("Supabase client not available")
        return
    
    print("=" * 80)
    print("DELETE ALL EMBEDDINGS FROM SUPABASE")
    print("=" * 80)
    print()
    
    if dry_run:
        print("[DRY RUN] No changes will be made")
        print()
    
    # Count total embeddings
    print("[1] Counting total embeddings...")
    try:
        count_response = client.table("pdf_embeddings")\
            .select("id", count="exact")\
            .execute()
        
        total_embeddings = count_response.count if hasattr(count_response, 'count') else len(count_response.data) if count_response.data else 0
        print(f"   Total embeddings: {total_embeddings:,}")
    except Exception as e:
        logger.error(f"Error counting embeddings: {str(e)}")
        return
    
    if total_embeddings == 0:
        print("\n[OK] No embeddings to delete")
        return
    
    # Count PDFs and assessments if needed
    if delete_pdfs:
        print("\n[2] Counting PDF documents...")
        try:
            pdf_response = client.table("pdf_documents")\
                .select("id", count="exact")\
                .execute()
            total_pdfs = pdf_response.count if hasattr(pdf_response, 'count') else len(pdf_response.data) if pdf_response.data else 0
            print(f"   Total PDF documents: {total_pdfs:,}")
        except Exception as e:
            logger.error(f"Error counting PDFs: {str(e)}")
            total_pdfs = 0
    else:
        total_pdfs = 0
    
    if delete_assessments:
        print("\n[3] Counting assessments...")
        try:
            assessment_response = client.table("assessments")\
                .select("id", count="exact")\
                .execute()
            total_assessments = assessment_response.count if hasattr(assessment_response, 'count') else len(assessment_response.data) if assessment_response.data else 0
            print(f"   Total assessments: {total_assessments:,}")
        except Exception as e:
            logger.error(f"Error counting assessments: {str(e)}")
            total_assessments = 0
    else:
        total_assessments = 0
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Embeddings to delete: {total_embeddings:,}")
    if delete_pdfs:
        print(f"PDF documents to delete: {total_pdfs:,}")
    if delete_assessments:
        print(f"Assessments to delete: {total_assessments:,}")
    print()
    
    if dry_run:
        print("[DRY RUN] Would delete the items listed above")
        print("Run with --execute to actually delete them")
        print()
        print("Options:")
        print("  --delete-pdfs        Also delete PDF documents")
        print("  --delete-assessments Also delete assessments")
        return
    
    # Confirm deletion
    print("[WARNING] This will permanently delete all embeddings!")
    if delete_pdfs:
        print("[WARNING] This will also delete all PDF documents!")
    if delete_assessments:
        print("[WARNING] This will also delete all assessments!")
    print()
    
    # Delete in order: assessments -> questions -> embeddings -> PDFs
    if delete_assessments:
        print("\n[4] Deleting assessments and questions...")
        try:
            # Get all assessments
            assessments = client.table("assessments").select("id").execute()
            
            if assessments.data:
                assessment_ids = [a["id"] for a in assessments.data]
                
                # Delete questions first
                for assessment_id in assessment_ids:
                    try:
                        questions = client.table("skill_assessment_questions")\
                            .select("id")\
                            .eq("assessment_id", assessment_id)\
                            .execute()
                        
                        if questions.data:
                            question_ids = [q["id"] for q in questions.data]
                            # Delete in batches
                            batch_size = 100
                            for i in range(0, len(question_ids), batch_size):
                                batch = question_ids[i:i + batch_size]
                                client.table("skill_assessment_questions").delete().in_("id", batch).execute()
                    except Exception as e:
                        logger.warning(f"Error deleting questions for assessment {assessment_id}: {str(e)}")
                
                # Delete assessments
                batch_size = 100
                for i in range(0, len(assessment_ids), batch_size):
                    batch = assessment_ids[i:i + batch_size]
                    client.table("assessments").delete().in_("id", batch).execute()
                    print(f"   Deleted {min(i + batch_size, len(assessment_ids))}/{len(assessment_ids)} assessments")
                
                print(f"   [OK] Deleted {len(assessment_ids)} assessments")
        except Exception as e:
            logger.error(f"Error deleting assessments: {str(e)}")
    
    # Delete embeddings in batches
    print("\n[5] Deleting all embeddings in batches...")
    deleted_embeddings = 0
    batch_size = 500
    
    try:
        while True:
            # Fetch a batch of embedding IDs
            batch_response = client.table("pdf_embeddings")\
                .select("id")\
                .limit(batch_size)\
                .execute()
            
            if not batch_response.data or len(batch_response.data) == 0:
                break
            
            batch_ids = [emb["id"] for emb in batch_response.data]
            
            # Delete this batch
            try:
                client.table("pdf_embeddings").delete().in_("id", batch_ids).execute()
                deleted_embeddings += len(batch_ids)
                print(f"   Deleted {deleted_embeddings:,}/{total_embeddings:,} embeddings ({deleted_embeddings*100//total_embeddings}%)")
            except Exception as e:
                logger.error(f"Error deleting batch: {str(e)}")
                # Try individual deletes as fallback
                for emb_id in batch_ids:
                    try:
                        client.table("pdf_embeddings").delete().eq("id", emb_id).execute()
                        deleted_embeddings += 1
                    except:
                        pass
                break
        
        print(f"\n   [OK] Deleted {deleted_embeddings:,} embeddings")
    except Exception as e:
        logger.error(f"Error deleting embeddings: {str(e)}")
    
    # Delete PDF documents if requested
    if delete_pdfs:
        print("\n[6] Deleting PDF documents...")
        try:
            pdfs = client.table("pdf_documents").select("id").execute()
            
            if pdfs.data:
                pdf_ids = [p["id"] for p in pdfs.data]
                batch_size = 100
                for i in range(0, len(pdf_ids), batch_size):
                    batch = pdf_ids[i:i + batch_size]
                    client.table("pdf_documents").delete().in_("id", batch).execute()
                    print(f"   Deleted {min(i + batch_size, len(pdf_ids))}/{len(pdf_ids)} PDF documents")
                
                print(f"   [OK] Deleted {len(pdf_ids)} PDF documents")
        except Exception as e:
            logger.error(f"Error deleting PDF documents: {str(e)}")
    
    print()
    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
    print()
    print("You can now re-upload and process your PDFs:")
    print("  python scripts/process_uploads.py")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Delete all embeddings from Supabase for clean re-upload",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (show what would be deleted)
  python scripts/delete_all_embeddings.py
  
  # Delete only embeddings
  python scripts/delete_all_embeddings.py --execute
  
  # Delete embeddings and PDF documents
  python scripts/delete_all_embeddings.py --delete-pdfs --execute
  
  # Delete everything (embeddings, PDFs, assessments)
  python scripts/delete_all_embeddings.py --delete-pdfs --delete-assessments --execute
        """
    )
    parser.add_argument(
        "--delete-pdfs",
        action="store_true",
        help="Also delete PDF documents"
    )
    parser.add_argument(
        "--delete-assessments",
        action="store_true",
        help="Also delete assessments (and their questions)"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually perform the deletion (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    try:
        delete_all_embeddings(
            delete_pdfs=args.delete_pdfs,
            delete_assessments=args.delete_assessments,
            dry_run=not args.execute
        )
    except KeyboardInterrupt:
        print("\n\n[INFO] Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        sys.exit(1)

