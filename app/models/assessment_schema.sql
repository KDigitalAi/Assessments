-- ===================================================================
-- ASSESSMENT PROJECT DATABASE SCHEMA
-- ===================================================================
-- Self-contained Assessment System - PDF Only
-- Separate Supabase Database
-- 
-- This schema creates exactly 10 tables:
--   7 Core Assessment Tables
--   3 PDF/RAG Tables
-- 
-- IMPORTANT:
-- - This is a NEW database project (separate from chatbot/RAG)
-- - PDF-only (no video, no chatbot features)
-- - Run this in your NEW Supabase project SQL Editor
-- ===================================================================

-- ===================================================================
-- EXTENSIONS
-- ===================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ===================================================================
-- CORE ASSESSMENT TABLES (7 Tables)
-- ===================================================================

-- ===================================================================
-- TABLE 1: profiles
-- ===================================================================
-- User profiles linked to Supabase Auth
-- ===================================================================
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    role TEXT DEFAULT 'user' CHECK (role IN ('user', 'admin', 'student')),
    organization TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE profiles IS 'User profiles for Assessment system';

CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON profiles(role);

-- ===================================================================
-- TABLE 2: courses
-- ===================================================================
-- Course definitions for grouping assessments
-- ===================================================================
CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE courses IS 'Course definitions for grouping assessments';

CREATE INDEX IF NOT EXISTS idx_courses_name ON courses(name);

-- ===================================================================
-- TABLE 3: assessments
-- ===================================================================
-- Assessment definitions and configurations
-- ===================================================================
CREATE TABLE IF NOT EXISTS assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    skill_domain TEXT NOT NULL,
    difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    question_count INTEGER DEFAULT 10 CHECK (question_count > 0),
    duration_minutes INTEGER DEFAULT 60 CHECK (duration_minutes > 0),
    passing_score INTEGER DEFAULT 60 CHECK (passing_score >= 0 AND passing_score <= 100),
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    blueprint JSONB, -- Stores assessment configuration and PDF reference
    course_id UUID REFERENCES courses(id) ON DELETE SET NULL,
    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE assessments IS 'Assessment definitions for Skill Assessment';

CREATE INDEX IF NOT EXISTS idx_assessments_skill_domain ON assessments(skill_domain);
CREATE INDEX IF NOT EXISTS idx_assessments_course_id ON assessments(course_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_created_by ON assessments(created_by);

-- ===================================================================
-- TABLE 4: skill_assessment_questions
-- ===================================================================
-- Questions generated from PDF embeddings
-- ===================================================================
CREATE TABLE IF NOT EXISTS skill_assessment_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID REFERENCES assessments(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL, -- Array of options for MCQ questions
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    question_type TEXT DEFAULT 'theory' CHECK (question_type IN ('theory', 'coding', 'mcq', 'descriptive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE skill_assessment_questions IS 'Stores questions generated from PDF embeddings';

-- Migration: Add question_type column if it doesn't exist (for existing databases)
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
        AND table_name = 'skill_assessment_questions' 
        AND column_name = 'question_type'
    ) THEN
        ALTER TABLE skill_assessment_questions 
        ADD COLUMN question_type TEXT DEFAULT 'theory';
        
        IF NOT EXISTS (
            SELECT 1 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'public'
            AND table_name = 'skill_assessment_questions' 
            AND constraint_name = 'skill_assessment_questions_question_type_check'
        ) THEN
            ALTER TABLE skill_assessment_questions
            ADD CONSTRAINT skill_assessment_questions_question_type_check 
            CHECK (question_type IN ('theory', 'coding', 'mcq', 'descriptive'));
        END IF;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_assessment_id ON skill_assessment_questions(assessment_id);
CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_topic ON skill_assessment_questions(topic);
CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_difficulty ON skill_assessment_questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_question_type ON skill_assessment_questions(question_type);

-- ===================================================================
-- TABLE 5: attempts
-- ===================================================================
-- User attempts for assessments
-- ===================================================================
CREATE TABLE IF NOT EXISTS attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'in_progress' CHECK (status IN ('in_progress', 'completed', 'abandoned', 'timed_out')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_minutes INTEGER,
    time_spent_seconds INTEGER,
    total_score NUMERIC(10,2) DEFAULT 0,
    max_score NUMERIC(10,2) DEFAULT 0,
    percentage_score NUMERIC(5,2) DEFAULT 0,
    time_remaining INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE attempts IS 'User attempts for assessments';

CREATE INDEX IF NOT EXISTS idx_attempts_assessment_id ON attempts(assessment_id);
CREATE INDEX IF NOT EXISTS idx_attempts_user_id ON attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON attempts(status);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON attempts(created_at);

-- ===================================================================
-- TABLE 6: responses
-- ===================================================================
-- Individual question responses in an attempt
-- ===================================================================
CREATE TABLE IF NOT EXISTS responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES skill_assessment_questions(id) ON DELETE CASCADE,
    answer_text TEXT, -- For descriptive/coding questions
    selected_option TEXT, -- For MCQ questions (A, B, C, D)
    score NUMERIC(10,2) DEFAULT 0,
    max_score NUMERIC(10,2) DEFAULT 1,
    feedback TEXT,
    feedback_json JSONB,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'scored', 'reviewed')),
    auto_scored BOOLEAN DEFAULT TRUE,
    scored_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE responses IS 'Individual question responses in an attempt';

CREATE INDEX IF NOT EXISTS idx_responses_attempt_id ON responses(attempt_id);
CREATE INDEX IF NOT EXISTS idx_responses_question_id ON responses(question_id);
CREATE INDEX IF NOT EXISTS idx_responses_status ON responses(status);

-- ===================================================================
-- TABLE 7: results
-- ===================================================================
-- Final assessment results
-- ===================================================================
CREATE TABLE IF NOT EXISTS results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL UNIQUE REFERENCES attempts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    assessment_id UUID NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    total_score NUMERIC(10,2) NOT NULL,
    max_score NUMERIC(10,2) NOT NULL,
    percentage_score NUMERIC(5,2) NOT NULL,
    passing_score INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    section_scores JSONB,
    overall_feedback TEXT,
    feedback_json JSONB,
    report_url TEXT,
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE results IS 'Final assessment results';

CREATE INDEX IF NOT EXISTS idx_results_attempt_id ON results(attempt_id);
CREATE INDEX IF NOT EXISTS idx_results_user_id ON results(user_id);
CREATE INDEX IF NOT EXISTS idx_results_assessment_id ON results(assessment_id);
CREATE INDEX IF NOT EXISTS idx_results_passed ON results(passed);

-- ===================================================================
-- PDF / RAG TABLES (3 Tables)
-- ===================================================================

-- ===================================================================
-- TABLE 8: pdf_documents
-- ===================================================================
-- PDF file metadata and tracking
-- ===================================================================
CREATE TABLE IF NOT EXISTS pdf_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    file_url TEXT NOT NULL, -- Supabase Storage URL
    file_size BIGINT, -- Size in bytes
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'processed', 'error')),
    error_message TEXT,
    uploaded_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE pdf_documents IS 'Tracks uploaded PDF files and their processing status';

CREATE INDEX IF NOT EXISTS idx_pdf_documents_status ON pdf_documents(status);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_uploaded_by ON pdf_documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_upload_date ON pdf_documents(upload_date);

-- ===================================================================
-- TABLE 9: pdf_embeddings
-- ===================================================================
-- PDF content chunks with vector embeddings
-- ===================================================================
CREATE TABLE IF NOT EXISTS pdf_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pdf_id UUID NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    pdf_title TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536), -- OpenAI text-embedding-3-small dimension
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE pdf_embeddings IS 'Stores PDF text chunks with vector embeddings for RAG';

CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_pdf_id ON pdf_embeddings(pdf_id);
CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_pdf_title ON pdf_embeddings(pdf_title);
CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_chunk_index ON pdf_embeddings(pdf_id, chunk_index);

-- Create vector similarity search index
CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_embedding ON pdf_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ===================================================================
-- TABLE 10: pdf_processing_log
-- ===================================================================
-- Monitor PDF processing pipeline
-- ===================================================================
CREATE TABLE IF NOT EXISTS pdf_processing_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pdf_id UUID NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('uploaded', 'extracting', 'chunking', 'embedding', 'generating_questions', 'completed', 'error')),
    error_message TEXT,
    chunks_created INTEGER DEFAULT 0,
    questions_generated INTEGER DEFAULT 0,
    assessments_created INTEGER DEFAULT 0,
    processing_started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE pdf_processing_log IS 'Tracks PDF processing pipeline status';

CREATE INDEX IF NOT EXISTS idx_pdf_processing_log_pdf_id ON pdf_processing_log(pdf_id);
CREATE INDEX IF NOT EXISTS idx_pdf_processing_log_status ON pdf_processing_log(status);

-- ===================================================================
-- FUNCTIONS AND TRIGGERS
-- ===================================================================

-- ===================================================================
-- UPDATE TIMESTAMP FUNCTION
-- ===================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ===================================================================
-- TRIGGERS FOR AUTO-UPDATE TIMESTAMPS
-- ===================================================================
DROP TRIGGER IF EXISTS update_profiles_updated_at ON profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_courses_updated_at ON courses;
CREATE TRIGGER update_courses_updated_at
    BEFORE UPDATE ON courses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_assessments_updated_at ON assessments;
CREATE TRIGGER update_assessments_updated_at
    BEFORE UPDATE ON assessments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_attempts_updated_at ON attempts;
CREATE TRIGGER update_attempts_updated_at
    BEFORE UPDATE ON attempts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_responses_updated_at ON responses;
CREATE TRIGGER update_responses_updated_at
    BEFORE UPDATE ON responses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_results_updated_at ON results;
CREATE TRIGGER update_results_updated_at
    BEFORE UPDATE ON results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_pdf_documents_updated_at ON pdf_documents;
CREATE TRIGGER update_pdf_documents_updated_at
    BEFORE UPDATE ON pdf_documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_pdf_processing_log_updated_at ON pdf_processing_log;
CREATE TRIGGER update_pdf_processing_log_updated_at
    BEFORE UPDATE ON pdf_processing_log
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ===================================================================
-- VECTOR SIMILARITY SEARCH FUNCTION
-- ===================================================================
CREATE OR REPLACE FUNCTION match_pdf_embeddings(
    query_embedding vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 10,
    filter_pdf_id uuid DEFAULT NULL
)
RETURNS TABLE (
    id uuid,
    pdf_id uuid,
    pdf_title text,
    chunk_text text,
    chunk_index integer,
    page_number integer,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pdf_embeddings.id,
        pdf_embeddings.pdf_id,
        pdf_embeddings.pdf_title,
        pdf_embeddings.chunk_text,
        pdf_embeddings.chunk_index,
        pdf_embeddings.page_number,
        1 - (pdf_embeddings.embedding <=> query_embedding) AS similarity
    FROM pdf_embeddings
    WHERE 
        (filter_pdf_id IS NULL OR pdf_embeddings.pdf_id = filter_pdf_id)
        AND 1 - (pdf_embeddings.embedding <=> query_embedding) > match_threshold
    ORDER BY pdf_embeddings.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ===================================================================
-- DEFAULT DATA
-- ===================================================================

-- Insert default courses
INSERT INTO courses (name, description) 
SELECT 'Python', 'Python programming language assessments'
WHERE NOT EXISTS (SELECT 1 FROM courses WHERE name = 'Python');

INSERT INTO courses (name, description) 
SELECT 'DevOps', 'DevOps tools and practices assessments'
WHERE NOT EXISTS (SELECT 1 FROM courses WHERE name = 'DevOps');

-- ===================================================================
-- VERIFICATION QUERIES
-- ===================================================================
-- Run these after executing the schema to verify everything was created:

-- Check all tables exist
-- SELECT table_name 
-- FROM information_schema.tables 
-- WHERE table_schema = 'public' 
--     AND table_name IN (
--         'profiles',
--         'courses',
--         'assessments', 
--         'skill_assessment_questions',
--         'attempts', 
--         'responses', 
--         'results',
--         'pdf_documents',
--         'pdf_embeddings',
--         'pdf_processing_log'
--     )
-- ORDER BY table_name;

-- Check courses
-- SELECT * FROM courses;

-- Check vector extension
-- SELECT * FROM pg_extension WHERE extname = 'vector';

-- Check vector similarity function
-- SELECT routine_name FROM information_schema.routines 
-- WHERE routine_schema = 'public' AND routine_name = 'match_pdf_embeddings';


