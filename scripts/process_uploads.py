#!/usr/bin/env python3
"""
Standalone script to process PDFs from app/uploads/ folder

This script:
- Scans app/uploads/ for course folders
- Processes each PDF: Extract → Chunk → Embed → Store → Generate Questions → Create Assessment
- Prevents duplicates at every stage
- Logs progress clearly

Usage:
    python scripts/process_uploads.py                    # Process all PDFs
    python scripts/process_uploads.py --course "core java"  # Process specific course
    python scripts/process_uploads.py --dry-run         # Preview what would be processed

This script is separate from the web server and should be run manually
or via a scheduler (cron, systemd timer, Windows Task Scheduler, etc.)

IMPORTANT: This script does NOT run during uvicorn startup.
The web server starts instantly, and PDF processing is handled separately.
"""

import sys
import argparse
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.folder_processor import folder_processor
from app.utils.logger import setup_logger, logger


def main():
    """Main processing function"""
    parser = argparse.ArgumentParser(
        description="Process PDFs from app/uploads/ folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs in app/uploads/
  python scripts/process_uploads.py
  
  # Process specific course folder
  python scripts/process_uploads.py --course "core java"
  
  # Dry run (check what would be processed without actually processing)
  python scripts/process_uploads.py --dry-run
  
  # Verbose logging
  python scripts/process_uploads.py --verbose
        """
    )
    
    parser.add_argument(
        "--course",
        type=str,
        help="Process only a specific course folder (folder name)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without actually processing"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logger
    setup_logger("skill_assessment")
    
    print("=" * 60)
    print("PDF Processing Script")
    print("=" * 60)
    print()
    
    if args.dry_run:
        print("[DRY RUN] No changes will be made")
        print()
    
    try:
        if args.course:
            # Process specific course
            uploads_dir = Path("app/uploads")
            course_folder = uploads_dir / args.course
            
            if not course_folder.exists():
                print(f"[ERROR] Course folder not found: {course_folder}")
                return 1
            
            if not course_folder.is_dir():
                print(f"[ERROR] Path is not a directory: {course_folder}")
                return 1
            
            print(f"Processing course folder: {args.course}")
            print()
            
            if args.dry_run:
                pdf_files = list(course_folder.glob("*.pdf"))
                print(f"Would process {len(pdf_files)} PDF file(s):")
                for pdf in pdf_files:
                    print(f"  - {pdf.name}")
                return 0
            
            result = folder_processor.process_course_folder(course_folder)
            
        else:
            # Process all folders
            print("Processing all course folders in app/uploads/")
            print()
            
            if args.dry_run:
                uploads_dir = Path("app/uploads")
                if not uploads_dir.exists():
                    print("[INFO] Uploads directory does not exist")
                    return 0
                
                folders = [f for f in uploads_dir.iterdir() if f.is_dir()]
                print(f"Would process {len(folders)} course folder(s):")
                for folder in folders:
                    pdf_files = list(folder.glob("*.pdf"))
                    print(f"  - {folder.name}: {len(pdf_files)} PDF(s)")
                    for pdf in pdf_files:
                        print(f"    * {pdf.name}")
                return 0
            
            result = folder_processor.process_all_folders()
        
        # Display results
        print()
        print("=" * 60)
        print("Processing Results")
        print("=" * 60)
        
        if result.get("success"):
            if args.course:
                assessments_created = result.get("assessments_created", 0)
                assessments_skipped = result.get("assessments_skipped", 0)
                pdfs_processed = result.get("pdfs_processed", 0)
                
                print(f"[SUCCESS] Course processed successfully")
                print(f"  PDFs processed: {pdfs_processed}")
                print(f"  Assessments created: {assessments_created}")
                print(f"  Assessments skipped: {assessments_skipped}")
                
                if result.get("errors"):
                    print(f"  Errors: {len(result.get('errors', []))}")
                    for error in result.get("errors", []):
                        print(f"    - {error.get('pdf')}: {error.get('error')}")
            else:
                courses_processed = result.get("courses_processed", 0)
                total_created = result.get("total_assessments_created", 0)
                total_skipped = result.get("total_assessments_skipped", 0)
                
                print(f"[SUCCESS] Processing complete")
                print(f"  Courses processed: {courses_processed}")
                print(f"  Total assessments created: {total_created}")
                print(f"  Total assessments skipped: {total_skipped}")
                
                if result.get("errors"):
                    print(f"  Errors: {len(result.get('errors', []))}")
                    for error in result.get("errors", []):
                        print(f"    - {error.get('folder')}: {error.get('error')}")
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"[FAILED] Processing failed: {error_msg}")
            return 1
        
        print()
        print("=" * 60)
        print("[COMPLETE] PDF processing finished")
        print("=" * 60)
        
        return 0
        
    except KeyboardInterrupt:
        print()
        print("[INTERRUPTED] Processing cancelled by user")
        print("You can safely restart the script - it will skip already processed PDFs")
        return 130  # Standard exit code for Ctrl+C
        
    except Exception as e:
        print()
        print(f"[ERROR] Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

