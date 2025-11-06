# Skill Assessment Builder with RAG System

An AI-powered platform for creating skill assessments and generating questions from Vimeo videos and PDF documents using **RAG (Retrieval-Augmented Generation)** with **FastAPI**, **Supabase**, and **OpenAI**.

## 🚀 Features

### Core Assessment Features
- **AI-Powered Question Generation**: Automatically generate MCQ and descriptive questions using LangChain and OpenAI
- **Automated Scoring**: Deterministic scoring for MCQ questions and LLM-based rubric scoring for descriptive answers
- **PDF Report Generation**: Generate comprehensive PDF reports with scores, feedback, and analytics
- **Supabase Integration**: Full integration with Supabase for authentication, database, and file storage

### RAG System Features (NEW)
- **Vimeo Video Processing**: Extract transcripts from Vimeo videos and generate embeddings
- **PDF Document Processing**: Upload PDFs, extract text, chunk, and generate embeddings
- **Unified Search**: Search across both videos and PDFs using vector similarity
- **Context-Aware Question Generation**: Generate questions from retrieved video/PDF content
- **Interactive Chat**: Ask questions about your videos and PDFs with AI-powered responses

## 📋 Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **Supabase Account** with a project
- **OpenAI API Key**
- **Vimeo API Token** (optional, only for private videos)

## 🛠️ Installation

### 1. Clone and Setup

   ```bash
   git clone <repository-url>
   cd Skill_Assessment
   ```

### 2. Backend Setup

   ```bash
# Create virtual environment
   python -m venv venv

# Activate virtual environment
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Linux/Mac:
source venv/bin/activate

# Install dependencies
   pip install -r requirements.txt
   ```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

   ```bash
# Copy from example
   cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Supabase (from https://app.supabase.com/project/YOUR_PROJECT/settings/api)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-key

# OpenAI (from https://platform.openai.com/api-keys)
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Optional: Vimeo (only for private videos)
VIMEO_ACCESS_TOKEN=your-vimeo-access-token

# Application Settings
DEBUG=True
```

### 4. Database Setup

1. **Run SQL Schema in Supabase**:
   - Go to Supabase Dashboard → SQL Editor
   - Run `app/models/unified_schema.sql` to create all tables and functions

2. **Enable Extensions**:
   - The schema automatically enables `uuid-ossp` and `vector` extensions

3. **Create Storage Bucket**:
   - Go to Supabase Dashboard → Storage
   - Create a bucket named `documents` for PDF storage

## 🏃 Running the Application

### Quick Start

**Windows PowerShell:**
```powershell
# Start Backend
.\start_backend.ps1
```

**Linux/Mac:**
```bash
# Start Backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Access Points

- **Frontend**: Open `frontend/index.html` in your browser (or serve via local server)
- **Backend API**: http://127.0.0.1:8000
- **API Documentation**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health

### Frontend Setup (Optional)

To serve the frontend with a local server:

```bash
# Python 3
cd frontend
python -m http.server 8080

# Or Node.js (if installed)
npx http-server frontend -p 8080
```

Then visit: http://localhost:8080

## 🧪 Testing Connection

### Backend Test
```bash
python tests/test_connection.py
```

## 📁 Project Structure

```
Skill_Assessment/
│
├── app/                          # Backend application
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # Configuration
│   │
│   ├── models/                   # Database models
│   │   ├── database.py           # Pydantic models
│   │   ├── schemas.py            # Request/Response schemas
│   │   └── unified_schema.sql    # Database schema (run this in Supabase)
│   │
│   ├── routes/                   # API routes
│   │   ├── auth.py               # Authentication
│   │   ├── assessments.py        # Assessment management
│   │   ├── questions.py          # Question generation
│   │   ├── attempts.py           # Attempt management
│   │   ├── reports.py            # PDF reports
│   │   ├── analytics.py          # Analytics
│   │   └── rag.py                # RAG endpoints (NEW)
│   │
│   ├── services/                 # Business logic
│   │   ├── supabase_service.py   # Supabase integration
│   │   ├── langchain_service.py  # LangChain/OpenAI
│   │   ├── scoring_service.py    # Scoring logic
│   │   ├── pdf_service.py        # PDF generation
│   │   ├── video_service.py      # Vimeo video processing (NEW)
│   │   ├── document_service.py   # PDF processing (NEW)
│   │   ├── embedding_service.py  # Embedding generation (NEW)
│   │   └── rag_service.py        # RAG pipeline (NEW)
│   │
│   ├── agents/                   # AI Agents
│   │   ├── question_agent.py     # Question generation agent
│   │   ├── scoring_agent.py      # Scoring agent
│   │   ├── analytics_agent.py    # Analytics agent
│   │   └── remediation_agent.py # Remediation agent
│   │
│   ├── tools/                    # LangChain tools
│   │   ├── db_tools.py           # Database tools
│   │   ├── feedback_tools.py     # Feedback tools
│   │   ├── pdf_tools.py           # PDF tools
│   │   └── similarity_tools.py   # Similarity search tools
│   │
│   └── utils/                    # Utilities
│       ├── auth.py               # Authentication
│       ├── logger.py              # Logging
│       ├── error_handler.py      # Error handling
│       ├── cache.py               # Caching
│       └── rate_limit.py          # Rate limiting
│
├── tests/                        # Tests
│   └── test_connection.py        # Connection tests
│
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
├── requirements.txt              # Python dependencies
├── start_backend.ps1             # Backend startup script (Windows)
└── README.md                     # This file
```

## 🔑 API Endpoints

### Dashboard APIs (New - Unified)
- `GET /api/getAssessments` - Get available assessments with user progress
- `POST /api/startAssessment` - Start assessment and generate questions from existing embeddings
- `POST /api/submitAssessment` - Submit answers and get score
- `GET /api/getProgress` - Get user progress, stats, and recent assessments

### Authentication
- `POST /api/v1/auth/login` - Login user
- `POST /api/v1/auth/register` - Register new user

### Assessments (Legacy - for compatibility)
- `POST /api/v1/assessments/create` - Create assessment
- `GET /api/v1/assessments/{id}` - Get assessment
- `GET /api/v1/assessments/` - List assessments

### Questions
- `POST /api/v1/questions/generate` - Generate questions
- `GET /api/v1/questions/assessment/{id}` - Get assessment questions

### RAG System (NEW)
- `POST /api/v1/rag/videos/process` - Process Vimeo video
- `POST /api/v1/rag/documents/upload` - Upload PDF document
- `GET /api/v1/rag/documents` - List user's PDF documents
- `DELETE /api/v1/rag/documents/{id}` - Delete PDF document
- `POST /api/v1/rag/questions/generate` - Generate questions from content
- `POST /api/v1/rag/chat` - Chat with documents/videos
- `GET /api/v1/rag/chat/history` - Get chat history

### Attempts & Reports
- `POST /api/v1/attempts/start` - Start assessment attempt
- `POST /api/v1/attempts/submit-answer` - Submit answer
- `POST /api/v1/reports/generate` - Generate PDF report

## 📖 Usage Guide

### 1. Process a Vimeo Video

Use the API endpoint `POST /api/v1/rag/videos/process`:
- Send Vimeo video URL (e.g., `https://vimeo.com/123456789`)
- Optionally provide Vimeo API access token (for private videos)
- Wait for processing to complete

### 2. Upload a PDF Document

Use the API endpoint `POST /api/v1/rag/documents/upload`:
- Upload PDF file via multipart/form-data
- Wait for processing to complete

### 3. Generate Questions

Use the API endpoint `POST /api/v1/rag/questions/generate`:
- Select source type (Video, PDF, or All)
- Questions will be returned with options and explanations

### 4. Chat with Content

Use the API endpoint `POST /api/v1/rag/chat`:
- Select source type (All Sources, Videos Only, or PDFs Only)
- Send your question
- Get AI-generated answers based on your content

## 🗄️ Database Schema

The unified schema includes:

### Existing Tables
- `profiles` - User profiles
- `assessments` - Assessment configurations
- `questions` - Generated questions
- `attempts` - Assessment attempts
- `responses` - User responses
- `results` - Aggregated results
- `embeddings` - Question embeddings (for deduplication)

### New RAG Tables
- `video_embeddings` - Video transcript chunks with embeddings
- `pdf_embeddings` - PDF document chunks with embeddings
- `pdf_documents` - PDF document metadata
- `user_queries` - User query history
- `chat_history` - Chat conversation history

### Supabase Functions
- `match_video_embeddings()` - Search video chunks
- `match_documents()` - Search PDF chunks
- `match_unified_embeddings()` - Unified search (main RAG function)
- `get_pdf_documents()` - List user PDFs
- `delete_pdf_document()` - Soft delete PDF

## 🔐 Authentication

The API uses Supabase JWT authentication. Include the token in requests:

```javascript
Authorization: Bearer <your-supabase-jwt-token>
```

## 🐛 Troubleshooting

### Backend Issues

**"Supabase client not initialized"**
- Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_KEY`
- Ensure credentials are not placeholders

**"OpenAI API key not configured"**
- Add `OPENAI_API_KEY` to `.env` file
- Get API key from https://platform.openai.com/api-keys

**"Module not found" errors**
- Run `pip install -r requirements.txt`
- Activate virtual environment

### Database Issues

**"Table does not exist"**
- Run `app/models/unified_schema.sql` in Supabase SQL Editor
- Check Supabase connection in `.env`

**"Function does not exist"**
- Ensure SQL schema was run completely
- Check that `vector` extension is enabled

## 🧪 Testing

### Run Connection Tests

```bash
# Test backend connection
python tests/test_connection.py
```

## 📝 Environment Variables

See `.env.example` for all required variables. Key variables:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Supabase anon key
- `OPENAI_API_KEY` - OpenAI API key
- `DEBUG` - Set to `True` for development

## 🚀 Deployment

### Backend Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📚 Documentation

- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc
- **RAG Setup Guide**: See `RAG_SETUP.md` for detailed RAG system setup

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

[Your License Here]

---

**Made with ❤️ using FastAPI, Supabase, and OpenAI**
