# Skill Assessment Platform - AI-Powered Learning & Assessment System

A comprehensive AI-powered platform for creating, delivering, and evaluating skill assessments. Built with **FastAPI**, **Supabase**, and **OpenAI**, this system automatically generates assessments from PDF documents, provides course-based organization, and offers intelligent feedback.

---

## 🎯 Project Overview

This platform enables:
- **Automated Assessment Generation**: Generate 20 high-quality MCQ questions per PDF document using AI
- **Course-Based Organization**: Organize assessments by courses (Python, DevOps, etc.)
- **Intelligent Question Generation**: Uses GPT-4 to create theory, code-tracing, and application questions
- **Real-Time Assessment Delivery**: Web-based interface for taking assessments
- **Automated Scoring & Feedback**: Instant scoring with AI-generated personalized feedback
- **Progress Tracking**: Monitor user progress across courses and assessments

---

## 🚀 Key Features

### Core Assessment Features
- ✅ **AI-Powered Question Generation**: Automatically generates 20 MCQ questions per PDF using OpenAI GPT-4
- ✅ **Course Management**: Organize assessments by courses (Python, DevOps, etc.)
- ✅ **Automatic Course Detection**: Intelligently detects course type from PDF titles and content
- ✅ **Duplicate Prevention**: Strict checks to prevent duplicate assessments and questions
- ✅ **Automated Scoring**: Instant scoring for MCQ questions
- ✅ **Personalized Feedback**: AI-generated feedback based on user performance
- ✅ **Progress Tracking**: Track user progress across courses and assessments

### Technical Features
- ✅ **FastAPI Backend**: High-performance async API
- ✅ **Supabase Integration**: PostgreSQL database with Row Level Security (RLS)
- ✅ **Vector Embeddings**: Store and search PDF content using embeddings
- ✅ **Service Role Authentication**: Secure admin operations bypassing RLS
- ✅ **Caching System**: In-memory caching for improved performance
- ✅ **Rate Limiting**: API rate limiting for security
- ✅ **Error Handling**: Comprehensive error handling and logging
- ✅ **CORS Support**: Configured for frontend-backend communication

---

## 📋 Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **Supabase Account** with a project
- **OpenAI API Key** (for question generation)
- **Node.js** (optional, for serving frontend)

---

## 🛠️ Installation & Setup

### 1. Clone Repository

   ```bash
   git clone <repository-url>
cd Assessments
   ```

### 2. Create Virtual Environment

   ```bash
# Windows PowerShell
   python -m venv venv
venv\Scripts\Activate.ps1

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
   pip install -r requirements.txt
   ```

### 4. Configure Environment Variables

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
```

**Where to get credentials:**
- **Supabase**: https://app.supabase.com/project/YOUR_PROJECT/settings/api
- **OpenAI**: https://platform.openai.com/api-keys

### 5. Database Setup

1. **Run SQL Schema in Supabase**:
   - Go to Supabase Dashboard → SQL Editor
   - Run `app/models/unified_schema.sql` to create all tables, indexes, and functions
   - The schema automatically enables `uuid-ossp` and `vector` extensions

2. **Verify Tables Created**:
   - `profiles` - User profiles
   - `courses` - Course definitions
   - `assessments` - Assessment configurations
   - `skill_assessment_questions` - Generated questions
   - `attempts` - User assessment attempts
   - `responses` - User answers
   - `results` - Assessment results
   - `pdf_embeddings` - PDF content chunks with embeddings

---

## 🏃 Running the Application

### Backend Server

**Windows PowerShell:**
```powershell
.\start_backend.ps1
```

**Linux/Mac:**
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Manual Start:**
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

The frontend is served automatically by the FastAPI backend at:
- **Main Dashboard**: http://127.0.0.1:8000/
- **Assessments Page**: http://127.0.0.1:8000/static/assessments.html
- **Assessment Page**: http://127.0.0.1:8000/static/assessment.html
- **Results Page**: http://127.0.0.1:8000/static/results.html

### Access Points

- **Frontend Dashboard**: http://127.0.0.1:8000/
- **Backend API**: http://127.0.0.1:8000/api
- **API Documentation (Swagger)**: http://127.0.0.1:8000/docs
- **ReDoc Documentation**: http://127.0.0.1:8000/redoc
- **Health Check**: http://127.0.0.1:8000/health

---

## 📁 Project Structure

```
Assessments/
│
├── app/                          # Backend application
│   ├── __init__.py
│   ├── config.py                 # Application configuration & settings
│   ├── main.py                   # FastAPI entry point & app initialization
│   │
│   ├── models/                   # Database models & schemas
│   │   ├── __init__.py
│   │   ├── database.py           # Pydantic database models
│   │   ├── schemas.py            # Request/Response schemas
│   │   └── unified_schema.sql    # Complete database schema (run in Supabase)
│   │
│   ├── routes/                   # API route handlers
│   │   ├── __init__.py
│   │   ├── dashboard.py          # Main dashboard API endpoints
│   │   ├── assessments.py        # Assessment generation endpoints
│   │   └── auth.py               # Authentication endpoints
│   │
│   ├── services/                 # Business logic services
│   │   ├── __init__.py
│   │   ├── supabase_service.py   # Supabase client & database operations
│   │   ├── assessment_generator.py # Assessment generation service
│   │   ├── embedding_service.py  # Vector embedding generation
│   │   ├── feedback_service.py    # AI feedback generation
│   │   ├── profile_service.py     # User profile management
│   │   ├── rag_service.py         # RAG (Retrieval-Augmented Generation) service
│   │   └── topic_question_service.py # Topic-based question generation
│   │
│   └── utils/                     # Utility modules
│       ├── __init__.py
│       ├── auth.py               # Authentication utilities
│       ├── cache.py              # In-memory caching system
│       ├── constants.py          # Application constants
│       ├── error_handler.py      # Global error handling
│       ├── helpers.py            # Helper functions
│       ├── logger.py             # Logging configuration
│       ├── rate_limit.py         # API rate limiting
│       └── validation.py        # System validation utilities
│
├── frontend/                      # Frontend web application
│   ├── index.html                # Main dashboard page
│   ├── assessments.html          # Course assessments listing page
│   ├── assessment.html           # Assessment taking page
│   ├── results.html              # Results display page
│   ├── app.js                    # Main frontend JavaScript
│   ├── assessment.js             # Assessment taking logic
│   ├── styles.css                # Application styles
│   └── assets/
│       └── logo.png              # Application logo
│
├── scripts/                       # Utility scripts
│   └── generate_all_assessments.py # Script to generate assessments from PDFs
│
├── venv/                          # Python virtual environment (gitignored)
│
├── .env                           # Environment variables (gitignored)
├── .gitignore                     # Git ignore rules
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Python dependencies
├── start_backend.ps1              # Windows startup script
└── README.md                      # This file
```

---

## 🔑 API Endpoints

### Dashboard APIs (Main Endpoints)

#### Get Assessments
```http
GET /api/getAssessments
```
Returns all courses with their assessments, test counts, and progress.

**Response:**
```json
{
  "success": true,
  "courses": [
    {
      "id": "uuid",
      "name": "Python",
      "test_count": 20,
      "progress": 100,
      "assessments": [...]
    }
  ],
  "assessments": [...] // For backward compatibility
}
```

#### Get Assessments by Course
```http
GET /api/assessments/by_course/{course_id}
```
Returns all assessments for a specific course.

#### Get Assessment Questions
```http
GET /api/assessments/{assessment_id}/questions
```
Returns questions for an assessment and creates an attempt record.

#### Start Assessment
```http
POST /api/startAssessment
Content-Type: application/json

{
  "skill_name": "Python",
  "num_questions": 10
}
```
Starts a new assessment and generates/fetches questions.

#### Submit Assessment
```http
POST /api/submitAssessment
Content-Type: application/json

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
Submits answers and returns score with feedback.

#### Get Attempt Result
```http
GET /api/attempts/{attempt_id}/result
```
Returns detailed results for a completed attempt.

#### Get User Progress
```http
GET /api/getProgress
```
Returns user progress, statistics, and recent assessments.

### Assessment Generation APIs

#### Generate Assessments from PDFs
```http
POST /api/generateAssessments
```
Triggers assessment generation from all PDF embeddings in the database.

#### Get Assessment Statistics
```http
GET /api/assessments/stats
```
Returns statistics about assessments in the database.

#### Sync Embeddings
```http
POST /api/embeddings/sync
```
Syncs embeddings from external sources.

### Authentication APIs

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

#### Register
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password",
  "name": "User Name"
}
```

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer <token>
```

---

## 📖 Usage Guide

### 1. Generate Assessments from PDFs

**Using the Script:**
```bash
python scripts/generate_all_assessments.py
```

This script:
1. Fetches all PDFs from `pdf_embeddings` table
2. For each PDF:
   - Detects course (Python/DevOps) from PDF title
   - Creates or gets course record
   - Generates 20 MCQ questions using GPT-4
   - Creates assessment record with `course_id`
   - Stores questions in `skill_assessment_questions` table
3. Prevents duplicates (checks existing assessments by `pdf_id`)

**Using the API:**
```bash
curl -X POST http://127.0.0.1:8000/api/generateAssessments
```

### 2. Course Organization

Assessments are automatically organized by courses:
- **Python**: Detected from keywords like "python", "datatypes", "loops", "functions"
- **DevOps**: Detected from keywords like "devops", "docker", "kubernetes", "linux"

The system:
- Automatically detects course from PDF title
- Creates course if it doesn't exist
- Links assessments to courses via `course_id`
- Updates `skill_domain` to match course name

### 3. Taking Assessments

1. **View Courses**: Navigate to http://127.0.0.1:8000/
2. **Select Course**: Click "VIEW ASSESSMENTS" on a course card
3. **Start Assessment**: Click "START ASSESSMENT" on an assessment
4. **Answer Questions**: Select answers and submit
5. **View Results**: See score, feedback, and detailed results

### 4. Frontend Workflow

1. **Dashboard** (`index.html`):
   - Displays all courses with test counts
   - Shows progress for each course
   - Links to course assessments

2. **Assessments Page** (`assessments.html`):
   - Lists all assessments for selected course
   - Filtered by `course_id`
   - Shows difficulty, question count, duration

3. **Assessment Page** (`assessment.html`):
   - Displays questions one by one
   - Tracks time remaining
   - Allows navigation between questions
   - Submits answers on completion

4. **Results Page** (`results.html`):
   - Shows total score and percentage
   - Displays correct/incorrect answers
   - Shows AI-generated feedback
   - Provides detailed breakdown

---

## 🗄️ Database Schema

### Core Tables

#### `profiles`
User profiles linked to Supabase Auth.
- `id` (UUID, PK) - References `auth.users`
- `email` (TEXT, UNIQUE)
- `full_name` (TEXT)
- `role` (TEXT) - 'user', 'admin', 'student'

#### `courses`
Course definitions for grouping assessments.
- `id` (UUID, PK)
- `name` (TEXT, UNIQUE) - e.g., "Python", "DevOps"
- `description` (TEXT)
- `created_at`, `updated_at` (TIMESTAMP)

#### `assessments`
Assessment configurations.
- `id` (UUID, PK)
- `title` (TEXT)
- `skill_domain` (TEXT) - Course name
- `course_id` (UUID, FK) - References `courses.id`
- `difficulty` (TEXT) - 'easy', 'medium', 'hard'
- `question_count` (INTEGER)
- `duration_minutes` (INTEGER)
- `status` (TEXT) - 'draft', 'published', 'archived'
- `blueprint` (TEXT, JSON) - Stores `pdf_id` and metadata
- `created_at`, `updated_at` (TIMESTAMP)

#### `skill_assessment_questions`
Generated questions for assessments.
- `id` (UUID, PK)
- `assessment_id` (UUID, FK) - References `assessments.id`
- `topic` (TEXT)
- `question` (TEXT)
- `options` (JSONB) - Array of 4 options
- `correct_answer` (TEXT)
- `explanation` (TEXT)
- `difficulty` (TEXT) - 'easy', 'medium', 'hard'
- `source_type` (TEXT) - 'pdf'
- `source_id` (TEXT) - PDF ID
- `created_at` (TIMESTAMP)

#### `attempts`
User assessment attempts.
- `id` (UUID, PK)
- `assessment_id` (UUID, FK)
- `user_id` (UUID, FK) - References `profiles.id`
- `status` (TEXT) - 'in_progress', 'completed'
- `started_at`, `completed_at` (TIMESTAMP)
- `total_score`, `max_score` (NUMERIC)
- `percentage_score` (NUMERIC)

#### `responses`
User answers to questions.
- `id` (UUID, PK)
- `attempt_id` (UUID, FK)
- `question_id` (UUID, FK)
- `answer` (TEXT)
- `is_correct` (BOOLEAN)
- `answered_at` (TIMESTAMP)

#### `results`
Aggregated assessment results.
- `id` (UUID, PK)
- `attempt_id` (UUID, FK)
- `assessment_id` (UUID, FK)
- `user_id` (UUID, FK)
- `total_score`, `max_score` (NUMERIC)
- `percentage_score` (NUMERIC)
- `feedback` (TEXT) - AI-generated feedback
- `completed_at` (TIMESTAMP)

#### `pdf_embeddings`
PDF content chunks with vector embeddings.
- `id` (UUID, PK)
- `pdf_id` (TEXT)
- `pdf_title` (TEXT)
- `chunk_text` (TEXT)
- `chunk_index` (INTEGER)
- `embedding` (VECTOR) - 1536 dimensions
- `created_at` (TIMESTAMP)

### Indexes

- `idx_assessments_course_id` - Fast course filtering
- `idx_assessments_status` - Fast status filtering
- `idx_skill_assessment_questions_assessment_id` - Fast question lookup
- `idx_attempts_user_id` - Fast user attempt lookup
- `idx_attempts_assessment_id` - Fast assessment attempt lookup

---

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|------------|---------|
| `SUPABASE_URL` | Yes | Supabase project URL | - |
| `SUPABASE_KEY` | Yes | Supabase anon key | - |
| `SUPABASE_SERVICE_KEY` | Recommended | Service role key (bypasses RLS) | - |
| `OPENAI_API_KEY` | Yes | OpenAI API key | - |
| `OPENAI_MODEL` | No | OpenAI model for generation | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | No | OpenAI embedding model | `text-embedding-3-small` |
| `DEBUG` | No | Debug mode | `True` |

### Application Settings

Configured in `app/config.py`:
- **API Version**: 1.0.0
- **Project Name**: Skill Capital AI Learning Platform
- **CORS Origins**: Configured for localhost and production domains
- **Default Question Count**: 10
- **Default Difficulty**: medium

---

## 🧪 Testing

### Health Check

```bash
curl http://127.0.0.1:8000/health
```

Returns system status including:
- Supabase connection status
- OpenAI configuration status
- Cache statistics
- System validation (in debug mode)

### API Testing

Use Swagger UI for interactive testing:
- Navigate to http://127.0.0.1:8000/docs
- Test endpoints directly from the browser
- View request/response schemas

---

## 🐛 Troubleshooting

### Common Issues

#### "Supabase client not initialized"
- **Solution**: Check `.env` file has correct `SUPABASE_URL` and `SUPABASE_KEY`
- Verify credentials are not placeholders

#### "new row violates row-level security policy"
- **Solution**: Use `SUPABASE_SERVICE_KEY` for admin operations
- The `generate_all_assessments.py` script uses service key automatically

#### "OpenAI API key not configured"
- **Solution**: Add `OPENAI_API_KEY` to `.env` file
- Get API key from https://platform.openai.com/api-keys

#### "Table does not exist"
- **Solution**: Run `app/models/unified_schema.sql` in Supabase SQL Editor
- Verify all tables are created successfully

#### "Assessments not showing in frontend"
- **Solution**: 
  1. Check assessments have `course_id` set
  2. Verify assessments have `status = 'published'`
  3. Clear browser cache (Ctrl+F5)
  4. Check browser console for errors

#### "Course detection not working"
- **Solution**: 
  1. Verify PDF titles contain course keywords
  2. Check `generate_all_assessments.py` course detection logic
  3. Manually update `course_id` if needed

---

## 🚀 Deployment

### Production Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Environment Variables for Production

Set `DEBUG=False` in production:
```env
DEBUG=False
```

### Frontend Deployment

The frontend is served as static files by FastAPI. For production:
1. Build frontend assets (if using a build process)
2. Ensure static files are in `frontend/` directory
3. FastAPI will serve them automatically

---

## 📚 Key Components

### Assessment Generator (`scripts/generate_all_assessments.py`)

**Purpose**: Generate assessments from PDF embeddings

**Features**:
- Fetches all PDFs from `pdf_embeddings` table
- Detects course automatically from PDF title
- Generates 20 high-quality MCQ questions per PDF
- Creates assessment records with course linking
- Prevents duplicate assessments and questions
- Uses service role key to bypass RLS

**Usage**:
```bash
python scripts/generate_all_assessments.py
```

### Course Detection Logic

The system automatically detects courses from PDF titles:

**Python Indicators**:
- Keywords: "python", "datatypes", "loops", "functions", "classes"
- Patterns: Python-specific terms

**DevOps Indicators**:
- Keywords: "devops", "docker", "kubernetes", "linux", "sonarqube"
- Patterns: Infrastructure and DevOps tools

**Priority**: DevOps indicators are checked first to avoid false positives.

### Question Generation

Each PDF generates 20 questions with:
- **10+ Code-tracing questions**: "What is the output?", "What error will occur?"
- **5+ Conceptual questions**: "Why does X work?", "What is the principle?"
- **5+ Application questions**: "In which scenario?", "How would you solve?"

Questions include:
- 4 multiple-choice options
- Correct answer (A, B, C, or D)
- Detailed explanation
- Difficulty level (easy, medium, hard)
- Topic classification

---

## 🔐 Security

### Authentication
- Uses Supabase JWT authentication
- Service role key for admin operations (bypasses RLS)
- Anon key for regular operations (respects RLS)

### Row Level Security (RLS)
- RLS enabled on all tables
- Admin scripts use service role key
- Frontend uses anon key with proper policies

### API Security
- Rate limiting enabled
- CORS configured for specific origins
- Input validation on all endpoints
- Error handling prevents information leakage

---

## 📊 Performance

### Caching
- In-memory cache for frequently accessed data
- Cache expiration and cleanup
- Cache statistics available via health endpoint

### Database Optimization
- Indexes on frequently queried columns
- Efficient foreign key relationships
- Vector indexes for embedding searches

### API Performance
- Async/await for non-blocking operations
- Connection pooling for database
- Efficient query patterns

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📝 License

[Your License Here]

---

## 🙏 Acknowledgments

- **FastAPI** - Modern web framework
- **Supabase** - Backend-as-a-Service
- **OpenAI** - AI question generation
- **PostgreSQL** - Robust database

---

## 📞 Support

For issues and questions:
1. Check the Troubleshooting section
2. Review API documentation at `/docs`
3. Check Supabase logs for database errors
4. Review application logs for backend errors

---

**Made with ❤️ using FastAPI, Supabase, and OpenAI**

---

## 📅 Version History

- **v1.0.0** (Current)
  - Initial release
  - Course-based assessment organization
  - AI-powered question generation
  - Automated scoring and feedback
  - PDF-based assessment generation

---

## 🔄 Future Enhancements

- [ ] Video-based assessment generation
- [ ] Advanced analytics dashboard
- [ ] Multi-language support
- [ ] Export assessment results to PDF
- [ ] Bulk assessment import
- [ ] Custom question templates
- [ ] Adaptive difficulty adjustment
- [ ] Social features (leaderboards, sharing)
