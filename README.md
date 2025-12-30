# Skill Assessment Platform API

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-2.22+-orange.svg)](https://supabase.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple.svg)](https://openai.com/)

> **API-only backend service** for creating, delivering, and evaluating skill assessments using OpenAI GPT-4 and vector embeddings. Designed for integration with Edify frontend.

---

## Overview

**Skill Assessment Platform API** is a **backend-only REST API service** that automates the complete assessment lifecycle from PDF upload to results delivery. This service provides RESTful APIs for frontend applications (like Edify) to integrate assessment functionality.

### Complete Pipeline

**PDF → Embeddings → Questions → Assessments → Courses → Attempts → Results**

The system:
- Accepts PDF document uploads via API
- Extracts text and generates vector embeddings
- Uses RAG (Retrieval-Augmented Generation) to generate contextual MCQ questions
- Creates assessments organized by courses
- Delivers assessments through API endpoints
- Automatically scores responses and provides AI-generated feedback

### Key Features

- **PDF-Based System**: Upload and process PDF documents exclusively
- **End-to-End Pipeline**: Complete workflow from PDF upload to assessment results
- **AI-Powered Question Generation**: Automatically generates MCQ questions from PDF content using OpenAI GPT-4o-mini
- **RAG-Powered**: Uses vector embeddings for context-aware question generation
- **Course-Based Organization**: Organizes assessments by courses with automatic course detection
- **Automated Scoring**: Instant scoring for MCQ questions
- **Personalized Feedback**: AI-generated feedback based on performance
- **JWT Authentication**: Secure authentication via Supabase Auth
- **Progress Tracking**: Monitor user progress across courses and assessments
- **API-Only**: Clean REST API service ready for frontend integration

---

## System Architecture

### Architecture Overview

This is a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                       │
│  Edify Frontend (Separate codebase - React/Vue/etc)        │
│  Consumes REST APIs via HTTPS + JWT Bearer Tokens          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      API LAYER (FastAPI)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Middleware Stack                                     │  │
│  │  • CORS (Edify domains)                               │  │
│  │  • Request ID Generation                             │  │
│  │  • Request Timing                                    │  │
│  │  • Rate Limiting (100 req/min)                      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Route Handlers                                      │  │
│  │  • /api/* (Dashboard, Assessments)                  │  │
│  │  • /auth/* (Authentication)                        │  │
│  │  • /api/pdf/* (PDF Upload)                          │  │
│  │  • /api/folder/* (Folder Upload)                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Exception Handlers                                  │  │
│  │  • Global Exception Handler                          │  │
│  │  • AppException Handler                              │  │
│  │  • HTTPException Handler                             │  │
│  │  • ValidationError Handler                           │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                     SERVICE LAYER                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Assessment   │  │ PDF          │  │ RAG          │    │
│  │ Generator    │  │ Processor    │  │ Service      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │            │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐    │
│  │ Topic        │  │ Embedding    │  │ Feedback     │    │
│  │ Question     │  │ Service      │  │ Service      │    │
│  │ Service      │  └──────────────┘  └──────────────┘    │
│  └──────────────┘                                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Supabase Service (Database + Storage)                │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATA LAYER (Supabase)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  PostgreSQL Database (10 Tables)                     │  │
│  │  • Core Assessment Tables (7)                       │  │
│  │  • PDF/RAG Tables (3)                               │  │
│  │  • pgvector Extension (vector similarity)           │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Supabase Storage (PDF files in 'pdfs' bucket)      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Supabase Auth (JWT authentication)                  │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  EXTERNAL INTEGRATIONS                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  OpenAI API                                           │  │
│  │  • GPT-4o-mini (question generation, feedback)     │  │
│  │  • text-embedding-3-small (1536-dim embeddings)     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Components

1. **FastAPI Backend**: RESTful API server with async/await support
   - Middleware: CORS, Request ID, Timing, Rate Limiting
   - Exception handling: Centralized error handlers
   - Route organization: Modular route handlers by feature

2. **Supabase Database**: PostgreSQL with pgvector extension
   - 10 tables: 7 core assessment tables + 3 PDF/RAG tables
   - Vector similarity search via `match_pdf_embeddings()` function
   - Row Level Security (RLS) for data access control

3. **Supabase Auth**: JWT-based authentication
   - Token validation on protected endpoints
   - User profile management
   - Token expiration handling

4. **OpenAI API**: Direct integration for AI features
   - Question generation (GPT-4o-mini)
   - Embedding generation (text-embedding-3-small)
   - Feedback generation (GPT-4o-mini)
   - Timeout handling (60 seconds) with retry logic

5. **Service Layer**: Business logic services
   - Assessment generation from PDF embeddings
   - PDF processing (extract, chunk, embed)
   - RAG search (vector similarity)
   - Feedback generation
   - Database operations abstraction

**Note**: This is an **API-only backend service**. Frontend UI is handled separately by the Edify team.

### Data Flow

#### Phase 1: PDF Upload & Processing

1. **Upload**: Frontend uploads PDF via `POST /api/pdf/upload`
2. **Storage**: File stored in Supabase Storage (bucket: `pdfs`)
3. **Metadata**: PDF metadata recorded in `pdf_documents` table (status: `uploaded`)
4. **Logging**: Processing status tracked in `pdf_processing_log` table
5. **Background Processing** (async):
   - Status → `processing`
   - **Extract**: PyPDF2 extracts text page-by-page
   - **Chunk**: Text split into 500-1000 character segments
   - **Embed**: OpenAI API generates embeddings (batch processing)
   - **Store**: Chunks + embeddings stored in `pdf_embeddings` table
   - Status → `processed`

#### Phase 2: Question Generation (RAG)

1. **Trigger**: Call `POST /api/generateAssessments`
2. **Source Retrieval**: Service reads all PDF sources from `pdf_embeddings` table
3. **For Each PDF**:
   - Retrieve chunks via `get_chunks_for_source()`
   - **Vector Search**: RAG service performs similarity search
   - **Context Retrieval**: Top-k similar chunks retrieved (default: 10, threshold: 0.7)
   - **Question Generation**: OpenAI GPT-4o-mini generates MCQ questions with context
   - **Storage**: Questions stored in `skill_assessment_questions` table

#### Phase 3: Assessment Creation

1. **Grouping**: Questions grouped by topic/skill domain
2. **Assessment Record**: Created in `assessments` table
3. **Blueprint**: `question_ids` stored in `blueprint` JSONB field
4. **Course Link**: Assessment linked to course via `course_id` in `courses` table
5. **Status**: Assessment set to `published` status

#### Phase 4: User Assessment Flow

1. **Authentication**: User authenticates via `POST /auth/login` (returns JWT token)
2. **Browse**: Frontend calls `GET /api/assessments?course_id={id}` to view assessments
3. **Start**: User starts assessment → `GET /api/assessments/{id}/questions`
   - Creates `attempts` record (status: `in_progress`)
   - Returns questions to frontend
4. **Submit**: User submits answers → `POST /api/submitAssessment`
   - Stores answers in `responses` table
   - Auto-scores MCQ questions (compares `selected_option` with `correct_answer`)
   - Updates `attempts` record (status: `completed`, scores calculated)
   - Creates `results` record with overall scores
5. **Feedback**: AI feedback generated via `feedback_service`
   - Analyzes performance (score, percentage, topic breakdown)
   - Generates personalized feedback using OpenAI GPT-4o-mini
   - Stores feedback in `results` table
6. **Retrieve**: Frontend retrieves results via `GET /api/attempts/{attempt_id}/result`

---

## Technology Stack

### Backend
- **Python 3.10+**: Core programming language
- **FastAPI 0.104.1**: Modern async web framework
- **Uvicorn**: ASGI server
- **Pydantic 2.6+**: Data validation and settings
- **Python-dotenv**: Environment management

### Database & Authentication
- **Supabase**: Backend-as-a-Service (PostgreSQL)
- **pgvector**: Vector extension for embeddings
- **Supabase Auth**: JWT-based authentication
- **Row Level Security (RLS)**: Database-level access control

### AI Services
- **OpenAI GPT-4o-mini**: LLM for question generation
- **OpenAI text-embedding-3-small**: Embedding model for RAG search

### API Features
- **RESTful API**: Standard HTTP methods and status codes
- **CORS**: Configured for Edify frontend integration
- **JWT Authentication**: Bearer token-based auth
- **Request Validation**: Pydantic models for request/response validation
- **Error Handling**: Standardized error responses

---

## Installation

### Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **Supabase Account** with a **NEW project** (separate from chatbot/RAG database)
- **OpenAI API Key** (for question generation and embeddings)
- **Git** (for cloning repository)

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd Assessments
```

### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
python -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Supabase Configuration (Required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key

# OpenAI Configuration (Required)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Application Settings
DEBUG=True
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**Where to get credentials:**
- **Supabase**: https://app.supabase.com/project/YOUR_PROJECT/settings/api
- **OpenAI**: https://platform.openai.com/api-keys

---

## Supabase Setup

### Step 1: Create NEW Supabase Project

**CRITICAL**: Create a **separate Supabase project** for this assessment system.

1. Go to https://app.supabase.com
2. Click **"New Project"**
3. Name it: `assessment-platform` (or your preferred name)
4. Wait for database initialization
5. **Do NOT reuse your existing chatbot/RAG database**

### Step 2: Run Database Schema

1. Go to **SQL Editor** in Supabase Dashboard
2. Open `app/models/assessment_schema.sql`
3. Copy and paste the entire SQL script
4. Click **Run** to execute

This creates exactly **10 tables**:
- **7 Core Assessment Tables**: profiles, courses, assessments, skill_assessment_questions, attempts, responses, results
- **3 PDF/RAG Tables**: pdf_documents, pdf_embeddings, pdf_processing_log

Also creates:
- Vector similarity search function: `match_pdf_embeddings()`
- Indexes for performance
- Foreign key constraints
- Auto-update triggers

### Step 3: Create Storage Bucket

1. Go to **Storage** in Supabase Dashboard
2. Click **"New bucket"**
3. Name: `pdfs`
4. Set to **Public** (or configure RLS policies)
5. This bucket stores uploaded PDF files

### Step 4: Configure Row Level Security (RLS)

Ensure RLS policies are configured:
- Anonymous users can read published assessments
- Authenticated users can create attempts and responses
- Users can only access their own attempts and results
- Service role key bypasses RLS for admin operations (PDF processing, assessment creation)

### Step 5: Verify Setup

Run this query in SQL Editor to verify all tables exist:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
    AND table_name IN (
        'profiles', 'courses', 'assessments',
        'skill_assessment_questions', 'attempts', 'responses', 'results',
        'pdf_documents', 'pdf_embeddings', 'pdf_processing_log'
    )
ORDER BY table_name;
```

Should return exactly **10 rows**.

---

## Running the Application

### Local Development

**Windows (PowerShell):**
```powershell
.\start_backend.ps1
```

**Linux/Mac:**
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Access Points

- **API Root**: http://127.0.0.1:8000/ (returns API information)
- **API Documentation (Swagger)**: http://127.0.0.1:8000/docs
- **ReDoc Documentation**: http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health

---

## API Documentation

### Base URL

- **Development**: `http://localhost:8000`
- **Production**: `https://your-backend-api.vercel.app`

### Authentication

All authenticated endpoints require a Bearer token in the Authorization header:

```http
Authorization: Bearer {access_token}
```

---

## Authentication Endpoints

### POST /auth/login

User login - Returns JWT token for authenticated requests.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "name": "User Name",
    "profile": {...}
  }
}
```

**Status Codes:**
- `200` - Success
- `401` - Invalid credentials
- `503` - Service unavailable

---

### POST /auth/register

User registration - Creates new user account.

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "password123",
  "name": "New User"
}
```

**Response:** Same as login

**Status Codes:**
- `201` - User created
- `400` - Validation error
- `409` - User already exists

---

### GET /auth/me

Get current user information (requires authentication).

**Headers:**
```http
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "name": "User Name",
  "profile": {...}
}
```

**Status Codes:**
- `200` - Success
- `401` - Unauthorized

---

## Dashboard Endpoints

### GET /api/getAssessments

Get all courses with their assessments.

**Headers:** (Optional - works without auth for public assessments)
```http
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "success": true,
  "assessments": [
    {
      "id": "uuid",
      "title": "Python Fundamentals",
      "course_id": "uuid",
      "course_name": "Python",
      "difficulty": "medium",
      "question_count": 10,
      "status": "published"
    }
  ],
  "courses": [
    {
      "id": "uuid",
      "name": "Python",
      "assessment_count": 5
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `503` - Service unavailable

---

### GET /api/getProgress

Get user progress statistics and recent assessments.

**Headers:**
```http
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "success": true,
  "total_assessments": 10,
  "avg_score": 85.5,
  "topic_mastery": {
    "Python": 90.0,
    "DevOps": 80.0
  },
  "recent_assessments": [...]
}
```

**Status Codes:**
- `200` - Success
- `401` - Unauthorized
- `503` - Service unavailable

---

### GET /api/assessments

Get assessments with optional course filter (query parameter).

**Query Parameters:**
- `course_id` (string, optional): Course UUID to filter assessments

**Headers:** (Optional)
```http
Authorization: Bearer {access_token}
```

**Examples:**
- `GET /api/assessments` - Returns all published assessments
- `GET /api/assessments?course_id=abc-123` - Returns assessments for specific course

**Response:**
```json
{
  "success": true,
  "assessments": [
    {
      "id": "uuid",
      "title": "Python Fundamentals",
      "course_id": "uuid",
      "course_name": "Python",
      "difficulty": "medium",
      "question_count": 10,
      "status": "published"
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `503` - Service unavailable

---

### GET /api/assessments/by_course/{course_id}

Get all assessments for a specific course (path parameter version).

**Path Parameters:**
- `course_id` (string, required): Course UUID

**Headers:** (Optional)
```http
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "success": true,
  "course": {
    "id": "uuid",
    "name": "Python"
  },
  "assessments": [
    {
      "id": "uuid",
      "title": "Python Fundamentals",
      "difficulty": "medium",
      "question_count": 10
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `404` - Course not found
- `503` - Service unavailable

**Note:** This endpoint is equivalent to `GET /api/assessments?course_id={course_id}` but uses path parameter instead of query parameter.

---

### GET /api/assessments/{assessment_id}/questions

Get questions for an assessment and create an attempt.

**Path Parameters:**
- `assessment_id` (string, required): Assessment UUID

**Headers:** (Optional - attempt will be created if authenticated)
```http
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "success": true,
  "attempt_id": "uuid",
  "assessment": {
    "id": "uuid",
    "title": "Python Fundamentals"
  },
  "questions": [
    {
      "id": "uuid",
      "question": "What is Python?",
      "options": ["A", "B", "C", "D"],
      "type": "mcq",
      "difficulty": "medium"
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `404` - Assessment not found
- `503` - Service unavailable

---

### POST /api/startAssessment

Start an assessment with dynamic question generation (legacy endpoint).

**Request:**
```json
{
  "skill_name": "Python",
  "num_questions": 10
}
```

**Response:**
```json
{
  "success": true,
  "attempt_id": "uuid",
  "questions": [...]
}
```

**Status Codes:**
- `200` - Success
- `400` - Bad request
- `503` - Service unavailable

---

### POST /api/submitAssessment

Submit assessment answers and get results.

**Request:**
```json
{
  "attempt_id": "uuid",
  "answers": [
    {
      "question_id": "uuid",
      "answer": "A"
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "attempt_id": "uuid",
  "score": 8,
  "total_questions": 10,
  "percentage": 80.0,
  "passed": true,
  "feedback": "Great job! You demonstrated strong understanding..."
}
```

**Status Codes:**
- `200` - Success
- `400` - Bad request
- `404` - Attempt not found
- `503` - Service unavailable

---

### GET /api/attempts/{attempt_id}/result

Get detailed results for a completed assessment attempt.

**Path Parameters:**
- `attempt_id` (string, required): Attempt UUID

**Headers:** (Optional)
```http
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "success": true,
  "attempt": {
    "id": "uuid",
    "score": 8,
    "total_questions": 10,
    "percentage": 80.0,
    "passed": true
  },
  "results": [
    {
      "question_id": "uuid",
      "question": "What is Python?",
      "user_answer": "A",
      "correct_answer": "A",
      "is_correct": true,
      "explanation": "..."
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `404` - Attempt not found
- `503` - Service unavailable

---

## PDF Upload Endpoints

### POST /api/pdf/upload

Upload a PDF file for processing.

**Request:** Multipart form data
- `file` (file, required): PDF file
- `title` (string, optional): Custom title for PDF

**Response:**
```json
{
  "success": true,
  "pdf_id": "uuid",
  "title": "Document Title",
  "status": "processing",
  "message": "PDF uploaded successfully. Processing started."
}
```

**Status Codes:**
- `200` - Success
- `400` - Invalid file format
- `503` - Service unavailable

---

### GET /api/pdf/list

List all uploaded PDFs.

**Response:**
```json
{
  "success": true,
  "pdfs": [
    {
      "id": "uuid",
      "title": "Document Title",
      "status": "completed",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `503` - Service unavailable

---

### GET /api/pdf/{pdf_id}/status

Get processing status of a PDF.

**Path Parameters:**
- `pdf_id` (string, required): PDF UUID

**Response:**
```json
{
  "success": true,
  "pdf_id": "uuid",
  "status": "completed",
  "progress": 100,
  "message": "Processing completed"
}
```

**Status Codes:**
- `200` - Success
- `404` - PDF not found
- `503` - Service unavailable

---

## Folder Upload Endpoints

### POST /api/folder/upload

Upload multiple PDFs as a course folder.

**Request:** Multipart form data
- `folder_name` (string, required): Course name
- `files` (files, required): List of PDF files

**Response:**
```json
{
  "success": true,
  "course_id": "uuid",
  "course_name": "Python",
  "uploaded_files": 5,
  "message": "Folder uploaded successfully"
}
```

**Status Codes:**
- `200` - Success
- `400` - Bad request
- `503` - Service unavailable

---

### POST /api/folder/process-all

Process all uploaded folders (admin endpoint).

**Response:**
```json
{
  "success": true,
  "processed": 3,
  "message": "All folders processed"
}
```

**Status Codes:**
- `200` - Success
- `503` - Service unavailable

---

### GET /api/folder/list

List all uploaded course folders.

**Response:**
```json
{
  "success": true,
  "folders": [
    {
      "course_id": "uuid",
      "course_name": "Python",
      "file_count": 5
    }
  ]
}
```

**Status Codes:**
- `200` - Success
- `503` - Service unavailable

---

## Assessment Generation Endpoints

### POST /api/generateAssessments

Generate assessments from all existing PDF embeddings.

**Note:** This is a long-running operation (may take several minutes).

**Response:**
```json
{
  "success": true,
  "message": "Generated 5 assessments from 5 sources",
  "total_sources": 5,
  "generated": 5,
  "failed": 0,
  "assessments": [...],
  "failed_sources": []
}
```

**Status Codes:**
- `200` - Success
- `500` - Generation failed
- `503` - Service unavailable

---

### GET /api/assessments/stats

Get statistics about generated assessments.

**Response:**
```json
{
  "success": true,
  "total_assessments": 10,
  "total_questions": 100,
  "questions_by_difficulty": {
    "easy": 30,
    "medium": 50,
    "hard": 20
  }
}
```

**Status Codes:**
- `200` - Success
- `503` - Service unavailable

---

### POST /api/embeddings/sync

Sync embeddings: Convert all pdf_embeddings into questions and assessments (alias for generateAssessments).

**Response:** Same as `/api/generateAssessments`

---

## System Endpoints

### GET /health

Health check endpoint with system status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "service": "Skill Capital AI Learning Platform",
  "environment": "local",
  "checks": {
    "supabase": {
      "status": "connected",
                    "test": "Connection successful"
    },
    "openai": "configured",
    "cache": {...}
  },
  "timestamp": 1234567890.0
}
```

**Status Codes:**
- `200` - Healthy
- `503` - Unhealthy

---

### GET /

Root endpoint - API information.

**Response:**
```json
{
  "message": "Skill Assessment Platform API",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health",
  "api_prefix": "/api",
  "auth_prefix": "/auth",
  "note": "This is an API-only backend service. Frontend UI is handled by Edify."
}
```

---

## Usage Examples

### Complete Assessment Flow

#### 1. User Registration

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123",
    "name": "John Doe"
  }'
```

#### 2. User Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "password123"
  }'
```

Save the `access_token` from response.

#### 3. Get All Assessments

```bash
curl -X GET http://localhost:8000/api/getAssessments \
  -H "Authorization: Bearer {access_token}"
```

#### 4. Get Course Assessments

```bash
curl -X GET http://localhost:8000/api/assessments/by_course/{course_id} \
  -H "Authorization: Bearer {access_token}"
```

#### 5. Start Assessment

```bash
curl -X GET http://localhost:8000/api/assessments/{assessment_id}/questions \
  -H "Authorization: Bearer {access_token}"
```

Save the `attempt_id` from response.

#### 6. Submit Assessment

```bash
curl -X POST http://localhost:8000/api/submitAssessment \
  -H "Authorization: Bearer {access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "attempt_id": "{attempt_id}",
    "answers": [
      {
        "question_id": "uuid1",
        "answer": "A"
      },
      {
        "question_id": "uuid2",
        "answer": "B"
      }
    ]
  }'
```

#### 7. Get Results

```bash
curl -X GET http://localhost:8000/api/attempts/{attempt_id}/result \
  -H "Authorization: Bearer {access_token}"
```

---

### PDF Upload Flow

#### 1. Upload PDF

```bash
curl -X POST http://localhost:8000/api/pdf/upload \
  -F "file=@document.pdf" \
  -F "title=My Document"
```

#### 2. Check Processing Status

```bash
curl -X GET http://localhost:8000/api/pdf/{pdf_id}/status
```

#### 3. Generate Assessments

```bash
curl -X POST http://localhost:8000/api/generateAssessments
```

---

## Project Structure

```
Assessments/
├── api/
│   └── index.py                    # Vercel serverless wrapper
├── app/
│   ├── main.py                     # FastAPI entry point (API-only)
│   ├── config.py                   # Configuration & settings
│   ├── models/                     # Database models & schemas
│   │   ├── schemas.py              # Pydantic schemas
│   │   └── assessment_schema.sql   # Database schema
│   ├── routes/                     # API route handlers
│   │   ├── dashboard.py            # Dashboard endpoints
│   │   ├── assessments.py          # Assessment generation
│   │   ├── auth.py                 # Authentication
│   │   ├── pdf_upload.py           # PDF upload endpoints
│   │   └── folder_upload.py        # Folder upload endpoints
│   ├── services/                   # Business logic services
│   │   ├── assessment_generator.py # Assessment generation
│   │   ├── topic_question_service.py # Question generation
│   │   ├── rag_service.py          # RAG search
│   │   ├── embedding_service.py    # Embedding generation
│   │   ├── feedback_service.py     # Feedback generation
│   │   ├── pdf_processor.py        # PDF processing
│   │   ├── folder_processor.py     # Folder processing
│   │   ├── supabase_service.py     # Database service
│   │   └── profile_service.py     # User profiles
│   └── utils/                      # Utility modules
│       ├── logger.py               # Logging
│       ├── error_handler.py       # Error handling
│       ├── auth.py                 # JWT authentication
│       ├── cache.py                # Caching
│       └── rate_limit.py          # Rate limiting
├── scripts/                        # Utility scripts
│   ├── process_uploads.py          # Process uploaded PDFs
│   └── ...
├── requirements.txt                # Python dependencies
├── vercel.json                     # Vercel deployment config
├── .gitignore                      # Git ignore rules
└── README.md                       # This file
```

---

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `SUPABASE_URL` | Yes | Supabase project URL | - |
| `SUPABASE_KEY` | Yes | Supabase anon key | - |
| `SUPABASE_SERVICE_KEY` | Recommended | Service role key (bypasses RLS) | - |
| `OPENAI_API_KEY` | Yes | OpenAI API key | - |
| `OPENAI_MODEL` | No | OpenAI model for questions | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | No | Embedding model | `text-embedding-3-small` |
| `DEBUG` | No | Debug mode | `True` |
| `CORS_ORIGINS` | No | Comma-separated CORS origins | - |

### CORS Configuration

The API is configured to allow requests from Edify domains:

**Production:**
- `https://edify.com`
- `https://www.edify.com`
- `https://app.edify.com`

**Development:**
- `http://localhost:3000`
- `http://localhost:5173`
- `http://localhost:8080`

---

## Deployment

### Deployment Architecture

#### Local Development
- **Runtime**: Uvicorn ASGI server
- **Port**: 8000 (default)
- **Hot Reload**: Enabled in debug mode
- **File System**: Full read/write access
- **Background Jobs**: Run in same process

#### Vercel Serverless Deployment (Recommended)

**Architecture:**
```
Vercel Platform
├── Serverless Functions (Python runtime)
│   ├── api/index.py (entry point)
│   └── app/main.py (FastAPI app)
├── Environment Variables (from Vercel dashboard)
└── Build Configuration (vercel.json)
```

**Constraints:**
- **Timeout**: 10 seconds (Hobby) / 60 seconds (Pro)
- **File System**: Read-only (except `/tmp`)
- **Cold Starts**: First request may be slower
- **Stateless**: No persistent in-memory state between invocations
- **Background Processing**: Must run separately (not in API functions)

**Optimizations:**
- Client caching (Supabase client reused)
- Async operations (non-blocking I/O)
- Minimal cold start (lazy imports)
- Connection pooling (handled by Supabase)

### Vercel Deployment Steps

1. **Connect Repository** to Vercel
2. **Set Environment Variables** in Vercel dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_SERVICE_KEY`
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL` (optional, default: `gpt-4o-mini`)
   - `OPENAI_EMBEDDING_MODEL` (optional, default: `text-embedding-3-small`)
   - `DEBUG=False` (for production)
3. **Deploy** - Vercel will automatically detect `vercel.json` and deploy

**Important Notes:**
- PDF processing should run separately (not in serverless functions) due to timeout constraints
- Use `scripts/process_uploads.py` for background PDF processing
- Health check endpoint (`/health`) can be used for monitoring

### Other Platforms

**AWS Lambda:**
- Use serverless framework or AWS SAM
- Configure environment variables
- Set up API Gateway

**Docker:**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Railway/Heroku:**
- Set environment variables
- Deploy via Git push
- Ensure Python 3.10+ runtime

---

## Edify Integration Guide

### Base API URL

**Production:** `https://your-backend-api.vercel.app`  
**Development:** `http://localhost:8000`

### Authentication Flow

1. **Register User:**
   ```javascript
   const response = await fetch('https://api.example.com/auth/register', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       email: 'user@example.com',
       password: 'password123',
       name: 'User Name'
     })
   });
   const { access_token } = await response.json();
   ```

2. **Login:**
   ```javascript
   const response = await fetch('https://api.example.com/auth/login', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({
       email: 'user@example.com',
       password: 'password123'
     })
   });
   const { access_token } = await response.json();
   localStorage.setItem('access_token', access_token);
   ```

3. **Use Token in Requests:**
   ```javascript
   const token = localStorage.getItem('access_token');
   const response = await fetch('https://api.example.com/api/getAssessments', {
     headers: {
       'Authorization': `Bearer ${token}`,
       'Content-Type': 'application/json'
     }
   });
   ```

### Key Endpoints for Edify

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | POST | User login |
| `/auth/register` | POST | User registration |
| `/auth/me` | GET | Get current user |
| `/api/getAssessments` | GET | List all courses and assessments |
| `/api/getProgress` | GET | Get user progress stats |
| `/api/assessments/by_course/{id}` | GET | Get course assessments |
| `/api/assessments/{id}/questions` | GET | Start assessment |
| `/api/submitAssessment` | POST | Submit answers |
| `/api/attempts/{id}/result` | GET | Get results |

### Error Handling

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

**Common Status Codes:**
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/missing token)
- `404` - Not Found
- `500` - Internal Server Error
- `503` - Service Unavailable

**Example Error Handling:**
```javascript
try {
  const response = await fetch(url, options);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Request failed');
  }
  const data = await response.json();
  return data;
} catch (error) {
  console.error('API Error:', error);
  // Handle error in UI
}
```

---

## Database Schema

### Core Tables (7)

1. **profiles** - User profiles linked to Supabase Auth
   - Columns: `id` (UUID, PK), `email`, `full_name`, `role`, `organization`
   - Indexes: `email`, `role`

2. **courses** - Course definitions
   - Columns: `id` (UUID, PK), `name` (unique), `description`
   - Indexes: `name`

3. **assessments** - Assessment configurations
   - Columns: `id` (UUID, PK), `title`, `skill_domain`, `difficulty`, `question_count`, `status`, `blueprint` (JSONB), `course_id` (FK)
   - Indexes: `course_id`, `status`, `skill_domain`, `created_by`

4. **skill_assessment_questions** - Generated MCQ questions
   - Columns: `id` (UUID, PK), `assessment_id` (FK, nullable), `topic`, `question`, `options` (JSONB), `correct_answer`, `explanation`, `difficulty`, `question_type`
   - Indexes: `assessment_id`, `topic`, `difficulty`, `question_type`
   - **Note**: `assessment_id` may be NULL; questions linked via `blueprint.question_ids` in assessments table

5. **attempts** - User assessment attempts
   - Columns: `id` (UUID, PK), `assessment_id` (FK), `user_id` (FK), `status`, `started_at`, `completed_at`, `total_score`, `max_score`, `percentage_score`
   - Indexes: `assessment_id`, `user_id`, `status`, `created_at`

6. **responses** - Individual question responses
   - Columns: `id` (UUID, PK), `attempt_id` (FK), `question_id` (FK), `answer_text`, `selected_option`, `score`, `max_score`, `feedback`, `status`
   - Indexes: `attempt_id`, `question_id`, `status`

7. **results** - Aggregated assessment results
   - Columns: `id` (UUID, PK), `attempt_id` (FK, unique), `user_id` (FK), `assessment_id` (FK), `total_score`, `max_score`, `percentage_score`, `passed`, `overall_feedback`, `feedback_json` (JSONB)
   - Indexes: `attempt_id`, `user_id`, `assessment_id`, `passed`

### PDF/RAG Tables (3)

8. **pdf_documents** - PDF metadata
   - Columns: `id` (UUID, PK), `title`, `file_url`, `file_size`, `status`, `uploaded_by` (FK)
   - Indexes: `status`, `uploaded_by`, `upload_date`

9. **pdf_embeddings** - PDF content chunks with vector embeddings
   - Columns: `id` (UUID, PK), `pdf_id` (FK), `pdf_title`, `chunk_text`, `embedding` (vector(1536)), `chunk_index`, `page_number`
   - Indexes: `pdf_id`, `pdf_title`, `chunk_index`, `embedding` (ivfflat index for similarity search)

10. **pdf_processing_log** - Processing status tracking
    - Columns: `id` (UUID, PK), `pdf_id` (FK), `status`, `error_message`, `chunks_created`, `questions_generated`, `assessments_created`
    - Indexes: `pdf_id`, `status`

### Key Relationships

```
profiles (1) ──→ (many) attempts
profiles (1) ──→ (many) results
courses (1) ──→ (many) assessments
assessments (1) ──→ (many) skill_assessment_questions (via blueprint.question_ids)
assessments (1) ──→ (many) attempts
attempts (1) ──→ (many) responses
attempts (1) ──→ (1) results
pdf_documents (1) ──→ (many) pdf_embeddings
pdf_documents (1) ──→ (many) pdf_processing_log
```

### Vector Similarity Search

**Function**: `match_pdf_embeddings(query_embedding, match_threshold, match_count, filter_pdf_id)`

**Usage**: Performs cosine similarity search on `pdf_embeddings.embedding` column
- **Index Type**: `ivfflat` with `vector_cosine_ops`
- **Dimension**: 1536 (OpenAI text-embedding-3-small)
- **Default Threshold**: 0.7
- **Default Match Count**: 10

---

## Troubleshooting

### Common Issues

**"Supabase client not initialized"**
- Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_KEY`
- Verify credentials are not placeholders
- Ensure environment variables are set in deployment platform

**"new row violates row-level security policy"**
- Use `SUPABASE_SERVICE_KEY` for admin operations
- Check RLS policies in Supabase Dashboard
- Ensure authenticated requests include valid JWT token

**"OpenAI API key not configured"**
- Add `OPENAI_API_KEY` to `.env` file
- Get key from https://platform.openai.com/api-keys
- Verify key has sufficient credits

**"Table does not exist"**
- Run `app/models/assessment_schema.sql` in Supabase SQL Editor
- Verify all 10 tables are created successfully
- Check table names match exactly

**"Invalid or expired token"**
- Token may have expired (default: 1 hour)
- Re-authenticate via `/auth/login`
- Check Supabase Auth configuration
- Ensure token is included in Authorization header

**"CORS error"**
- Verify frontend domain is in `EDIFY_FRONTEND_ORIGINS` list
- Check CORS configuration in `app/main.py`
- Ensure `allow_credentials` matches origin configuration

**"Assessments not showing"**
- Check assessments have `status = 'published'`
- Verify `course_id` is set
- Ensure user has proper permissions

**"PDF processing stuck"**
- Check `pdf_processing_log` table for errors
- Verify OpenAI API key is valid
- Check Supabase Storage bucket permissions
- Review logs for processing errors

---

## API Response Formats

### Success Response

```json
{
  "success": true,
  "data": {...},
  "message": "Operation completed successfully"
}
```

### Error Response

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Pagination (if applicable)

```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

---

## Security Considerations

### Authentication & Authorization
- **JWT Tokens**: Validated via Supabase Auth on every protected request
- **Token Expiration**: Handled automatically (default: 1 hour)
- **Bearer Token**: Required in `Authorization` header for protected endpoints
- **User Context**: Stored in `request.state.user_id` after validation

### Access Control
- **RLS (Row Level Security)**: Enforced at database level in Supabase
- **Service Key**: Used for admin operations (bypasses RLS)
- **User Isolation**: Users can only access their own attempts and results
- **Public Assessments**: Published assessments readable by anonymous users

### API Security
- **CORS**: Only Edify domains allowed in production (`https://edify.com`, etc.)
- **Rate Limiting**: Sliding window algorithm (100 requests/minute default)
- **Input Validation**: All inputs validated via Pydantic models
- **Error Messages**: Sensitive information not exposed in errors (DEBUG mode only)
- **Request ID**: Every request has unique ID for tracking and debugging

### Data Protection
- **Environment Variables**: Sensitive credentials stored in environment (not in code)
- **HTTPS**: All production traffic encrypted
- **SQL Injection**: Prevented via parameterized queries (Supabase client)
- **XSS**: Not applicable (API-only, no HTML rendering)

---

## Monitoring & Logging

### Logging Strategy

**Structured Logging:**
- **Format**: JSON-formatted logs for production
- **Levels**: DEBUG, INFO, WARNING, ERROR
- **Request ID**: Every request has unique UUID for correlation
- **Context**: Logs include request path, method, user ID, timing

**Log Locations:**
- **Local**: Console output (stdout/stderr)
- **Vercel**: Accessible via Vercel dashboard logs
- **Structured Format**: Ready for log aggregation tools (Datadog, LogRocket, etc.)

### Monitoring Endpoints

**Health Check** (`GET /health`):
- Checks Supabase connection
- Verifies OpenAI API configuration
- Returns cache statistics
- Provides system status

**Response Headers:**
- `X-Request-ID`: Unique request identifier
- `X-Process-Time`: Request processing time in milliseconds

### Error Tracking

**Error Response Format:**
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "details": {},
    "request_id": "uuid"
  }
}
```

**Error Logging:**
- All errors logged with full stack trace (DEBUG mode)
- Request context included (path, method, user ID)
- Exception details captured for debugging

### Performance Metrics

- **Request Timing**: Tracked via middleware (X-Process-Time header)
- **Database Queries**: Logged at DEBUG level
- **API Calls**: OpenAI API calls logged with timing
- **Cache Hits/Misses**: Tracked in cache statistics

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License.

---

## Acknowledgments

- **FastAPI** - Modern web framework
- **Supabase** - Backend-as-a-Service
- **OpenAI** - AI question generation
- **PostgreSQL** - Robust database

---

## Support

For API questions or issues:
- Check interactive API docs at `/docs`
- Review health check at `/health`
- Contact backend team

---

**Made with FastAPI, Supabase, and OpenAI**

**API-Only Backend Service - Ready for Edify Integration**
