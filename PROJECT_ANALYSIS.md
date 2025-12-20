# Complete Assessment Project Analysis

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Workflows](#workflows)
6. [Database Schema](#database-schema)
7. [API Endpoints](#api-endpoints)
8. [Frontend Structure](#frontend-structure)
9. [Key Functions & Services](#key-functions--services)
10. [Configuration](#configuration)

---

## Project Overview

**Skill Assessment Builder** is an AI-powered learning platform that automates the complete assessment lifecycle. The system:

- **Generates assessments** from PDF and video content using OpenAI GPT-4
- **Organizes assessments** by courses automatically
- **Delivers assessments** through a web interface
- **Scores automatically** for MCQ questions
- **Provides personalized feedback** using AI
- **Tracks user progress** across courses and skills

### Technology Stack

**Backend:**
- Python 3.10+ with FastAPI 0.104.1
- Supabase (PostgreSQL with pgvector)
- OpenAI GPT-4o-mini for question generation
- OpenAI text-embedding-3-small for embeddings

**Frontend:**
- HTML5/CSS3/JavaScript (ES6+)
- Static files served by FastAPI

**Database:**
- Supabase PostgreSQL
- pgvector extension for vector similarity search
- Row Level Security (RLS) for access control

---

## System Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Frontend      │  HTML/JS/CSS (Static files)
│  (Browser)      │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────┐
│   FastAPI        │  Python Web Framework
│   Backend        │  - Routes (dashboard, assessments, auth)
│                  │  - Services (generation, RAG, feedback)
│                  │  - Utils (logger, cache, validation)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌──────────┐
│Supabase │ │  OpenAI  │
│Database │ │   API    │
│(Postgres│ │  (GPT-4) │
│+pgvector│ │          │
└─────────┘ └──────────┘
```

### Data Flow

**Assessment Generation Flow:**
1. System reads PDF/video embeddings from Supabase
2. RAG service searches for relevant content chunks
3. OpenAI generates MCQ questions from chunks
4. Questions stored in `skill_assessment_questions` table
5. Assessment records created in `assessments` table
6. Assessments linked to courses

**Assessment Taking Flow:**
1. User views courses/assessments on dashboard
2. User starts assessment → creates `attempt` record
3. Questions loaded from database
4. User answers questions
5. Answers submitted → automatic scoring
6. AI generates personalized feedback
7. Results stored in `results` table

---

## Project Structure

```
Assessments/
├── app/                          # Backend Application
│   ├── __init__.py
│   ├── main.py                   # FastAPI entry point & app setup
│   ├── config.py                 # Configuration & environment variables
│   │
│   ├── models/                   # Data Models & Database Schema
│   │   ├── __init__.py
│   │   ├── database.py           # Pydantic models (Profile, Assessment, Question, etc.)
│   │   ├── schemas.py            # Request/Response validation schemas
│   │   └── unified_schema.sql    # PostgreSQL database schema (tables, indexes, RLS)
│   │
│   ├── routes/                    # API Route Handlers
│   │   ├── __init__.py
│   │   ├── dashboard.py          # Main dashboard endpoints (1424 lines)
│   │   ├── assessments.py        # Assessment generation endpoints
│   │   └── auth.py                # Authentication endpoints
│   │
│   ├── services/                  # Business Logic Services
│   │   ├── __init__.py
│   │   ├── assessment_generator.py    # Generates assessments from embeddings
│   │   ├── topic_question_service.py   # Question generation using OpenAI
│   │   ├── rag_service.py             # RAG (Retrieval-Augmented Generation)
│   │   ├── embedding_service.py       # Embedding generation
│   │   ├── feedback_service.py        # AI-powered feedback generation
│   │   ├── supabase_service.py        # Supabase client wrapper
│   │   └── profile_service.py          # User profile management
│   │
│   └── utils/                     # Utility Modules
│       ├── __init__.py
│       ├── logger.py             # Logging configuration
│       ├── error_handler.py      # Global exception handlers
│       ├── auth.py                # JWT authentication utilities
│       ├── cache.py               # In-memory caching
│       ├── rate_limit.py          # Rate limiting middleware
│       ├── validation.py          # System validation
│       ├── constants.py           # Application constants
│       └── helpers.py             # Helper functions
│
├── frontend/                      # Frontend Web Application
│   ├── index.html                # Main dashboard page
│   ├── assessments.html          # Course assessments listing
│   ├── assessment.html            # Assessment taking page
│   ├── results.html               # Results display page
│   ├── app.js                     # Main frontend logic (dashboard)
│   ├── assessment.js              # Assessment taking logic
│   ├── styles.css                 # Global styles
│   └── assets/
│       └── logo.png               # Logo image
│
├── scripts/                       # Utility Scripts
│   └── generate_all_assessments.py  # Standalone assessment generation script
│
├── venv/                          # Python Virtual Environment
├── requirements.txt               # Python dependencies
├── start_backend.ps1              # Windows startup script
├── pytest.ini                     # Pytest configuration
└── README.md                       # Project documentation
```

---

## Core Components

### 1. Main Application (`app/main.py`)

**Purpose:** FastAPI application entry point with middleware, routing, and static file serving.

**Key Features:**
- **Lifespan Management:** Startup/shutdown hooks
  - Checks for placeholder credentials
  - Ensures test user exists
  - Auto-generates assessments if none exist
  - Cache cleanup task
- **CORS Middleware:** Configurable for dev/production
- **Request ID & Timing:** Tracks request processing time
- **Rate Limiting:** Prevents abuse
- **Exception Handlers:** Global error handling
- **Static File Serving:** Serves frontend HTML/CSS/JS
- **Health Check Endpoint:** System status monitoring

**Key Functions:**
- `lifespan()`: Application lifecycle management
- `health_check()`: System health monitoring
- `root()`: Serves frontend index.html

### 2. Configuration (`app/config.py`)

**Purpose:** Centralized configuration using Pydantic Settings.

**Key Settings:**
- Supabase credentials (URL, anon key, service key)
- OpenAI API key and model selection
- JWT configuration
- CORS origins
- Debug mode
- Default question generation parameters

**Features:**
- Environment variable loading from `.env`
- Validation and warnings for placeholder values
- Type-safe configuration with Pydantic

### 3. Database Models (`app/models/`)

**`database.py`:** Pydantic models for type safety
- `Profile`: User profiles
- `Assessment`: Assessment configurations
- `Question`: MCQ questions
- `Attempt`: User assessment attempts
- `Response`: Individual question responses
- `Result`: Aggregated results with feedback
- `Embedding`: Vector embeddings

**`schemas.py`:** Request/Response validation
- `AssessmentCreate/Update/Response`
- `QuestionGenerate/Create/Response`
- `AttemptStart/Response/Update`
- `ResponseSubmit/Score/Response`
- `ResultResponse`
- `SuccessResponse/ErrorResponse`

**`unified_schema.sql`:** PostgreSQL schema
- Table definitions
- Indexes for performance
- Foreign key constraints
- Row Level Security (RLS) policies
- pgvector extension setup

---

## Workflows

### Workflow 1: Assessment Generation

**Trigger:** API call to `/api/generateAssessments` or startup check

**Steps:**
1. **Get Sources** (`assessment_generator.py`)
   - Query `pdf_embeddings` table → unique PDF sources
   - Query `video_embeddings` table → unique video sources
   
2. **For Each Source:**
   - Get text chunks from embeddings (20 chunks per source)
   - Determine difficulty from content complexity
   - Generate course name from source title
   
3. **Question Generation** (`topic_question_service.py`)
   - Use RAG service to find relevant chunks
   - Generate 10 MCQ questions using OpenAI GPT-4
   - Each question includes:
     - Question text
     - 4 options (A, B, C, D)
     - Correct answer
     - Explanation
     - Difficulty level
   
4. **Store Questions**
   - Insert into `skill_assessment_questions` table
   - Link to assessment via `assessment_id`
   
5. **Create Assessment**
   - Create record in `assessments` table
   - Link to course via `course_id`
   - Set status to "published"
   - Store question IDs in `blueprint` (JSON)

**Key Functions:**
- `get_all_pdf_sources()` / `get_all_video_sources()`
- `get_chunks_for_source()`
- `generate_assessment_for_source()`
- `generate_and_store_questions()`

### Workflow 2: Taking an Assessment

**Trigger:** User clicks "START ASSESSMENT" on frontend

**Steps:**
1. **Load Assessment** (`GET /api/assessments/{assessment_id}/questions`)
   - Fetch assessment from database
   - Get questions from `skill_assessment_questions` table
   - Filter by `assessment_id` or use blueprint question IDs
   
2. **Create Attempt**
   - Insert record in `attempts` table
   - Status: "in_progress"
   - Link to test user (single-user mode)
   - Store `started_at` timestamp
   
3. **Return Questions**
   - Remove correct answers (security)
   - Return question text and options only
   - Include `attempt_id` for submission
   
4. **User Answers Questions**
   - Frontend tracks answers in memory
   - Timer counts down from `duration_minutes`
   
5. **Submit Assessment** (`POST /api/submitAssessment`)
   - Receive answers with `attempt_id`
   - Fetch correct answers from database
   - Score each answer (correct/incorrect)
   - Calculate total score and percentage
   
6. **Store Responses**
   - Insert each answer into `responses` table
   - Store score (1 for correct, 0 for incorrect)
   
7. **Update Attempt**
   - Set status to "completed"
   - Store `total_score`, `max_score`, `percentage_score`
   - Set `completed_at` timestamp
   
8. **Generate Feedback** (`feedback_service.py`)
   - Analyze performance (correct/incorrect count)
   - Generate personalized feedback using OpenAI
   - Fallback to rule-based feedback if OpenAI fails
   
9. **Create Result**
   - Insert record in `results` table
   - Store feedback, scores, pass/fail status
   
10. **Return Results**
    - Return score, percentage, feedback
    - Include detailed results per question
    - Frontend displays results page

**Key Functions:**
- `get_assessment_questions()` (dashboard.py)
- `submit_assessment()` (dashboard.py)
- `generate_feedback()` (feedback_service.py)

### Workflow 3: Progress Tracking

**Trigger:** User views dashboard or calls `/api/getProgress`

**Steps:**
1. **Fetch Completed Attempts**
   - Query `attempts` table with status="completed"
   - Filter by test user (if in single-user mode)
   - Join with `results` and `assessments` tables
   
2. **Calculate Statistics**
   - Total assessments completed
   - Average score (from percentage_score)
   - Skill progress (average per skill domain)
   - Topic mastery (correct/total per topic)
   
3. **Recent Assessments**
   - Last 5 completed assessments
   - Include skill name, score, date
   
4. **Return Data**
   - JSON response with all statistics
   - Frontend displays charts and progress bars

**Key Functions:**
- `get_progress()` (dashboard.py)

---

## Database Schema

### Core Tables

**`profiles`**
- User profiles linked to Supabase Auth
- Fields: `id`, `email`, `full_name`, `role`, `organization`

**`courses`**
- Course definitions
- Fields: `id`, `name`, `description`, `created_at`

**`assessments`**
- Assessment configurations
- Fields: `id`, `title`, `description`, `skill_domain`, `difficulty`, `question_count`, `duration_minutes`, `passing_score`, `status`, `blueprint` (JSON), `course_id`, `created_by`

**`skill_assessment_questions`**
- Generated MCQ questions
- Fields: `id`, `assessment_id`, `question`, `options` (JSON array), `correct_answer`, `explanation`, `difficulty`, `topic`, `created_at`

**`attempts`**
- User assessment attempts
- Fields: `id`, `assessment_id`, `user_id`, `status`, `started_at`, `completed_at`, `duration_minutes`, `total_score`, `max_score`, `percentage_score`

**`responses`**
- Individual question responses
- Fields: `id`, `attempt_id`, `question_id`, `answer_text`, `score`, `max_score`, `status`

**`results`**
- Aggregated assessment results
- Fields: `id`, `attempt_id`, `user_id`, `assessment_id`, `total_score`, `max_score`, `percentage_score`, `passing_score`, `passed`, `overall_feedback`, `generated_at`

**`pdf_embeddings`**
- PDF content chunks with vector embeddings
- Fields: `id`, `pdf_id`, `pdf_title`, `content`, `embedding` (vector), `chunk_id`, `page_number`

**`video_embeddings`**
- Video transcript chunks with vector embeddings
- Fields: `id`, `video_id`, `video_title`, `content`, `embedding` (vector), `chunk_id`, `start_time`, `end_time`

### Relationships

```
profiles (1) ──→ (N) attempts
courses (1) ──→ (N) assessments
assessments (1) ──→ (N) skill_assessment_questions
assessments (1) ──→ (N) attempts
attempts (1) ──→ (N) responses
attempts (1) ──→ (1) results
```

---

## API Endpoints

### Dashboard Endpoints (`/api/*`)

**`GET /api/getAssessments`**
- Returns all courses with assessments
- Groups assessments by course
- Includes assessment count per course
- Handles assessments without course_id (creates virtual courses)

**`GET /api/assessments/by_course/{course_id}`**
- Returns assessments for a specific course
- Normalizes assessment titles
- Deduplicates by normalized title

**`GET /api/assessments/{assessment_id}/questions`**
- Returns questions for an assessment
- Creates attempt record
- Removes correct answers (security)
- Returns `attempt_id` for submission

**`POST /api/submitAssessment`**
- Accepts answers with `attempt_id`
- Scores answers automatically
- Generates AI feedback
- Creates result record
- Returns detailed results

**`GET /api/attempts/{attempt_id}/result`**
- Returns complete result data
- Includes questions with explanations
- Shows correct/incorrect answers
- Includes AI-generated feedback

**`GET /api/getProgress`**
- Returns user progress statistics
- Calculates average score
- Skill progress per domain
- Topic mastery percentages
- Recent assessments list

### Assessment Generation Endpoints

**`POST /api/generateAssessments`**
- Generates assessments from all embeddings
- Processes PDF and video sources
- Creates questions and assessments
- Returns generation statistics

**`GET /api/assessments/stats`**
- Returns assessment statistics
- Total assessments and questions
- Questions by difficulty

**`POST /api/embeddings/sync`**
- Alias for generateAssessments
- Syncs embeddings to assessments

### System Endpoints

**`GET /health`**
- Health check with system status
- Supabase connection test
- OpenAI configuration check
- Cache statistics

**`GET /docs`**
- Interactive API documentation (Swagger UI)

**`GET /`**
- Serves frontend index.html

---

## Frontend Structure

### Pages

**`index.html`** - Main Dashboard
- Displays courses with assessments
- Shows progress statistics
- Recent assessments list
- Skill progress charts
- Topic mastery visualization

**`assessments.html`** - Course Assessments
- Lists all assessments for a course
- Filter by difficulty
- Start assessment button

**`assessment.html`** - Assessment Taking
- Displays questions one by one
- Timer countdown
- Answer selection (radio buttons)
- Submit button

**`results.html`** - Results Display
- Shows score and percentage
- Pass/fail status
- AI-generated feedback
- Detailed results per question
- Correct answers with explanations

### JavaScript Files

**`app.js`** - Main Dashboard Logic
- `loadCourses()`: Fetches and displays courses
- `displayCourses()`: Renders course cards
- `loadProgress()`: Loads progress statistics
- `displayTopicMastery()`: Shows topic mastery chart
- `displayRecentAssessments()`: Shows recent assessments
- `refreshChartData()`: Auto-refreshes data

**`assessment.js`** - Assessment Taking Logic
- `startAssessment()`: Loads questions and starts timer
- `displayQuestion()`: Shows current question
- `selectAnswer()`: Records user answer
- `submitAssessment()`: Submits answers and shows results
- `updateTimer()`: Updates countdown timer

### Styling

**`styles.css`** - Global Styles
- Modern, responsive design
- Color scheme and typography
- Card layouts for courses
- Progress bars and charts
- Button styles and animations

---

## Key Functions & Services

### Assessment Generator Service

**File:** `app/services/assessment_generator.py`

**Purpose:** Generates assessments from PDF/video embeddings

**Key Methods:**
- `get_all_pdf_sources()`: Gets unique PDF sources
- `get_all_video_sources()`: Gets unique video sources
- `get_chunks_for_source()`: Retrieves text chunks for a source
- `determine_difficulty_from_chunks()`: Analyzes content complexity
- `generate_assessment_for_source()`: Creates assessment for a source
- `generate_all_assessments()`: Main entry point - processes all sources

**Workflow:**
1. Get all PDF and video sources
2. For each source, get chunks
3. Determine difficulty
4. Generate course name
5. Generate 10 questions using topic_question_service
6. Store questions in database
7. Create assessment record
8. Link to course

### RAG Service

**File:** `app/services/rag_service.py`

**Purpose:** Retrieval-Augmented Generation for context-aware question generation

**Key Methods:**
- `search_similar_chunks()`: Vector similarity search
- `generate_question_with_context()`: Generates question using RAG

**How It Works:**
1. Generate embedding for query text
2. Search `pdf_embeddings` or `video_embeddings` using pgvector
3. Find top N similar chunks (cosine similarity)
4. Use chunks as context for OpenAI question generation
5. Return generated question with context

### Topic Question Service

**File:** `app/services/topic_question_service.py`

**Purpose:** Generates MCQ questions using OpenAI

**Key Methods:**
- `generate_and_store_questions()`: Main question generation method

**Process:**
1. Use RAG to find relevant content chunks
2. Build prompt with chunks as context
3. Call OpenAI GPT-4 to generate question
4. Parse response (JSON format)
5. Validate question structure
6. Store in database

**Question Format:**
```json
{
  "question": "What is React?",
  "options": ["A) Library", "B) Framework", "C) Language", "D) Database"],
  "correct_answer": "A",
  "explanation": "React is a JavaScript library..."
}
```

### Feedback Service

**File:** `app/services/feedback_service.py`

**Purpose:** Generates personalized feedback for assessment results

**Key Methods:**
- `generate_feedback()`: Main feedback generation
- `_analyze_topic_performance()`: Analyzes correct/incorrect answers
- `_generate_llm_feedback()`: Uses OpenAI for feedback
- `_generate_fallback_feedback()`: Rule-based fallback

**Feedback Generation:**
1. Analyze performance (score, percentage, correct count)
2. If OpenAI available: Generate personalized feedback
3. If OpenAI fails: Use rule-based feedback
4. Always return a feedback message (never None)

**Feedback Examples:**
- High score (≥80%): "Excellent work! You've demonstrated strong understanding..."
- Medium score (60-79%): "Good effort! You're on the right track..."
- Low score (<60%): "Keep practicing! Review the areas where you struggled..."

### Supabase Service

**File:** `app/services/supabase_service.py`

**Purpose:** Wrapper for Supabase client with connection management

**Key Methods:**
- `get_client()`: Returns Supabase client (anon or service key)
- `_initialize_client()`: Initializes client from config

**Features:**
- Singleton pattern
- Supports both anon key (respects RLS) and service key (bypasses RLS)
- Automatic retry on connection failure
- Connection pooling

### Profile Service

**File:** `app/services/profile_service.py`

**Purpose:** User profile management (single-user mode)

**Key Methods:**
- `get_test_user_id()`: Gets or creates test user
- `create_test_user()`: Creates test user profile

**Single-User Mode:**
- For Skill Capital, uses a single test user
- All attempts linked to this user
- No authentication required for taking assessments

---

## Configuration

### Environment Variables (`.env` file)

**Required:**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
OPENAI_API_KEY=your-openai-api-key
```

**Optional:**
```env
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
DEBUG=True
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Configuration Loading

1. Loads from `.env` file in project root
2. Validates required variables
3. Warns about placeholder values
4. Falls back to defaults if not set

---

## Key Design Patterns

### 1. Service Layer Pattern
- Business logic separated into services
- Routes only handle HTTP concerns
- Services are reusable and testable

### 2. Repository Pattern (via Supabase)
- Database access abstracted through Supabase client
- Consistent query interface
- Easy to swap database backends

### 3. Dependency Injection
- Services injected into routes
- Configuration loaded once at startup
- Easy to mock for testing

### 4. Singleton Pattern
- Services are singleton instances
- Shared state (Supabase client, OpenAI client)
- Efficient resource usage

### 5. Factory Pattern
- Assessment generator creates assessments
- Question service creates questions
- Feedback service creates feedback

---

## Security Features

1. **Row Level Security (RLS)**
   - Database-level access control
   - Users can only access their own data
   - Service key bypasses RLS for admin operations

2. **Answer Hiding**
   - Correct answers removed from question responses
   - Only shown after submission

3. **Input Validation**
   - Pydantic schemas validate all inputs
   - Prevents SQL injection
   - Type safety

4. **Rate Limiting**
   - Prevents API abuse
   - Configurable limits

5. **Error Handling**
   - No sensitive data in error messages
   - Detailed logging for debugging

---

## Performance Optimizations

1. **Caching**
   - In-memory cache for frequent queries
   - Cache cleanup task runs every 5 minutes

2. **Database Indexes**
   - Indexes on foreign keys
   - Indexes on frequently queried columns
   - Vector indexes for similarity search

3. **Lazy Loading**
   - Questions loaded only when needed
   - Progress calculated on-demand

4. **Connection Pooling**
   - Supabase client reuses connections
   - Efficient database access

---

## Error Handling

### Global Exception Handlers

**`app/utils/error_handler.py`**
- `global_exception_handler()`: Catches all unhandled exceptions
- `http_exception_handler()`: Handles HTTP exceptions
- `validation_exception_handler()`: Handles validation errors
- `app_exception_handler()`: Handles custom app exceptions

### Error Response Format

```json
{
  "success": false,
  "error": "Error message",
  "details": {
    "field": "Additional error details"
  }
}
```

### Logging

**`app/utils/logger.py`**
- Structured logging with request IDs
- Log levels: DEBUG, INFO, WARNING, ERROR
- Logs to console (can be extended to file)

---

## Testing

**Configuration:** `pytest.ini`
- Test discovery patterns
- Async test support

**Dependencies:**
- `pytest==7.4.3`
- `pytest-asyncio==0.21.1`

**Test Structure:**
- Unit tests for services
- Integration tests for API endpoints
- Mock external dependencies (OpenAI, Supabase)

---

## Deployment

### Local Development

**Windows:**
```powershell
.\start_backend.ps1
```

**Linux/Mac:**
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Production Deployment

**Platforms:**
- Vercel (serverless)
- AWS (EC2/Lambda)
- Heroku
- Railway

**Requirements:**
- Set environment variables
- Set `DEBUG=False`
- Configure CORS origins
- Enable RLS policies in Supabase

---

## Future Enhancements

1. **Multi-User Support**
   - Full authentication system
   - User-specific progress tracking
   - Role-based access control

2. **Advanced Question Types**
   - Descriptive questions
   - Coding challenges
   - File upload questions

3. **Analytics Dashboard**
   - Detailed performance analytics
   - Skill gap analysis
   - Learning path recommendations

4. **PDF Report Generation**
   - Downloadable assessment reports
   - Certificate generation
   - Progress reports

5. **Real-Time Features**
   - Live assessment taking
   - Real-time progress updates
   - Collaborative assessments

---

## Conclusion

This is a **production-ready, AI-powered assessment platform** with:

✅ **Complete Assessment Lifecycle:** Generation → Delivery → Scoring → Feedback  
✅ **AI Integration:** OpenAI GPT-4 for question generation and feedback  
✅ **Modern Architecture:** FastAPI, Supabase, pgvector  
✅ **Scalable Design:** Service layer, caching, connection pooling  
✅ **Security:** RLS, input validation, error handling  
✅ **User-Friendly:** Modern frontend with progress tracking  

The codebase is well-organized, documented, and follows best practices for Python web development.

