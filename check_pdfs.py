"""
Diagnostic script to check PDF status in database
"""
import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("[ERROR] SUPABASE_URL and SUPABASE_KEY must be set in .env file")
    exit(1)

# Create Supabase client
client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("PDF DIAGNOSTIC REPORT")
print("=" * 60)
print()

# Check pdf_embeddings table
print("1. Checking pdf_embeddings table...")
try:
    embeddings_response = client.table("pdf_embeddings")\
        .select("pdf_id, pdf_title")\
        .execute()
    
    if embeddings_response.data:
        # Get unique PDFs
        unique_pdfs = {}
        for row in embeddings_response.data:
            pdf_id = row.get("pdf_id")
            if pdf_id:
                if pdf_id not in unique_pdfs:
                    unique_pdfs[pdf_id] = {
                        "pdf_id": pdf_id,
                        "pdf_title": row.get("pdf_title", "Unknown"),
                        "chunk_count": 0
                    }
                unique_pdfs[pdf_id]["chunk_count"] += 1
        
        print(f"   [OK] Found {len(unique_pdfs)} unique PDFs with embeddings")
        print(f"   [OK] Total embedding chunks: {len(embeddings_response.data)}")
        print()
        print("   PDFs with embeddings:")
        for i, (pdf_id, pdf_info) in enumerate(unique_pdfs.items(), 1):
            print(f"   {i:2d}. {pdf_info['pdf_title']} (ID: {pdf_id[:20]}...) - {pdf_info['chunk_count']} chunks")
    else:
        print("   [WARN] No PDFs found in pdf_embeddings table")
        print("   This means no PDFs have embeddings generated yet")
        
except Exception as e:
    print(f"   [ERROR] Error querying pdf_embeddings: {str(e)}")

print()
print("=" * 60)

# Check assessments table
print("2. Checking existing assessments...")
try:
    assessments_response = client.table("assessments")\
        .select("id, title, skill_domain")\
        .execute()
    
    if assessments_response.data:
        print(f"   [OK] Found {len(assessments_response.data)} existing assessments")
        print()
        print("   Existing assessments:")
        for i, assessment in enumerate(assessments_response.data[:20], 1):  # Show first 20
            print(f"   {i:2d}. {assessment.get('title', 'Unknown')} (Domain: {assessment.get('skill_domain', 'Unknown')})")
        if len(assessments_response.data) > 20:
            print(f"   ... and {len(assessments_response.data) - 20} more")
    else:
        print("   [WARN] No assessments found")
        
except Exception as e:
    print(f"   [ERROR] Error querying assessments: {str(e)}")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)

if embeddings_response.data:
    unique_count = len(unique_pdfs)
    assessment_count = len(assessments_response.data) if assessments_response.data else 0
    
    print(f"PDFs with embeddings: {unique_count}")
    print(f"Assessments created: {assessment_count}")
    print()
    
    if unique_count > assessment_count:
        missing = unique_count - assessment_count
        print(f"[WARN] {missing} PDF(s) have embeddings but no assessment yet")
        print("   Run assessment generation to create assessments for these PDFs")
    elif unique_count == assessment_count:
        print("[OK] All PDFs with embeddings have assessments")
    else:
        print("[INFO] More assessments than PDFs (may include video-based assessments)")
    
    if unique_count < 33:
        missing_embeddings = 33 - unique_count
        print()
        print(f"[WARN] {missing_embeddings} PDF(s) uploaded but no embeddings found")
        print("   These PDFs need embeddings generated first before assessments can be created")
        print("   Check your PDF upload/embedding generation process")

print()
print("=" * 60)

