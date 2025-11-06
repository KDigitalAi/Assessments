"""
Feedback generation service using OpenAI API
Generates personalized, motivational feedback for assessment results
"""

from typing import Dict, Any, Optional, List
from openai import OpenAI
from app.config import settings
from app.utils.logger import logger


class FeedbackService:
    """Service for generating personalized assessment feedback"""
    
    def __init__(self):
        """Initialize feedback service"""
        self.client = None
        self._initialize_openai_client()
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client"""
        try:
            if settings.OPENAI_API_KEY and "your-openai" not in settings.OPENAI_API_KEY:
                self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("OpenAI client initialized for feedback service")
            else:
                logger.warning("OpenAI API key not configured. Feedback generation will use fallback messages.")
                self.client = None
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            self.client = None
    
    def generate_feedback(
        self,
        score: float,
        max_score: float,
        percentage: float,
        passed: bool,
        results: List[Dict[str, Any]],
        skill_domain: Optional[str] = None
    ) -> str:
        """
        Generate personalized feedback based on assessment results
        
        Args:
            score: Total score achieved
            max_score: Maximum possible score
            percentage: Percentage score
            passed: Whether the assessment was passed
            results: List of detailed question results
            skill_domain: Skill/topic name (optional)
        
        Returns:
            Personalized feedback message
        """
        # Analyze topic-wise performance if results are available
        topic_analysis = self._analyze_topic_performance(results)
        
        # Generate feedback using OpenAI if available
        if self.client:
            try:
                feedback = self._generate_llm_feedback(
                    score=score,
                    max_score=max_score,
                    percentage=percentage,
                    passed=passed,
                    topic_analysis=topic_analysis,
                    skill_domain=skill_domain
                )
                if feedback and len(feedback.strip()) > 0:
                    logger.info("✅ Generated feedback using OpenAI")
                    return feedback
                else:
                    logger.warning("OpenAI returned empty feedback. Using fallback.")
            except Exception as e:
                logger.warning(f"OpenAI feedback generation failed: {str(e)}. Using fallback.")
        
        # Fallback to rule-based feedback (always returns a message)
        fallback_feedback = self._generate_fallback_feedback(
            score=score,
            max_score=max_score,
            percentage=percentage,
            passed=passed,
            topic_analysis=topic_analysis,
            skill_domain=skill_domain
        )
        logger.info("✅ Generated fallback feedback")
        return fallback_feedback
    
    def _analyze_topic_performance(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance by topic/question type"""
        if not results:
            return {}
        
        total = len(results)
        correct = sum(1 for r in results if r.get("is_correct", False))
        accuracy = (correct / total * 100) if total > 0 else 0
        
        # Identify strong and weak areas
        # For now, we'll use overall accuracy, but this can be extended
        # to analyze by question difficulty or topic if that data is available
        
        return {
            "total_questions": total,
            "correct_answers": correct,
            "accuracy": accuracy,
            "strong_areas": [],  # Can be extended with topic analysis
            "weak_areas": []     # Can be extended with topic analysis
        }
    
    def _generate_llm_feedback(
        self,
        score: float,
        max_score: float,
        percentage: float,
        passed: bool,
        topic_analysis: Dict[str, Any],
        skill_domain: Optional[str] = None
    ) -> Optional[str]:
        """Generate feedback using OpenAI API"""
        if not self.client:
            return None
        
        try:
            # Build prompt for feedback generation
            skill_context = f" in {skill_domain}" if skill_domain else ""
            accuracy = topic_analysis.get("accuracy", 0)
            correct = topic_analysis.get("correct_answers", 0)
            total = topic_analysis.get("total_questions", 0)
            
            prompt = f"""Generate a short, personalized, and motivational feedback message for a student who just completed an assessment{skill_context}.

Assessment Results:
- Score: {score:.1f} out of {max_score:.1f}
- Percentage: {percentage:.1f}%
- Status: {'Passed' if passed else 'Needs Improvement'}
- Correct Answers: {correct} out of {total} questions
- Accuracy: {accuracy:.1f}%

Requirements:
1. Start with a motivational message (e.g., "Great job!", "You're improving fast!", "Excellent work!")
2. Provide positive reinforcement for their performance
3. If accuracy is below 70%, gently suggest areas to focus on
4. Always end with encouragement to continue learning
5. Keep the tone positive, supportive, and student-friendly - never discouraging
6. Maximum 3-4 sentences
7. Use emojis sparingly (1-2 max) if appropriate

Generate only the feedback message, no additional text:"""

            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a supportive and encouraging educational assistant. Generate personalized, positive feedback for students based on their assessment performance. Always maintain an uplifting and motivational tone."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            feedback = response.choices[0].message.content.strip()
            
            # Clean up feedback (remove quotes if present)
            if feedback.startswith('"') and feedback.endswith('"'):
                feedback = feedback[1:-1]
            if feedback.startswith("'") and feedback.endswith("'"):
                feedback = feedback[1:-1]
            
            return feedback
            
        except Exception as e:
            logger.error(f"Error generating LLM feedback: {str(e)}")
            return None
    
    def _generate_fallback_feedback(
        self,
        score: float,
        max_score: float,
        percentage: float,
        passed: bool,
        topic_analysis: Dict[str, Any],
        skill_domain: Optional[str] = None
    ) -> str:
        """Generate fallback feedback using rule-based approach"""
        skill_context = f" in {skill_domain}" if skill_domain else ""
        
        if percentage >= 90:
            return f" Outstanding work{skill_context}! You've demonstrated excellent understanding and mastery. Keep up this fantastic performance and continue challenging yourself with more advanced topics!"
        elif percentage >= 80:
            return f" Great job{skill_context}! You're showing strong comprehension and are on the right track. Keep practicing and you'll master this skill completely soon!"
        elif percentage >= 70:
            return f" Good effort{skill_context}! You're making solid progress. Focus on reviewing the areas where you had difficulty, and with continued practice, you'll see even better results next time!"
        elif percentage >= 60:
            return f" Nice work{skill_context}! You're improving and getting closer to mastery. Review the questions you missed, focus on those topics, and keep practicing. You're on the right path!"
        else:
            return f" Great effort{skill_context}! Every assessment is a learning opportunity. Review the areas where you struggled, focus on understanding the concepts, and keep practicing. You'll get even better results next time!"

