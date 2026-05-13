"""
Defect Detection API for KR-AI-Engine
FastAPI endpoints for AI-powered defect detection
"""

import logging
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile

from core.data_models import DefectDetectionResponse
from services.ai_service import AIService
from services.database_adapter import DatabaseAdapter


class DefectDetectionAPI:
    """
    Defect Detection API for KR-AI-Engine

    Endpoints:
    - POST /defect-detection/analyze: Analyze image for defects
    - GET /defect-detection/history: Get detection history
    - POST /defect-detection/feedback: Provide feedback on detection
    """

    def __init__(self, ai_service: AIService, database_service: DatabaseAdapter):
        self.ai_service = ai_service
        self.database_service = database_service
        self.logger = logging.getLogger("krai.api.defect_detection")
        self._setup_logging()

        # Create router
        self.router = APIRouter(prefix="/defect-detection", tags=["defect-detection"])
        self._setup_routes()

    def _setup_logging(self):
        """Setup logging for defect detection API"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - DefectDetectionAPI - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _setup_routes(self):
        """Setup API routes"""

        @self.router.post("/analyze", response_model=DefectDetectionResponse)
        async def analyze_defect(file: UploadFile = File(...), description: str | None = None):
            """Analyze image for defects"""
            try:
                # Read image content
                image_content = await file.read()

                # Validate image format
                if not file.content_type.startswith("image/"):
                    raise HTTPException(status_code=400, detail="File must be an image")

                # Perform defect detection
                detection_result = await self.ai_service.detect_defects(image=image_content, description=description)

                # Create response
                response = DefectDetectionResponse(
                    defect_type=detection_result.get("defect_type", "unknown"),
                    confidence=detection_result.get("confidence", 0.0),
                    suggested_solutions=detection_result.get("suggested_solutions", []),
                    estimated_fix_time=detection_result.get("estimated_fix_time"),
                    required_parts=detection_result.get("required_parts", []),
                    difficulty_level=detection_result.get("difficulty_level", "easy"),
                    related_error_codes=detection_result.get("related_error_codes", []),
                )

                # Log detection event
                await self.database_service.log_audit(
                    action="defect_detection",
                    entity_type="image",
                    entity_id="",
                    details={
                        "defect_type": response.defect_type,
                        "confidence": response.confidence,
                        "filename": file.filename,
                        "file_size": len(image_content),
                        "description": description,
                    },
                )

                return response

            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"Defect detection failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/history")
        async def get_detection_history(limit: int = 10, offset: int = 0, defect_type: str | None = None):
            """Get defect detection history"""
            try:
                # This would typically query the audit log for defect detection events
                # For now, return placeholder data
                history = [
                    {
                        "id": "1",
                        "timestamp": datetime.utcnow().isoformat(),
                        "defect_type": "paper_jam",
                        "confidence": 0.95,
                        "filename": "printer_image_1.jpg",
                        "solutions_provided": 3,
                    },
                    {
                        "id": "2",
                        "timestamp": datetime.utcnow().isoformat(),
                        "defect_type": "toner_issue",
                        "confidence": 0.88,
                        "filename": "printer_image_2.jpg",
                        "solutions_provided": 2,
                    },
                ]

                # Filter by defect type if specified
                if defect_type:
                    history = [h for h in history if h["defect_type"] == defect_type]

                return {
                    "history": history[offset : offset + limit],
                    "total_count": len(history),
                    "limit": limit,
                    "offset": offset,
                }

            except Exception as e:
                self.logger.error(f"Failed to get detection history: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post("/feedback")
        async def provide_feedback(
            detection_id: str, was_helpful: bool, correct_diagnosis: bool, comments: str | None = None
        ):
            """Provide feedback on defect detection"""
            try:
                # This would typically store feedback in the database
                # For now, just log the feedback
                await self.database_service.log_audit(
                    action="defect_detection_feedback",
                    entity_type="detection",
                    entity_id=detection_id,
                    details={"was_helpful": was_helpful, "correct_diagnosis": correct_diagnosis, "comments": comments},
                )

                return {
                    "message": "Feedback recorded successfully",
                    "detection_id": detection_id,
                    "feedback": {
                        "was_helpful": was_helpful,
                        "correct_diagnosis": correct_diagnosis,
                        "comments": comments,
                    },
                }

            except Exception as e:
                self.logger.error(f"Failed to record feedback: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/defect-types")
        async def get_defect_types():
            """Get list of known defect types"""
            try:
                defect_types = [
                    {
                        "type": "paper_jam",
                        "name": "Paper Jam",
                        "description": "Paper stuck in paper path",
                        "common_causes": ["Paper misalignment", "Worn rollers", "Paper quality"],
                        "difficulty": "easy",
                    },
                    {
                        "type": "toner_issue",
                        "name": "Toner Issue",
                        "description": "Problems with toner cartridge or toner supply",
                        "common_causes": ["Empty toner", "Toner leak", "Toner cartridge error"],
                        "difficulty": "medium",
                    },
                    {
                        "type": "mechanical_failure",
                        "name": "Mechanical Failure",
                        "description": "Hardware component failure",
                        "common_causes": ["Worn parts", "Motor failure", "Gear problems"],
                        "difficulty": "hard",
                    },
                    {
                        "type": "connectivity_issue",
                        "name": "Connectivity Issue",
                        "description": "Network or connection problems",
                        "common_causes": ["Network configuration", "Driver issues", "Cable problems"],
                        "difficulty": "easy",
                    },
                ]

                return {"defect_types": defect_types, "total_count": len(defect_types)}

            except Exception as e:
                self.logger.error(f"Failed to get defect types: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.get("/health")
        async def defect_detection_health_check():
            """Defect detection service health check"""
            try:
                # Test AI service
                ai_health = await self.ai_service.health_check()

                return {
                    "status": "healthy" if ai_health["status"] == "healthy" else "degraded",
                    "ai_service": ai_health,
                    "timestamp": datetime.utcnow().isoformat(),
                }

            except Exception as e:
                return {"status": "unhealthy", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
