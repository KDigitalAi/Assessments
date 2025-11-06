-- ===================================================================
-- UNIFIED DATABASE SCHEMA FOR SKILL CAPITAL ASSESSMENT + RAG SYSTEM
-- ===================================================================
-- This schema creates all tables needed for both:
--   1. Skill Assessment module (assessments, attempts, questions, results)
--   2. RAG Chatbot module (video embeddings, PDF embeddings, chat history)
-- 
-- IMPORTANT NOTES:
-- - This schema uses CREATE TABLE IF NOT EXISTS to avoid conflicts
-- - RAG tables (video_embeddings, pdf_embeddings, chat_history, user_queries)
--   are documented but assumed to already exist from the vimeo_video_chatbot project
-- - If RAG tables don't exist, you'll need to create them separately
-- - Run this in Supabase SQL Editor with proper permissions
-- ===================================================================

-- ===================================================================
-- EXTENSIONS
-- ===================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ===================================================================
-- PART 1: SKILL ASSESSMENT TABLES
-- ===================================================================

-- ===================================================================
-- TABLE 1: Profiles
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

COMMENT ON TABLE profiles IS 'User profiles for Skill Assessment system';

CREATE INDEX IF NOT EXISTS idx_profiles_email ON profiles(email);
CREATE INDEX IF NOT EXISTS idx_profiles_role ON profiles(role);

-- ===================================================================
-- TABLE 2: Assessments
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
    blueprint TEXT,
    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE assessments IS 'Assessment definitions for Skill Assessment';

CREATE INDEX IF NOT EXISTS idx_assessments_skill_domain ON assessments(skill_domain);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessments_created_by ON assessments(created_by);

-- ===================================================================
-- TABLE 3: Attempts
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
-- TABLE 4: Responses
-- ===================================================================
-- Individual question responses in an attempt
-- ===================================================================
CREATE TABLE IF NOT EXISTS responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    question_id UUID NOT NULL, -- References skill_assessment_questions(id)
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
-- TABLE 5: Results
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
-- TABLE 6: Skill Assessment Questions
-- ===================================================================
-- Questions generated from video and PDF embeddings
-- ===================================================================
CREATE TABLE IF NOT EXISTS skill_assessment_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL, -- Array of options for MCQ questions
    correct_answer TEXT NOT NULL,
    source_type TEXT CHECK (source_type IN ('pdf', 'video', 'both')),
    source_id TEXT, -- Video ID or document ID if applicable
    explanation TEXT, -- Optional explanation for the answer
    difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE skill_assessment_questions IS 'Stores questions generated from existing video and PDF embeddings';

CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_topic ON skill_assessment_questions(topic);
CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_source_type ON skill_assessment_questions(source_type);
CREATE INDEX IF NOT EXISTS idx_skill_assessment_questions_created_at ON skill_assessment_questions(created_at);

-- ===================================================================
-- PART 2: RAG SYSTEM TABLES (Documentation Only)
-- ===================================================================
-- NOTE: These tables are assumed to already exist from the 
--       vimeo_video_chatbot project. If they don't exist, you'll
--       need to create them separately.
-- 
-- Expected RAG tables:
-- 
-- 1. video_embeddings
--    - id (UUID)
--    - video_id (TEXT)
--    - video_title (TEXT)
--    - video_url (TEXT)
--    - chunk_text (TEXT)
--    - embedding (vector)
--    - chunk_index (INTEGER)
--    - created_at (TIMESTAMP)
-- 
-- 2. pdf_embeddings
--    - id (UUID)
--    - pdf_id (TEXT)
--    - pdf_title (TEXT)
--    - pdf_url (TEXT)
--    - chunk_text (TEXT)
--    - embedding (vector)
--    - chunk_index (INTEGER)
--    - created_at (TIMESTAMP)
-- 
-- 3. chat_history
--    - id (UUID)
--    - user_id (UUID) - Optional, for user tracking
--    - query_text (TEXT)
--    - response_text (TEXT)
--    - source_type (TEXT) - 'video', 'pdf', 'both'
--    - source_ids (JSONB) - Array of source IDs used
--    - created_at (TIMESTAMP)
-- 
-- 4. user_queries
--    - id (UUID)
--    - user_id (UUID) - Optional
--    - query_text (TEXT)
--    - source_type (TEXT)
--    - created_at (TIMESTAMP)
-- 
-- If these tables don't exist, create them with appropriate schema
-- matching the structure expected by the RAG service.
-- ===================================================================

-- ===================================================================
-- PART 3: FUNCTIONS AND TRIGGERS
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

-- ===================================================================
-- VERIFICATION QUERIES
-- ===================================================================
-- Run these after executing the schema to verify everything was created:

-- Check all Skill Assessment tables exist
-- SELECT table_name 
-- FROM information_schema.tables 
-- WHERE table_schema = 'public' 
--     AND table_name IN (
--         'profiles', 
--         'assessments', 
--         'attempts', 
--         'responses', 
--         'results', 
--         'skill_assessment_questions'
--     )
-- ORDER BY table_name;

-- Check foreign key constraints
-- SELECT
--     tc.table_name, 
--     kcu.column_name, 
--     ccu.table_name AS foreign_table_name
-- FROM information_schema.table_constraints AS tc 
-- JOIN information_schema.key_column_usage AS kcu
--     ON tc.constraint_name = kcu.constraint_name
-- JOIN information_schema.constraint_column_usage AS ccu
--     ON ccu.constraint_name = tc.constraint_name
-- WHERE tc.constraint_type = 'FOREIGN KEY'
--     AND tc.table_schema = 'public'
-- ORDER BY tc.table_name;

-- Check RAG tables exist (if applicable)
-- SELECT table_name 
-- FROM information_schema.tables 
-- WHERE table_schema = 'public' 
--     AND table_name IN (
--         'video_embeddings', 
--         'pdf_embeddings', 
--         'chat_history', 
--         'user_queries'
--     )
-- ORDER BY table_name;

