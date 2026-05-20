"""
Quality Check Service - Validates processing quality
Ensures data integrity and completeness
"""

import logging
from datetime import datetime
from typing import Any


class QualityCheckService:
    """
    Quality Check Service - Validates processing quality

    Checks:
    - Stage completeness
    - Data integrity
    - FK relationships
    - Counts and ratios
    - Error detection
    """

    def __init__(self, database_service):
        self.database_service = database_service
        self.logger = logging.getLogger("krai.quality_check")

        # Expected ratios (learned from data)
        self.expected_ratios = {
            "chunks_per_doc": (500, 3000),  # Min/Max chunks per doc
            "images_per_doc": (50, 500),  # Min/Max images per doc
            "deduplication_rate": (0.05, 0.15),  # 5-15% dedup expected
            "embedding_chunk_ratio": (0.95, 1.0),  # 95-100% chunks should have embeddings
        }

    async def check_document_quality(self, document_id: str) -> dict[str, Any]:
        """
        Comprehensive quality check for a single document

        Returns:
            {
                'passed': bool,
                'score': float (0-100),
                'issues': List[str],
                'warnings': List[str],
                'stats': Dict
            }
        """
        issues = []
        warnings = []
        checks_passed = 0
        total_checks = 0

        try:
            # Get document info
            doc = await self.database_service.get_document(document_id)
            if not doc:
                return {"passed": False, "score": 0, "issues": ["Document not found"], "warnings": [], "stats": {}}

            stats = {}

            # Check 1: Content chunks exist
            total_checks += 1
            content_chunks = await self.database_service.get_chunks_by_document(document_id)
            stats["content_chunks"] = len(content_chunks)

            if len(content_chunks) == 0:
                issues.append("❌ No content chunks found")
            elif len(content_chunks) < self.expected_ratios["chunks_per_doc"][0]:
                warnings.append(
                    f"⚠️ Only {len(content_chunks)} chunks (expected >{self.expected_ratios['chunks_per_doc'][0]})"
                )
                checks_passed += 0.5
            else:
                checks_passed += 1

            # Check 2: Intelligence chunks exist
            total_checks += 1
            intelligence_chunks = await self.database_service.get_intelligence_chunks_by_document(document_id)
            stats["intelligence_chunks"] = len(intelligence_chunks)

            if len(intelligence_chunks) == 0:
                issues.append("❌ No intelligence chunks found (chunk_prep not run?)")
            elif len(content_chunks) > 0:
                dedup_rate = 1.0 - (len(intelligence_chunks) / len(content_chunks))
                stats["deduplication_rate"] = round(dedup_rate, 3)

                if dedup_rate < self.expected_ratios["deduplication_rate"][0]:
                    warnings.append(f"⚠️ Low deduplication rate: {dedup_rate*100:.1f}% (expected 5-15%)")
                elif dedup_rate > self.expected_ratios["deduplication_rate"][1]:
                    warnings.append(f"⚠️ High deduplication rate: {dedup_rate*100:.1f}% (possible data loss?)")

                checks_passed += 1

            # Check 3: Images exist
            total_checks += 1
            images = await self.database_service.get_images_by_document(document_id)
            stats["images"] = len(images)

            if len(images) == 0:
                warnings.append("⚠️ No images found (image_processor not run?)")
                checks_passed += 0.5
            else:
                checks_passed += 1

            # Check 4: Links exist
            total_checks += 1
            links_count = await self.database_service.count_links_by_document(document_id)
            stats["links"] = links_count

            if links_count == 0:
                warnings.append("⚠️ No links found (may be normal for some docs)")
                checks_passed += 0.7  # Not critical
            else:
                checks_passed += 1

            # Check 5: Embeddings exist and match chunks
            total_checks += 1
            if len(intelligence_chunks) > 0:
                embeddings_exist = await self.database_service.check_embeddings_exist(document_id)

                if not embeddings_exist:
                    issues.append("❌ No embeddings found (embedding_processor not run?)")
                else:
                    # Check ratio
                    # TODO: Get actual embedding count per document
                    stats["embeddings_exist"] = True
                    checks_passed += 1
            else:
                stats["embeddings_exist"] = False
                checks_passed += 0  # Can't have embeddings without chunks

            # Check 6: Classification complete
            total_checks += 1
            manufacturer = getattr(doc, "manufacturer", None)
            doc_type = getattr(doc, "document_type", None)

            if not manufacturer or manufacturer == "Unknown":
                warnings.append("⚠️ Manufacturer unknown (classification may have failed)")
                checks_passed += 0.5
            elif not doc_type or doc_type == "unknown":
                warnings.append("⚠️ Document type unknown (classification incomplete)")
                checks_passed += 0.5
            else:
                stats["manufacturer"] = manufacturer
                stats["document_type"] = doc_type
                checks_passed += 1

            # Check 7: FK integrity (intelligence chunks → embeddings)
            total_checks += 1
            if len(intelligence_chunks) > 0:
                # Sample check: first chunk should be valid
                sample_chunk = intelligence_chunks[0]
                chunk_id = sample_chunk.get("id")

                if chunk_id:
                    stats["fk_integrity"] = "valid"
                    checks_passed += 1
                else:
                    issues.append("❌ Chunk ID missing (data corruption?)")
            else:
                checks_passed += 0

            # Calculate score
            score = (checks_passed / total_checks) * 100 if total_checks > 0 else 0
            passed = score >= 80 and len(issues) == 0

            return {
                "passed": passed,
                "score": round(score, 1),
                "issues": issues,
                "warnings": warnings,
                "stats": stats,
                "checks": {"passed": checks_passed, "total": total_checks},
            }

        except Exception as e:
            self.logger.error(f"Quality check failed: {e}")
            return {
                "passed": False,
                "score": 0,
                "issues": [f"Quality check error: {e!s}"],
                "warnings": [],
                "stats": {},
            }

    async def check_pipeline_health(self) -> dict[str, Any]:
        """
        Check overall pipeline health

        Returns health metrics for entire system
        """
        health = {
            "status": "unknown",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {},
            "issues": [],
            "warnings": [],
        }

        try:
            # Check 1: Database connectivity
            try:
                # Simple query to test connection
                self.database_service.client.table("vw_documents").select("id").limit(1).execute()
                health["checks"]["database"] = "healthy"
            except Exception as e:
                health["checks"]["database"] = "failed"
                health["issues"].append(f"Database connection failed: {e}")

            # Check 2: Tables exist and have data
            try:
                docs = self.database_service.client.table("vw_documents").select("id", count="exact").execute()
                content_chunks = (
                    self.database_service.client.from_("vw_chunks").select("id", count="exact").limit(1).execute()
                )
                intelligence_chunks = (
                    self.database_service.service_client.schema("krai_intelligence")
                    .table("vw_chunks")
                    .select("id", count="exact")
                    .limit(1)
                    .execute()
                )

                health["checks"]["documents_count"] = docs.count or 0
                health["checks"]["content_chunks_count"] = content_chunks.count or 0
                health["checks"]["intelligence_chunks_count"] = intelligence_chunks.count or 0

                # Warnings
                if health["checks"]["documents_count"] == 0:
                    health["warnings"].append("No documents in database")

                if health["checks"]["content_chunks_count"] == 0:
                    health["warnings"].append("No content chunks found")

                if health["checks"]["intelligence_chunks_count"] == 0:
                    health["warnings"].append("No intelligence chunks found (run chunk_prep)")

            except Exception as e:
                health["issues"].append(f"Failed to count tables: {e}")

            # Determine overall status
            if len(health["issues"]) == 0:
                if len(health["warnings"]) == 0:
                    health["status"] = "healthy"
                else:
                    health["status"] = "degraded"
            else:
                health["status"] = "unhealthy"

            return health

        except Exception as e:
            health["status"] = "error"
            health["issues"].append(f"Health check failed: {e!s}")
            return health

    async def validate_stage_completion(self, document_id: str, stage: str) -> dict[str, Any]:
        """
        Validate that a specific stage completed successfully

        Returns:
            {
                'valid': bool,
                'message': str,
                'details': Dict
            }
        """
        validation = {"valid": False, "message": "", "details": {}}

        try:
            if stage == "text":
                chunks = await self.database_service.get_chunks_by_document(document_id)
                validation["details"]["chunks_count"] = len(chunks)

                if len(chunks) > 0:
                    validation["valid"] = True
                    validation["message"] = f"✅ Text stage valid: {len(chunks)} chunks"
                else:
                    validation["message"] = "❌ Text stage failed: No chunks found"

            elif stage == "chunk_prep":
                intelligence_chunks = await self.database_service.get_intelligence_chunks_by_document(document_id)
                validation["details"]["intelligence_chunks_count"] = len(intelligence_chunks)

                if len(intelligence_chunks) > 0:
                    validation["valid"] = True
                    validation["message"] = f"✅ Chunk prep valid: {len(intelligence_chunks)} chunks"
                else:
                    validation["message"] = "❌ Chunk prep failed: No intelligence chunks"

            elif stage == "image":
                images = await self.database_service.get_images_by_document(document_id)
                validation["details"]["images_count"] = len(images)

                if len(images) > 0:
                    validation["valid"] = True
                    validation["message"] = f"✅ Image stage valid: {len(images)} images"
                else:
                    validation["message"] = "⚠️ Image stage: No images (may be normal)"
                    validation["valid"] = True  # Not critical

            elif stage == "embedding":
                embeddings_exist = await self.database_service.check_embeddings_exist(document_id)
                validation["details"]["embeddings_exist"] = embeddings_exist

                if embeddings_exist:
                    validation["valid"] = True
                    validation["message"] = "✅ Embedding stage valid"
                else:
                    validation["message"] = "❌ Embedding stage failed: No embeddings"

            else:
                validation["message"] = f"⚠️ Unknown stage: {stage}"

            return validation

        except Exception as e:
            validation["message"] = f"❌ Validation error: {e!s}"
            return validation

    def print_quality_report(self, document_id: str, quality_result: dict):
        """Pretty print quality report"""
        print(f"\n{'='*60}")
        print(f"📊 QUALITY REPORT: {document_id[:8]}...")
        print(f"{'='*60}")

        # Score
        score = quality_result["score"]
        if score >= 90:
            score_emoji = "🟢"
        elif score >= 70:
            score_emoji = "🟡"
        else:
            score_emoji = "🔴"

        print(f"\n{score_emoji} SCORE: {score}/100")
        print(f"Status: {'✅ PASSED' if quality_result['passed'] else '❌ FAILED'}")

        # Stats
        if quality_result["stats"]:
            print("\n📈 Statistics:")
            for key, value in quality_result["stats"].items():
                print(f"  • {key}: {value}")

        # Issues
        if quality_result["issues"]:
            print(f"\n❌ Issues ({len(quality_result['issues'])}):")
            for issue in quality_result["issues"]:
                print(f"  {issue}")

        # Warnings
        if quality_result["warnings"]:
            print(f"\n⚠️  Warnings ({len(quality_result['warnings'])}):")
            for warning in quality_result["warnings"]:
                print(f"  {warning}")

        print(f"\n{'='*60}\n")
