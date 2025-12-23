#!/usr/bin/env python3
"""
Cleanup script to delete duplicate PDF documents with no embeddings

This script:
- Finds PDF documents with no embeddings
- Identifies duplicates (same title, same file size, or same file hash)
- Deletes orphaned PDF documents (no embeddings)
- Keeps the PDF with embeddings if duplicates exist
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.supabase_service import supabase_service
from app.utils.logger import setup_logger, logger
from collections import defaultdict

setup_logger("skill_assessment")


def cleanup_duplicate_pdfs(dry_run: bool = True):
    """
    Clean up duplicate PDF documents
    
    Args:
        dry_run: If True, only show what would be deleted without actually deleting
    """
    client = supabase_service.get_client(use_service_key=True)
    
    if not client:
        logger.error("Supabase client not available")
        return
    
    print("=" * 80)
    print("PDF DUPLICATE CLEANUP")
    print("=" * 80)
    print()
    
    if dry_run:
        print("[DRY RUN] No changes will be made")
        print()
    
    # Get all PDF documents
    print("[1] Fetching all PDF documents...")
    try:
        # Try to get file_hash if column exists
        pdf_docs_response = client.table("pdf_documents").select("id, title, status, file_size, file_hash").execute()
    except Exception:
        # Fallback if file_hash column doesn't exist yet
        pdf_docs_response = client.table("pdf_documents").select("id, title, status, file_size").execute()
    
    pdf_docs = pdf_docs_response.data if pdf_docs_response.data else []
    
    print(f"   Found {len(pdf_docs)} PDF document(s)")
    print()
    
    # Check each PDF for embeddings
    pdfs_with_embeddings = set()
    pdfs_without_embeddings = []
    
    print("[2] Checking which PDFs have embeddings...")
    for pdf_doc in pdf_docs:
        pdf_id = pdf_doc.get("id")
        
        # Check if embeddings exist
        emb_response = client.table("pdf_embeddings")\
            .select("id")\
            .eq("pdf_id", pdf_id)\
            .limit(1)\
            .execute()
        
        if emb_response.data and len(emb_response.data) > 0:
            pdfs_with_embeddings.add(pdf_id)
        else:
            pdfs_without_embeddings.append(pdf_doc)
    
    print(f"   PDFs with embeddings: {len(pdfs_with_embeddings)}")
    print(f"   PDFs without embeddings: {len(pdfs_without_embeddings)}")
    print()
    
    if not pdfs_without_embeddings:
        print("[OK] No orphaned PDFs found (all PDFs have embeddings)")
        return
    
    # Group by title to find duplicates
    print("[3] Identifying duplicate PDFs...")
    by_title = defaultdict(list)
    by_hash = defaultdict(list)
    
    for pdf_doc in pdf_docs:
        title = pdf_doc.get("title", "")
        file_hash = pdf_doc.get("file_hash")
        pdf_id = pdf_doc.get("id")
        
        if title:
            by_title[title].append(pdf_doc)
        
        if file_hash:
            by_hash[file_hash].append(pdf_doc)
    
    # Find duplicates
    duplicates_by_title = {title: pdfs for title, pdfs in by_title.items() if len(pdfs) > 1}
    duplicates_by_hash = {file_hash: pdfs for file_hash, pdfs in by_hash.items() if len(pdfs) > 1}
    
    print(f"   Duplicate groups by title: {len(duplicates_by_title)}")
    print(f"   Duplicate groups by hash: {len(duplicates_by_hash)}")
    print()
    
    # Identify PDFs to delete
    pdfs_to_delete = []
    
    print("[4] Identifying PDFs to delete...")
    
    # Delete PDFs without embeddings that have duplicates with embeddings
    for title, pdf_list in duplicates_by_title.items():
        pdfs_with_emb = [p for p in pdf_list if p.get("id") in pdfs_with_embeddings]
        pdfs_without_emb = [p for p in pdf_list if p.get("id") not in pdfs_with_embeddings]
        
        if pdfs_with_emb and pdfs_without_emb:
            # Keep PDFs with embeddings, delete ones without
            for pdf in pdfs_without_emb:
                pdfs_to_delete.append({
                    "pdf": pdf,
                    "reason": f"Duplicate of '{title}' - PDF with embeddings exists"
                })
    
    # Also check by file hash
    for file_hash, pdf_list in duplicates_by_hash.items():
        pdfs_with_emb = [p for p in pdf_list if p.get("id") in pdfs_with_embeddings]
        pdfs_without_emb = [p for p in pdf_list if p.get("id") not in pdfs_with_embeddings]
        
        if pdfs_with_emb and pdfs_without_emb:
            # Keep PDFs with embeddings, delete ones without
            for pdf in pdfs_without_emb:
                pdf_id = pdf.get("id")
                # Avoid duplicates in the list
                if not any(d["pdf"].get("id") == pdf_id for d in pdfs_to_delete):
                    pdfs_to_delete.append({
                        "pdf": pdf,
                        "reason": f"Duplicate by file hash - PDF with embeddings exists"
                    })
    
    # Also delete standalone PDFs without embeddings (not duplicates, just orphaned)
    for pdf in pdfs_without_embeddings:
        pdf_id = pdf.get("id")
        # Only add if not already in delete list
        if not any(d["pdf"].get("id") == pdf_id for d in pdfs_to_delete):
            pdfs_to_delete.append({
                "pdf": pdf,
                "reason": "No embeddings and no duplicates found"
            })
    
    print(f"   PDFs identified for deletion: {len(pdfs_to_delete)}")
    print()
    
    if not pdfs_to_delete:
        print("[OK] No PDFs to delete")
        return
    
    # Show what will be deleted
    print("[5] PDFs to be deleted:")
    print("-" * 80)
    for item in pdfs_to_delete:
        pdf = item["pdf"]
        print(f"  ID: {pdf.get('id')}")
        print(f"  Title: {pdf.get('title', 'N/A')}")
        print(f"  Status: {pdf.get('status', 'N/A')}")
        print(f"  File Size: {pdf.get('file_size', 'N/A')}")
        print(f"  Reason: {item['reason']}")
        print()
    
    # Delete if not dry run
    if not dry_run:
        print("[6] Deleting PDFs...")
        deleted_count = 0
        failed_count = 0
        
        for item in pdfs_to_delete:
            pdf = item["pdf"]
            pdf_id = pdf.get("id")
            pdf_title = pdf.get("title", "Unknown")
            
            try:
                # Delete from pdf_documents table
                client.table("pdf_documents").delete().eq("id", pdf_id).execute()
                deleted_count += 1
                logger.info(f"[OK] Deleted PDF: {pdf_title} (ID: {pdf_id[:8]}...)")
            except Exception as e:
                failed_count += 1
                logger.error(f"[FAILED] Error deleting PDF {pdf_title}: {str(e)}")
        
        print(f"   Deleted: {deleted_count}")
        print(f"   Failed: {failed_count}")
    else:
        print("[DRY RUN] Would delete the PDFs listed above")
        print("   Run with --execute to actually delete them")
    
    print()
    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up duplicate PDF documents")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete PDFs (default is dry-run)"
    )
    
    args = parser.parse_args()
    
    try:
        cleanup_duplicate_pdfs(dry_run=not args.execute)
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        sys.exit(1)

