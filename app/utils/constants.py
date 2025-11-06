"""
Application constants and enums
"""

from enum import Enum


class QuestionType(str, Enum):
    """Question type enumeration"""
    MCQ = "mcq"
    DESCRIPTIVE = "descriptive"
    CODING = "coding"


class Difficulty(str, Enum):
    """Difficulty level enumeration"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AssessmentStatus(str, Enum):
    """Assessment status enumeration"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AttemptStatus(str, Enum):
    """Attempt status enumeration"""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    TIMED_OUT = "timed_out"


class ResponseStatus(str, Enum):
    """Response status enumeration"""
    PENDING = "pending"
    SCORED = "scored"
    REVIEWING = "reviewing"


# Prompt Templates
QUESTION_GENERATION_PROMPT = """You are an expert assessment question generator.
Generate {question_type} questions for the skill assessment with the following requirements:

Skill Domain: {skill_domain}
Difficulty Level: {difficulty}
Context/Blueprint: {blueprint}

Requirements:
1. Create {question_type} questions that accurately assess the skill
2. For MCQ questions, provide 4 options with exactly one correct answer
3. For descriptive questions, provide a clear rubric for evaluation
4. Ensure questions are relevant and practical
5. Include explanations for correct answers

Generate the question in JSON format with the following structure:
{{
    "question": "The question text",
    "question_type": "{question_type}",
    "difficulty": "{difficulty}",
    "options": ["option1", "option2", "option3", "option4"],  // Only for MCQ
    "correct_answer": "correct option index or answer key",
    "explanation": "Why this answer is correct",
    "rubric": "{{"criteria": "description", "points": 10}}",  // Only for descriptive
    "tags": ["tag1", "tag2"]
}}
"""

RUBRIC_SCORING_PROMPT = """You are an expert evaluator for skill assessments.
Evaluate the following descriptive answer using the provided rubric.

Question: {question}
Rubric: {rubric}
Candidate Answer: {answer}

Evaluate the answer and provide:
1. Score (0-{max_points})
2. Detailed feedback
3. Strengths and weaknesses
4. Suggestions for improvement

Respond in JSON format:
{{
    "score": <number>,
    "max_score": {max_points},
    "feedback": "Detailed feedback text",
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "suggestions": ["suggestion1", "suggestion2"]
}}
"""

FEEDBACK_GENERATION_PROMPT = """Generate comprehensive feedback for the assessment response.

Question: {question}
Candidate Answer: {answer}
Score: {score}/{max_score}
Evaluation: {evaluation}

Provide:
1. A clear explanation of why the answer was correct/incorrect
2. Learning points and key takeaways
3. Recommended resources or topics to review
4. Encouraging and constructive tone

Format as JSON:
{{
    "explanation": "Why the answer was evaluated this way",
    "learning_points": ["point1", "point2"],
    "resources": ["resource1", "resource2"],
    "encouragement": "Encouraging message"
}}
"""

# Error Messages
ERROR_MESSAGES = {
    "AUTH_REQUIRED": "Authentication required",
    "INVALID_TOKEN": "Invalid or expired token",
    "ASSESSMENT_NOT_FOUND": "Assessment not found",
    "QUESTION_NOT_FOUND": "Question not found",
    "ATTEMPT_NOT_FOUND": "Attempt not found",
    "INVALID_ATTEMPT": "Attempt is not in progress",
    "ATTEMPT_EXPIRED": "Assessment attempt has expired",
    "SCORING_FAILED": "Failed to score response"
}

