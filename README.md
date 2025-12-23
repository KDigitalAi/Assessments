# Skill Assessment Builder - AI-Powered Learning Platform

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-2.22+-orange.svg)](https://supabase.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-purple.svg)](https://openai.com/)

> Production-ready platform for creating, delivering, and evaluating skill assessments using OpenAI GPT-4 and vector embeddings.

---

## Overview

**Skill Assessment Builder** is a **PDF-based AI Assessment Platform** that automates the complete assessment lifecycle. This is a **self-contained system** using a **separate Supabase database** dedicated exclusively to assessments.

### Complete Pipeline

**PDF → Embeddings → Questions → Assessments → Courses → Attempts → Results**

The system:
- Uploads PDF documents via web interface
- Extracts text and generates vector embeddings
- Uses RAG (Retrieval-Augmented Generation) to generate contextual MCQ questions
- Creates assessments organized by courses
- Delivers assessments through a web interface
- Automatically scores responses and provides AI-generated feedback

### Key Features

- 📄 **PDF-Only System**: Upload and process PDF documents exclusively (no video, no chatbot)
- 🔄 **End-to-End Pipeline**: Complete workflow from PDF upload to assessment results
- 🤖 **AI-Powered Question Generation**: Automatically generates MCQ questions from PDF content using OpenAI GPT-4
- 🔍 **RAG-Powered**: Uses vector embeddings for context-aware question generation
- 📚 **Course-Based Organization**: Organizes assessments by courses with automatic course detection
- 🎯 **Automated Scoring**: Instant scoring for MCQ questions
- 💬 **Personalized Feedback**: AI-generated feedback based on performance
- 🔐 **JWT Authentication**: Secure authentication via Supabase Auth
- 📊 **Progress Tracking**: Monitor user progress across courses and assessments
- 🗄️ **Self-Contained Database**: Separate Supabase project dedicated to assessments

---

## System Architecture

The system consists of:

1. **FastAPI Backend**: RESTful API server handling all HTTP requests and serving static frontend files
2. **Supabase Database**: PostgreSQL with pgvector extension for storing assessments, questions, attempts, and embeddings
3. **Supabase Auth**: JWT-based authentication and user management
4. **OpenAI API**: Direct integration for question generation, embeddings, and feedback
5. **Frontend Application**: HTML/JavaScript client served as static files by FastAPI
6. **Service Layer**: Python services for assessment generation, RAG search, feedback generation, and database operations

### Complete Data Flow

**Phase 1: PDF Upload & Processing**
1. User uploads PDF via web interface
2. File stored in Supabase Storage (bucket: `pdfs`)
3. PDF metadata recorded in `pdf_documents` table
4. Processing status tracked in `pdf_processing_log`

**Phase 2: Text Extraction & Embedding**
1. Extract text page-by-page from PDF
2. Chunk text into 500-1000 character segments
3. Generate embeddings using OpenAI `text-embedding-3-small`
4. Store chunks and embeddings in `pdf_embeddings` table

**Phase 3: Question Generation (RAG)**
1. Perform vector similarity search on `pdf_embeddings`
2. Retrieve relevant context chunks
3. Generate MCQ questions using OpenAI GPT-4
4. Store questions in `skill_assessment_questions` table

**Phase 4: Assessment Creation**
1. Group questions by topic/skill domain
2. Create assessment record in `assessments` table
3. Link to course via `course_id` in `courses` table

**Phase 5: User Assessment**
1. User authenticates via Supabase Auth (JWT token)
2. Views courses and assessments via frontend
3. Starts assessment → creates `attempts` record
4. Answers questions → stored in `responses` table
5. System scores answers automatically
6. Generate AI feedback → stored in `results` table

For detailed architecture documentation, see [ARCHITECTURE.tex](ARCHITECTURE.tex).

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

### Frontend
- **HTML5/CSS3**: Structure and styling
- **JavaScript (ES6+)**: Client-side logic
- **Fetch API**: HTTP communication

---

## Installation

### Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **Supabase Account** with a **NEW project** (separate from chatbot/RAG database)
- **OpenAI API Key** (for question generation and embeddings)
- **Git** (for cloning repository)
- **PyPDF2** (for PDF text extraction): `pip install PyPDF2`

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

### API Endpoints

**PDF Upload & Processing:**
- `POST /api/pdf/upload` - Upload PDF file
- `GET /api/pdf/list` - List all uploaded PDFs
- `GET /api/pdf/{pdf_id}/status` - Get PDF processing status

**Assessment Generation:**
- `POST /api/generateAssessments` - Generate assessments from PDFs
- `POST /api/embeddings/sync` - Sync embeddings and generate assessments

**Assessment Taking:**
- `GET /api/getAssessments` - Get all assessments
- `POST /api/startAssessment` - Start an assessment attempt
- `POST /api/submitResponse` - Submit answer
- `POST /api/submitAssessment` - Complete assessment

### Access Points

- **Frontend Dashboard**: http://127.0.0.1:8000/
- **API Documentation (Swagger)**: http://127.0.0.1:8000/docs
- **Health Check**: http://127.0.0.1:8000/health

---

## Usage

### Generate Assessments from PDFs

**Using the API:**
```bash
curl -X POST http://127.0.0.1:8000/api/generateAssessments
```

**Using the Script:**
```bash
python scripts/generate_all_assessments.py
```

This process:
1. Reads all PDF embeddings from the database
2. Generates 10 MCQ questions per source using OpenAI
3. Creates assessment records linked to courses
4. Stores questions in the database

### User Registration and Login

**Register:**
```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123", "name": "User Name"}'
```

**Login:**
```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

Returns JWT token to use in subsequent requests.

### Take an Assessment

1. Navigate to http://127.0.0.1:8000/
2. Register/Login if required
3. Select a course
4. Click "START ASSESSMENT" on an assessment
5. Answer questions
6. Submit to see results and feedback

---

## API Endpoints

### Authentication

- `POST /auth/login` - User login (returns JWT token)
- `POST /auth/register` - User registration
- `GET /auth/me` - Get current user info (requires authentication)

### Dashboard

- `GET /api/getAssessments` - Get all courses with assessments
- `GET /api/assessments/by_course/{course_id}` - Get assessments for a course
- `GET /api/assessments/{assessment_id}/questions` - Get questions and create attempt
- `POST /api/submitAssessment` - Submit answers and get results
- `GET /api/attempts/{attempt_id}/result` - Get detailed results
- `GET /api/getProgress` - Get user progress statistics

### Assessment Generation

- `POST /api/generateAssessments` - Generate assessments from embeddings
- `GET /api/assessments/stats` - Get assessment statistics
- `POST /api/embeddings/sync` - Sync embeddings (alias for generateAssessments)

### System

- `GET /health` - Health check with system status
- `GET /docs` - Interactive API documentation (Swagger UI)

For interactive API documentation, visit http://127.0.0.1:8000/docs

---

## Project Structure

```
Assessments/
├── app/                          # Backend application
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # Configuration & settings
│   ├── models/                   # Database models & schemas
│   │   ├── schemas.py            # Pydantic schemas
│   │   └── assessment_schema.sql    # Database schema (PDF-only)
│   ├── routes/                   # API route handlers
│   │   ├── dashboard.py          # Main dashboard endpoints
│   │   ├── assessments.py        # Assessment generation endpoints
│   │   └── auth.py               # Authentication endpoints
│   ├── services/                 # Business logic services
│   │   ├── assessment_generator.py
│   │   ├── topic_question_service.py
│   │   ├── rag_service.py
│   │   ├── embedding_service.py
│   │   ├── feedback_service.py
│   │   ├── supabase_service.py
│   │   └── profile_service.py
│   └── utils/                    # Utility modules
│       ├── logger.py
│       ├── error_handler.py
│       ├── auth.py               # JWT authentication
│       ├── cache.py
│       └── rate_limit.py
├── frontend/                      # Frontend web application
│   ├── index.html                # Main dashboard
│   ├── assessments.html          # Course assessments
│   ├── assessment.html            # Assessment taking page
│   ├── results.html               # Results display
│   ├── app.js                     # Main frontend logic
│   ├── assessment.js              # Assessment logic
│   └── styles.css                 # Styles
├── scripts/                        # Utility scripts
│   └── generate_all_assessments.py
├── requirements.txt               # Python dependencies
├── start_backend.ps1              # Windows startup script
└── README.md                       # This file
```

---

## Database Schema

### Core Tables

- **profiles**: User profiles linked to Supabase Auth users
- **courses**: Course definitions (Python, DevOps, etc.)
- **assessments**: Assessment configurations with blueprints (JSON containing question IDs)
- **skill_assessment_questions**: Generated MCQ questions with options, correct answers, explanations
- **attempts**: User assessment attempts with status, scores, timestamps
- **responses**: Individual question responses with scores
- **results**: Aggregated assessment results with AI-generated feedback
- **pdf_embeddings**: PDF content chunks with vector embeddings (populated externally)

---

## Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `SUPABASE_URL` | Yes | Supabase project URL | - |
| `SUPABASE_KEY` | Yes | Supabase anon key | - |
| `SUPABASE_SERVICE_KEY` | Recommended | Service role key (bypasses RLS) | - |
| `OPENAI_API_KEY` | Yes | OpenAI API key | - |
| `OPENAI_MODEL` | No | OpenAI model | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | No | Embedding model | `text-embedding-3-small` |
| `DEBUG` | No | Debug mode | `True` |
| `CORS_ORIGINS` | No | Comma-separated CORS origins | - |

---

## Deployment

### Production Deployment

1. **Set Environment Variables** in your hosting platform:
   - `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`
   - `OPENAI_API_KEY`
   - `DEBUG=False`
   - `CORS_ORIGINS` (your production domain)

2. **Deploy FastAPI Application**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

3. **Frontend**: Served automatically by FastAPI (no separate deployment needed)

4. **Database**: Use Supabase production instance

### Deployment Platforms

- **Vercel**: Serverless deployment (recommended)
- **AWS**: EC2 or Lambda
- **Heroku**: Platform-as-a-Service
- **Railway**: Simple deployment

### Production Considerations

- Set `DEBUG=False` in production
- Configure CORS origins for production domain
- Use `SUPABASE_SERVICE_KEY` for admin operations
- Enable RLS policies in Supabase
- Configure rate limiting for production load
- Set up monitoring and logging

---

## Troubleshooting

### Common Issues

**"Supabase client not initialized"**
- Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_KEY`
- Verify credentials are not placeholders

**"new row violates row-level security policy"**
- Use `SUPABASE_SERVICE_KEY` for admin operations
- Check RLS policies in Supabase Dashboard

**"OpenAI API key not configured"**
- Add `OPENAI_API_KEY` to `.env` file
- Get key from https://platform.openai.com/api-keys

**"Table does not exist"**
- Run `app/models/assessment_schema.sql` in Supabase SQL Editor
- Verify all 10 tables are created successfully

**"Invalid or expired token"**
- Token may have expired (default: 1 hour)
- Re-authenticate via `/auth/login`
- Check Supabase Auth configuration

**"Assessments not showing"**
- Check assessments have `status = 'published'`
- Verify `course_id` is set
- Clear browser cache

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

**Made with ❤️ using FastAPI, Supabase, and OpenAI**
