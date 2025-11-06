"""
System validation utilities for Agentic AI Skill Assessment Builder
"""

from typing import Dict, Any, List, Optional
from app.utils.logger import logger


class SystemValidator:
    """Validate system components are properly initialized and connected"""
    
    @staticmethod
    def validate_agents() -> Dict[str, Any]:
        """Validate all agents are initialized"""
        results = {
            "question_agent": {"status": "unknown", "error": None},
            "scoring_agent": {"status": "unknown", "error": None},
            "analytics_agent": {"status": "unknown", "error": None},
            "remediation_agent": {"status": "unknown", "error": None}
        }
        
        # Optimized: helper function to reduce duplication
        def _validate_agent(agent_name: str, module_name: str):
            """Helper to validate agent"""
            try:
                module = __import__(f"app.agents.{module_name}", fromlist=[agent_name])
                agent = getattr(module, agent_name, None)
                if agent and getattr(agent, "agent", None):
                    results[agent_name]["status"] = "initialized"
                else:
                    results[agent_name]["status"] = "failed"
                    results[agent_name]["error"] = "Agent not initialized"
            except Exception as e:
                results[agent_name]["status"] = "error"
                results[agent_name]["error"] = str(e)
        
        _validate_agent("question_agent", "question_agent")
        _validate_agent("scoring_agent", "scoring_agent")
        _validate_agent("analytics_agent", "analytics_agent")
        _validate_agent("remediation_agent", "remediation_agent")
        
        return results
    
    @staticmethod
    def validate_tools() -> Dict[str, Any]:
        """Validate all tools are importable"""
        results = {
            "db_tools": {"status": "unknown", "tools": []},
            "similarity_tools": {"status": "unknown", "tools": []},
            "feedback_tools": {"status": "unknown", "tools": []},
            "pdf_tools": {"status": "unknown", "tools": []}
        }
        
        try:
            from app.tools.db_tools import (
                get_assessment_tool,
                get_questions_tool,
                create_question_tool,
                check_duplicate_questions_tool,
                get_user_attempts_tool,
                get_assessment_results_tool
            )
            results["db_tools"]["status"] = "loaded"
            results["db_tools"]["tools"] = [
                "get_assessment_tool",
                "get_questions_tool",
                "create_question_tool",
                "check_duplicate_questions_tool",
                "get_user_attempts_tool",
                "get_assessment_results_tool"
            ]
        except Exception as e:
            results["db_tools"]["status"] = "error"
            results["db_tools"]["error"] = str(e)
        
        try:
            from app.tools.similarity_tools import (
                check_question_similarity_tool,
                find_similar_questions_tool,
                generate_embedding_tool
            )
            results["similarity_tools"]["status"] = "loaded"
            results["similarity_tools"]["tools"] = [
                "check_question_similarity_tool",
                "find_similar_questions_tool",
                "generate_embedding_tool"
            ]
        except Exception as e:
            results["similarity_tools"]["status"] = "error"
            results["similarity_tools"]["error"] = str(e)
        
        try:
            from app.tools.feedback_tools import (
                generate_feedback_tool,
                create_learning_path_tool,
                suggest_resources_tool
            )
            results["feedback_tools"]["status"] = "loaded"
            results["feedback_tools"]["tools"] = [
                "generate_feedback_tool",
                "create_learning_path_tool",
                "suggest_resources_tool"
            ]
        except Exception as e:
            results["feedback_tools"]["status"] = "error"
            results["feedback_tools"]["error"] = str(e)
        
        try:
            from app.tools.pdf_tools import (
                generate_report_tool,
                upload_pdf_tool
            )
            results["pdf_tools"]["status"] = "loaded"
            results["pdf_tools"]["tools"] = [
                "generate_report_tool",
                "upload_pdf_tool"
            ]
        except Exception as e:
            results["pdf_tools"]["status"] = "error"
            results["pdf_tools"]["error"] = str(e)
        
        return results
    
    @staticmethod
    def validate_services() -> Dict[str, Any]:
        """Validate all services are importable"""
        results = {}
        
        try:
            from app.services.agent_service import agent_service
            if agent_service:
                results["agent_service"] = {"status": "loaded", "agents": len(agent_service.__dict__)}
            else:
                results["agent_service"] = {"status": "failed", "error": "Service not initialized"}
        except Exception as e:
            results["agent_service"] = {"status": "error", "error": str(e)}
        
        try:
            from app.services.supabase_service import supabase_service
            if supabase_service:
                results["supabase_service"] = {"status": "loaded"}
            else:
                results["supabase_service"] = {"status": "failed"}
        except Exception as e:
            results["supabase_service"] = {"status": "error", "error": str(e)}
        
        try:
            from app.services.langchain_service import langchain_service
            if langchain_service:
                results["langchain_service"] = {"status": "loaded"}
            else:
                results["langchain_service"] = {"status": "failed"}
        except Exception as e:
            results["langchain_service"] = {"status": "error", "error": str(e)}
        
        try:
            from app.services.pdf_service import pdf_service
            if pdf_service:
                results["pdf_service"] = {"status": "loaded"}
            else:
                results["pdf_service"] = {"status": "failed"}
        except Exception as e:
            results["pdf_service"] = {"status": "error", "error": str(e)}
        
        try:
            from app.services.scoring_service import scoring_service
            if scoring_service:
                results["scoring_service"] = {"status": "loaded"}
            else:
                results["scoring_service"] = {"status": "failed"}
        except Exception as e:
            results["scoring_service"] = {"status": "error", "error": str(e)}
        
        return results
    
    @staticmethod
    def validate_routes() -> Dict[str, Any]:
        """Validate all routes are importable"""
        results = {}
        
        routes_to_check = [
            "assessments",
            "questions",
            "attempts",
            "reports",
            "analytics"
        ]
        
        for route_name in routes_to_check:
            try:
                module = __import__(f"app.routes.{route_name}", fromlist=[route_name])
                if hasattr(module, "router"):
                    results[route_name] = {"status": "loaded", "has_router": True}
                else:
                    results[route_name] = {"status": "warning", "has_router": False}
            except Exception as e:
                results[route_name] = {"status": "error", "error": str(e)}
        
        return results
    
    @staticmethod
    def full_validation() -> Dict[str, Any]:
        """Perform full system validation"""
        logger.info("Starting full system validation...")
        
        validation_results = {
            "agents": SystemValidator.validate_agents(),
            "tools": SystemValidator.validate_tools(),
            "services": SystemValidator.validate_services(),
            "routes": SystemValidator.validate_routes(),
            "overall_status": "unknown"
        }
        
        # Determine overall status
        all_agents_ok = all(
            agent["status"] == "initialized"
            for agent in validation_results["agents"].values()
        )
        
        all_tools_ok = all(
            tool["status"] == "loaded"
            for tool in validation_results["tools"].values()
        )
        
        all_services_ok = all(
            service["status"] == "loaded"
            for service in validation_results["services"].values()
        )
        
        all_routes_ok = all(
            route["status"] == "loaded"
            for route in validation_results["routes"].values()
        )
        
        if all_agents_ok and all_tools_ok and all_services_ok and all_routes_ok:
            validation_results["overall_status"] = "healthy"
            logger.info("System validation passed - all components healthy")
        else:
            validation_results["overall_status"] = "degraded"
            logger.warning("System validation found issues - some components may not be working")
        
        return validation_results


# Global validator instance
system_validator = SystemValidator()

