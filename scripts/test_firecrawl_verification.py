"""
Firecrawl Manufacturer Verification Test Script
================================================
Testet die web-basierte Hersteller-Verifikation mit Firecrawl.

Features:
- Hersteller-Erkennung von Modellnummern
- Modell-Verifikation mit Spezifikationen
- Parts-Discovery
- Hardware-Specs-Extraktion
- Cache-Verhalten

Usage:
    python scripts/test_firecrawl_verification.py --model M454dn
    python scripts/test_firecrawl_verification.py --model E475 --manufacturer HP
    python scripts/test_firecrawl_verification.py --test-all
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

from backend.processors.env_loader import load_all_env_files
from backend.services.database_service import DatabaseService
from backend.services.manufacturer_verification_service import ManufacturerVerificationService
from backend.services.web_scraping_service import create_web_scraping_service
from backend.utils.colored_logging import apply_colored_logging_globally


class FirecrawlVerificationTester:
    """Testet Firecrawl-basierte Hersteller-Verifikation"""

    def __init__(self, enable_cache: bool = True, verbose: bool = False):
        """Initialize tester

        Args:
            enable_cache: Enable result caching
            verbose: Enable verbose logging
        """
        log_level = logging.DEBUG if verbose else logging.INFO
        apply_colored_logging_globally(level=log_level)
        self.logger = logging.getLogger("firecrawl_tester")

        # Load environment
        load_all_env_files(PROJECT_ROOT)

        # Initialize services
        self.database_service = None
        self.web_scraping_service = None
        self.verification_service = None
        self.enable_cache = enable_cache

        self.logger.info("✅ Firecrawl Verification Tester initialized")

    async def initialize_services(self):
        """Initialize required services"""
        self.logger.info("Initializing services...")

        try:
            # Database service (for caching)
            if self.enable_cache:
                self.database_service = DatabaseService()
                await self.database_service.connect()
                self.logger.info("✅ Database service connected (caching enabled)")
            else:
                self.logger.info("ℹ️  Caching disabled - running without database")
        except Exception as e:
            self.logger.warning(f"⚠️  Database service not available: {e}")
            self.database_service = None

        try:
            # Web scraping service (Firecrawl)
            # Use factory function to create service with proper backend selection
            self.web_scraping_service = create_web_scraping_service()
            self.logger.info("✅ Web scraping service initialized")
        except Exception as e:
            self.logger.error(f"❌ Web scraping service failed: {e}")
            raise

        try:
            # Manufacturer verification service
            self.verification_service = ManufacturerVerificationService(
                database_service=self.database_service,
                web_scraping_service=self.web_scraping_service,
                enable_cache=self.enable_cache,
                cache_days=90,
                min_confidence=0.7,
            )
            self.logger.info("✅ Manufacturer verification service initialized")
        except Exception as e:
            self.logger.error(f"❌ Verification service failed: {e}")
            raise

    async def test_manufacturer_verification(self, model_number: str, hints: list[str] = None) -> dict[str, Any]:
        """Test manufacturer verification from model number

        Args:
            model_number: Product model number
            hints: Optional hints (filename, title, etc.)

        Returns:
            Verification result
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info("🔍 Testing Manufacturer Verification")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Model Number: {model_number}")
        if hints:
            self.logger.info(f"Hints: {', '.join(hints)}")

        try:
            result = await self.verification_service.verify_manufacturer(model_number=model_number, hints=hints)

            self.logger.info("\n📊 Results:")
            self.logger.info(f"  Manufacturer: {result.get('manufacturer', 'Not found')}")
            self.logger.info(f"  Confidence: {result.get('confidence', 0.0):.2f}")
            self.logger.info(f"  Source URL: {result.get('source_url', 'N/A')}")
            self.logger.info(f"  Cached: {'Yes' if result.get('cached') else 'No'}")

            if result.get("manufacturer"):
                self.logger.info("✅ Manufacturer detected successfully!")
            else:
                self.logger.warning("⚠️  No manufacturer found")

            return result

        except Exception as e:
            self.logger.error(f"❌ Verification failed: {e}")
            return None

    async def test_model_verification(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """Test model verification with specifications

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            Model verification result
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info("🔍 Testing Model Verification")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Manufacturer: {manufacturer}")
        self.logger.info(f"Model Number: {model_number}")

        try:
            result = await self.verification_service.verify_model(manufacturer=manufacturer, model_number=model_number)

            self.logger.info("\n📊 Results:")
            self.logger.info(f"  Model Exists: {'Yes' if result.get('exists') else 'No'}")
            self.logger.info(f"  Confidence: {result.get('confidence', 0.0):.2f}")
            self.logger.info(f"  Cached: {'Yes' if result.get('cached') else 'No'}")

            specs = result.get("specifications", {})
            if specs:
                self.logger.info("\n  📋 Specifications:")
                for key, value in specs.items():
                    self.logger.info(f"    {key}: {value}")
            else:
                self.logger.info("  No specifications found")

            if result.get("exists"):
                self.logger.info("✅ Model verified successfully!")
            else:
                self.logger.warning("⚠️  Model not found")

            return result

        except Exception as e:
            self.logger.error(f"❌ Model verification failed: {e}")
            return None

    async def test_parts_discovery(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """Test parts and accessories discovery

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            Parts discovery result
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info("🔍 Testing Parts Discovery")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Manufacturer: {manufacturer}")
        self.logger.info(f"Model Number: {model_number}")

        try:
            result = await self.verification_service.discover_parts(
                manufacturer=manufacturer, model_number=model_number
            )

            self.logger.info("\n📊 Results:")
            parts = result.get("parts", [])
            self.logger.info(f"  Parts Found: {len(parts)}")
            self.logger.info(f"  Confidence: {result.get('confidence', 0.0):.2f}")
            self.logger.info(f"  Cached: {'Yes' if result.get('cached') else 'No'}")

            if parts:
                self.logger.info("\n  🔧 Parts List:")
                for i, part in enumerate(parts[:10], 1):  # Show first 10
                    part_num = part.get("part_number", "Unknown")
                    part_type = part.get("type", "unknown")
                    self.logger.info(f"    {i}. {part_num} ({part_type})")

                if len(parts) > 10:
                    self.logger.info(f"    ... and {len(parts) - 10} more")

                self.logger.info("✅ Parts discovered successfully!")
            else:
                self.logger.warning("⚠️  No parts found")

            return result

        except Exception as e:
            self.logger.error(f"❌ Parts discovery failed: {e}")
            return None

    async def test_hardware_specs(self, manufacturer: str, model_number: str) -> dict[str, Any]:
        """Test hardware specifications extraction

        Args:
            manufacturer: Manufacturer name
            model_number: Product model number

        Returns:
            Hardware specs result
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info("🔍 Testing Hardware Specs Extraction")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Manufacturer: {manufacturer}")
        self.logger.info(f"Model Number: {model_number}")

        try:
            result = await self.verification_service.get_hardware_specs(
                manufacturer=manufacturer, model_number=model_number
            )

            self.logger.info("\n📊 Results:")
            specs = result.get("specifications", {})
            self.logger.info(f"  Specs Found: {len(specs)}")
            self.logger.info(f"  Confidence: {result.get('confidence', 0.0):.2f}")
            self.logger.info(f"  Cached: {'Yes' if result.get('cached') else 'No'}")

            if specs:
                self.logger.info("\n  💾 Hardware Specifications:")
                for key, value in specs.items():
                    self.logger.info(f"    {key}: {value}")

                self.logger.info("✅ Hardware specs extracted successfully!")
            else:
                self.logger.warning("⚠️  No hardware specs found")

            return result

        except Exception as e:
            self.logger.error(f"❌ Hardware specs extraction failed: {e}")
            return None

    async def test_complete_workflow(self, model_number: str, manufacturer: str = None) -> dict[str, Any]:
        """Test complete verification workflow

        Args:
            model_number: Product model number
            manufacturer: Optional manufacturer (will be detected if not provided)

        Returns:
            Complete workflow results
        """
        self.logger.info(f"\n{'='*60}")
        self.logger.info("🚀 Testing Complete Verification Workflow")
        self.logger.info(f"{'='*60}")

        results = {
            "model_number": model_number,
            "manufacturer_input": manufacturer,
            "timestamp": datetime.now().isoformat(),
        }

        # Step 1: Detect manufacturer if not provided
        if not manufacturer:
            self.logger.info("\nStep 1: Detecting manufacturer...")
            manufacturer_result = await self.test_manufacturer_verification(model_number)
            results["manufacturer_detection"] = manufacturer_result

            if manufacturer_result and manufacturer_result.get("manufacturer"):
                manufacturer = manufacturer_result["manufacturer"]
                self.logger.info(f"✅ Manufacturer detected: {manufacturer}")
            else:
                self.logger.error("❌ Could not detect manufacturer - stopping workflow")
                return results
        else:
            self.logger.info(f"\nStep 1: Using provided manufacturer: {manufacturer}")
            results["manufacturer_detection"] = {"manufacturer": manufacturer, "provided": True}

        # Step 2: Verify model
        self.logger.info("\nStep 2: Verifying model...")
        model_result = await self.test_model_verification(manufacturer, model_number)
        results["model_verification"] = model_result

        # Step 3: Discover parts
        self.logger.info("\nStep 3: Discovering parts...")
        parts_result = await self.test_parts_discovery(manufacturer, model_number)
        results["parts_discovery"] = parts_result

        # Step 4: Extract hardware specs
        self.logger.info("\nStep 4: Extracting hardware specs...")
        specs_result = await self.test_hardware_specs(manufacturer, model_number)
        results["hardware_specs"] = specs_result

        # Summary
        self.logger.info(f"\n{'='*60}")
        self.logger.info("📊 Workflow Summary")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"Model: {model_number}")
        self.logger.info(f"Manufacturer: {manufacturer}")
        self.logger.info(f"Model Exists: {model_result.get('exists', False) if model_result else False}")
        self.logger.info(f"Parts Found: {len(parts_result.get('parts', [])) if parts_result else 0}")
        self.logger.info(f"Specs Found: {len(specs_result.get('specifications', {})) if specs_result else 0}")

        return results

    async def cleanup(self):
        """Cleanup resources"""
        if self.database_service:
            try:
                await self.database_service.disconnect()
                self.logger.info("✅ Database disconnected")
            except Exception as e:
                self.logger.warning(f"⚠️  Database disconnect error: {e}")


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test Firecrawl-based manufacturer verification")
    parser.add_argument("--model", type=str, help="Model number to verify (e.g., M454dn, E475, C759)")
    parser.add_argument(
        "--manufacturer", type=str, help="Manufacturer name (optional, will be detected if not provided)"
    )
    parser.add_argument("--hints", type=str, nargs="+", help="Hints for manufacturer detection (e.g., HP LaserJet)")
    parser.add_argument(
        "--test-all", action="store_true", help="Run all verification tests (manufacturer, model, parts, specs)"
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable result caching")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--output", type=str, help="Save results to JSON file")

    args = parser.parse_args()

    # Validate arguments
    if not args.model and not args.test_all:
        parser.error("Either --model or --test-all is required")

    # Initialize tester
    tester = FirecrawlVerificationTester(enable_cache=not args.no_cache, verbose=args.verbose)

    try:
        await tester.initialize_services()

        results = None

        if args.test_all:
            # Run complete workflow with predefined test cases
            test_cases = [
                {"model": "M454dn", "manufacturer": "HP Inc."},
                {"model": "E475", "manufacturer": None},  # Will detect HP
                {"model": "C759", "manufacturer": "Konica Minolta"},
            ]

            all_results = []
            for test_case in test_cases:
                result = await tester.test_complete_workflow(
                    model_number=test_case["model"], manufacturer=test_case.get("manufacturer")
                )
                all_results.append(result)

            results = {"test_mode": "all", "test_cases": all_results, "timestamp": datetime.now().isoformat()}

        elif args.model:
            if args.manufacturer:
                # Full workflow with provided manufacturer
                results = await tester.test_complete_workflow(model_number=args.model, manufacturer=args.manufacturer)
            else:
                # Just manufacturer detection
                results = await tester.test_manufacturer_verification(model_number=args.model, hints=args.hints)

        # Save results if requested
        if args.output and results:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            tester.logger.info(f"\n💾 Results saved to: {output_path}")

    except KeyboardInterrupt:
        tester.logger.info("\n⚠️  Test interrupted by user")
    except Exception as e:
        tester.logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return 1
    finally:
        await tester.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
