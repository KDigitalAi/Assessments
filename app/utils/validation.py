"""
System validation utilities for Agentic AI Skill Assessment Builder
"""

from typing import Dict, Any, List, Optional
from app.utils.logger import logger


class SystemValidator:
    """Validate system components are properly initialized and connected"""
    
    @staticmethod
    def validate_agents() -> Dict[str, Any]:
        """Validate all agents are initialized - currently not implemented"""
        return {
            "note": "Agents module not implemented in this version",
            "status": "not_implemented"
        }
    
    @staticmethod
    def validate_tools() -> Dict[str, Any]:
        """Validate all tools are importable - currently not implemented"""
        return {
            "note": "Tools module not implemented in this version",
            "status": "not_implemented"
        }
    
    @staticmethod
    def validate_services() -> Dict[str, Any]:
        """Validate all services are importable"""
        results = {}
        
        # Validate existing services only
        services_to_check = [
            "supabase_service",
            "assessment_generator",
            "embedding_service",
            "feedback_service",
            "profile_service",
            "rag_service",
            "topic_question_service"
        ]
        
        for service_name in services_to_check:
            try:
                module = __import__(f"app.services.{service_name}", fromlist=[service_name])
                service = getattr(module, service_name, None)
                if service:
                    results[service_name] = {"status": "loaded"}
                else:
                    results[service_name] = {"status": "failed", "error": "Service not initialized"}
            except ImportError:
                results[service_name] = {"status": "not_found", "error": "Module does not exist"}
            except Exception as e:
                results[service_name] = {"status": "error", "error": str(e)}
        
        return results
    
    @staticmethod
    def validate_routes() -> Dict[str, Any]:
        """Validate all routes are importable"""
        results = {}
        
        routes_to_check = [
            "assessments",
            "dashboard",
            "auth"
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
        
        # Determine overall status (only check services and routes that exist)
        all_services_ok = all(
            service.get("status") == "loaded"
            for service in validation_results["services"].values()
        )
        
        all_routes_ok = all(
            route.get("status") == "loaded"
            for route in validation_results["routes"].values()
        )
        
        if all_services_ok and all_routes_ok:
            validation_results["overall_status"] = "healthy"
            logger.info("System validation passed - all components healthy")
        else:
            validation_results["overall_status"] = "degraded"
            logger.warning("System validation found issues - some components may not be working")
        
        return validation_results


# Global validator instance
system_validator = SystemValidator()

