-- ===================================================================
-- ASSESSMENT PROJECT DATABASE SCHEMA (RENAMED TABLES MIGRATION)
-- ===================================================================
-- Safe migration goals:
-- 1) Drop unused table: pdf_processing_log
-- 2) Rename core tables to assessment_* namespace
-- 3) Preserve data and foreign keys
-- 4) Keep pdf_documents and pdf_embeddings unchanged
-- ===================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ===================================================================
-- STEP A: DROP UNUSED TABLE SAFELY
-- ===================================================================
DROP TABLE IF EXISTS pdf_processing_log CASCADE;

-- ===================================================================
-- STEP B: RENAME EXISTING TABLES (SAFE, DATA-PRESERVING)
-- ===================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='profiles')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_profiles') THEN
        ALTER TABLE profiles RENAME TO assessment_profiles;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='courses')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_courses') THEN
        ALTER TABLE courses RENAME TO assessment_courses;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessments')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_assessments') THEN
        ALTER TABLE assessments RENAME TO assessment_assessments;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='skill_assessment_questions')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_questions') THEN
        ALTER TABLE skill_assessment_questions RENAME TO assessment_questions;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='attempts')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_attempts') THEN
        ALTER TABLE attempts RENAME TO assessment_attempts;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='responses')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_responses') THEN
        ALTER TABLE responses RENAME TO assessment_responses;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='results')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='assessment_results') THEN
        ALTER TABLE results RENAME TO assessment_results;
    END IF;
END $$;

-- ===================================================================
-- STEP C: CREATE TABLES IF FRESH DEPLOYMENT
-- ===================================================================
CREATE TABLE IF NOT EXISTS assessment_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID UNIQUE REFERENCES auth.users(id) ON DELETE SET NULL,
    session_id TEXT UNIQUE NOT NULL,
    role TEXT DEFAULT 'student' CHECK (role IN ('student', 'admin')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

DO $$
BEGIN
    -- Safe migration from auth-bound profiles to session-first profiles.
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='assessment_profiles' AND column_name='id'
    ) THEN
        -- If old schema had id -> auth.users, keep IDs/data and add session_id if missing.
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='assessment_profiles' AND column_name='session_id'
        ) THEN
            ALTER TABLE assessment_profiles ADD COLUMN session_id TEXT;
            UPDATE assessment_profiles
            SET session_id = COALESCE(session_id, 'legacy_' || id::text)
            WHERE session_id IS NULL;
            ALTER TABLE assessment_profiles ALTER COLUMN session_id SET NOT NULL;
        END IF;
    END IF;

    -- Ensure optional admin-compatible user_id column exists on existing databases.
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='assessment_profiles' AND column_name='user_id'
    ) THEN
        ALTER TABLE assessment_profiles ADD COLUMN user_id UUID;
        BEGIN
            ALTER TABLE assessment_profiles
            ADD CONSTRAINT assessment_profiles_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS assessment_courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assessment_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    skill_domain TEXT NOT NULL,
    difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    question_count INTEGER DEFAULT 10 CHECK (question_count > 0),
    duration_minutes INTEGER DEFAULT 60 CHECK (duration_minutes > 0),
    passing_score INTEGER DEFAULT 60 CHECK (passing_score >= 0 AND passing_score <= 100),
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    blueprint JSONB,
    course_id UUID REFERENCES assessment_courses(id) ON DELETE SET NULL,
    created_by UUID REFERENCES assessment_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS assessment_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID REFERENCES assessment_assessments(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    question TEXT NOT NULL,
    options JSONB NOT NULL,
    correct_answer TEXT NOT NULL,
    explanation TEXT,
    difficulty TEXT DEFAULT 'medium' CHECK (difficulty IN ('easy', 'medium', 'hard')),
    question_type TEXT DEFAULT 'theory' CHECK (question_type IN ('theory', 'coding', 'mcq', 'descriptive')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assessment_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assessment_id UUID NOT NULL REFERENCES assessment_assessments(id) ON DELETE CASCADE,
    user_id UUID REFERENCES assessment_profiles(id) ON DELETE SET NULL, -- optional admin compatibility
    session_id TEXT NOT NULL,
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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='assessment_attempts' AND column_name='user_id'
    ) THEN
        ALTER TABLE assessment_attempts ADD COLUMN user_id UUID;
        BEGIN
            ALTER TABLE assessment_attempts
            ADD CONSTRAINT assessment_attempts_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES assessment_profiles(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='assessment_attempts' AND column_name='session_id'
    ) THEN
        ALTER TABLE assessment_attempts ADD COLUMN session_id TEXT;
        UPDATE assessment_attempts
        SET session_id = COALESCE(session_id, 'legacy_' || COALESCE(user_id::text, id::text))
        WHERE session_id IS NULL;
        ALTER TABLE assessment_attempts ALTER COLUMN session_id SET NOT NULL;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS assessment_responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    answer_text TEXT,
    selected_option TEXT,
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

CREATE TABLE IF NOT EXISTS assessment_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    attempt_id UUID NOT NULL UNIQUE REFERENCES assessment_attempts(id) ON DELETE CASCADE,
    user_id UUID REFERENCES assessment_profiles(id) ON DELETE SET NULL, -- optional admin compatibility
    session_id TEXT,
    assessment_id UUID NOT NULL REFERENCES assessment_assessments(id) ON DELETE CASCADE,
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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='assessment_results' AND column_name='user_id'
    ) THEN
        ALTER TABLE assessment_results ADD COLUMN user_id UUID;
        BEGIN
            ALTER TABLE assessment_results
            ADD CONSTRAINT assessment_results_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES assessment_profiles(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='assessment_results' AND column_name='session_id'
    ) THEN
        ALTER TABLE assessment_results ADD COLUMN session_id TEXT;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS pdf_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    file_url TEXT NOT NULL,
    file_size BIGINT,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'uploaded' CHECK (status IN ('uploaded', 'processing', 'processed', 'error')),
    assessment_status TEXT DEFAULT 'pending' CHECK (assessment_status IN ('pending', 'generating', 'generated', 'failed')),
    assessment_error_message TEXT,
    assessment_generated_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    uploaded_by UUID REFERENCES assessment_profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'pdf_documents' AND column_name = 'assessment_status'
    ) THEN
        ALTER TABLE pdf_documents ADD COLUMN assessment_status TEXT DEFAULT 'pending';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'pdf_documents' AND column_name = 'assessment_error_message'
    ) THEN
        ALTER TABLE pdf_documents ADD COLUMN assessment_error_message TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'pdf_documents' AND column_name = 'assessment_generated_at'
    ) THEN
        ALTER TABLE pdf_documents ADD COLUMN assessment_generated_at TIMESTAMP WITH TIME ZONE;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = 'pdf_documents'
          AND constraint_name = 'pdf_documents_assessment_status_check'
    ) THEN
        ALTER TABLE pdf_documents
        ADD CONSTRAINT pdf_documents_assessment_status_check
        CHECK (assessment_status IN ('pending', 'generating', 'generated', 'failed'));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS pdf_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pdf_id UUID NOT NULL REFERENCES pdf_documents(id) ON DELETE CASCADE,
    pdf_title TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1536),
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===================================================================
-- INDEXES
-- ===================================================================
CREATE INDEX IF NOT EXISTS idx_assessment_profiles_user_id ON assessment_profiles(user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_profiles_role ON assessment_profiles(role);
CREATE INDEX IF NOT EXISTS idx_assessment_profiles_session_id ON assessment_profiles(session_id);

CREATE INDEX IF NOT EXISTS idx_assessment_courses_name ON assessment_courses(name);

CREATE INDEX IF NOT EXISTS idx_assessment_assessments_skill_domain ON assessment_assessments(skill_domain);
CREATE INDEX IF NOT EXISTS idx_assessment_assessments_course_id ON assessment_assessments(course_id);
CREATE INDEX IF NOT EXISTS idx_assessment_assessments_status ON assessment_assessments(status);
CREATE INDEX IF NOT EXISTS idx_assessment_assessments_created_by ON assessment_assessments(created_by);

CREATE INDEX IF NOT EXISTS idx_assessment_questions_assessment_id ON assessment_questions(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_questions_topic ON assessment_questions(topic);
CREATE INDEX IF NOT EXISTS idx_assessment_questions_difficulty ON assessment_questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_assessment_questions_question_type ON assessment_questions(question_type);

CREATE INDEX IF NOT EXISTS idx_assessment_attempts_assessment_id ON assessment_attempts(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_user_id ON assessment_attempts(user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_session_id ON assessment_attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_status ON assessment_attempts(status);
CREATE INDEX IF NOT EXISTS idx_assessment_attempts_created_at ON assessment_attempts(created_at);

CREATE INDEX IF NOT EXISTS idx_assessment_responses_attempt_id ON assessment_responses(attempt_id);
CREATE INDEX IF NOT EXISTS idx_assessment_responses_question_id ON assessment_responses(question_id);
CREATE INDEX IF NOT EXISTS idx_assessment_responses_status ON assessment_responses(status);

CREATE INDEX IF NOT EXISTS idx_assessment_results_attempt_id ON assessment_results(attempt_id);
CREATE INDEX IF NOT EXISTS idx_assessment_results_user_id ON assessment_results(user_id);
CREATE INDEX IF NOT EXISTS idx_assessment_results_session_id ON assessment_results(session_id);
CREATE INDEX IF NOT EXISTS idx_assessment_results_assessment_id ON assessment_results(assessment_id);
CREATE INDEX IF NOT EXISTS idx_assessment_results_passed ON assessment_results(passed);

CREATE INDEX IF NOT EXISTS idx_pdf_documents_status ON pdf_documents(status);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_uploaded_by ON pdf_documents(uploaded_by);
CREATE INDEX IF NOT EXISTS idx_pdf_documents_upload_date ON pdf_documents(upload_date);

CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_pdf_id ON pdf_embeddings(pdf_id);
CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_pdf_title ON pdf_embeddings(pdf_title);
CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_chunk_index ON pdf_embeddings(pdf_id, chunk_index);
CREATE INDEX IF NOT EXISTS idx_pdf_embeddings_embedding ON pdf_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ===================================================================
-- COMMENTS
-- ===================================================================
COMMENT ON TABLE assessment_profiles IS 'User profiles for Assessment system';
COMMENT ON TABLE assessment_courses IS 'Course definitions for grouping assessments';
COMMENT ON TABLE assessment_assessments IS 'Assessment definitions for Skill Assessment';
COMMENT ON TABLE assessment_questions IS 'Stores questions generated from PDF embeddings';
COMMENT ON TABLE assessment_attempts IS 'User attempts for assessments';
COMMENT ON TABLE assessment_responses IS 'Individual question responses in an attempt';
COMMENT ON TABLE assessment_results IS 'Final assessment results';
COMMENT ON TABLE pdf_documents IS 'Tracks uploaded PDF files and their processing status';
COMMENT ON TABLE pdf_embeddings IS 'Stores PDF text chunks with vector embeddings for RAG';

-- ===================================================================
-- UPDATE TIMESTAMP FUNCTION + TRIGGERS
-- ===================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_assessment_profiles_updated_at ON assessment_profiles;
CREATE TRIGGER update_assessment_profiles_updated_at
    BEFORE UPDATE ON assessment_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_assessment_courses_updated_at ON assessment_courses;
CREATE TRIGGER update_assessment_courses_updated_at
    BEFORE UPDATE ON assessment_courses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_assessment_assessments_updated_at ON assessment_assessments;
CREATE TRIGGER update_assessment_assessments_updated_at
    BEFORE UPDATE ON assessment_assessments
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_assessment_attempts_updated_at ON assessment_attempts;
CREATE TRIGGER update_assessment_attempts_updated_at
    BEFORE UPDATE ON assessment_attempts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_assessment_responses_updated_at ON assessment_responses;
CREATE TRIGGER update_assessment_responses_updated_at
    BEFORE UPDATE ON assessment_responses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_assessment_results_updated_at ON assessment_results;
CREATE TRIGGER update_assessment_results_updated_at
    BEFORE UPDATE ON assessment_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_pdf_documents_updated_at ON pdf_documents;
CREATE TRIGGER update_pdf_documents_updated_at
    BEFORE UPDATE ON pdf_documents
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
INSERT INTO assessment_courses (name, description)
SELECT 'Python', 'Python programming language assessments'
WHERE NOT EXISTS (SELECT 1 FROM assessment_courses WHERE name = 'Python');

INSERT INTO assessment_courses (name, description)
SELECT 'DevOps', 'DevOps tools and practices assessments'
WHERE NOT EXISTS (SELECT 1 FROM assessment_courses WHERE name = 'DevOps');
