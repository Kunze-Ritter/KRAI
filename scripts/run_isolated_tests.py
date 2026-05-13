#!/usr/bin/env python3
"""
KRAI Test Runner - Dedicated Test Environment

This script manages the complete test lifecycle including:
- Environment setup and teardown
- Test execution in isolation
- Result reporting and cleanup
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class TestRunner:
    """Manage test environment and execution"""

    def __init__(self):
        self.test_env_file = Path(".env.test")
        self.docker_compose_test = Path("docker-compose.test.yml")
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)

    def check_prerequisites(self):
        """Check if test environment prerequisites are met"""
        logger.info("🔍 Checking test environment prerequisites...")

        prerequisites = {
            "docker_compose_test": self.docker_compose_test.exists(),
            "test_env_file": self.test_env_file.exists(),
            "docker_available": self._check_docker(),
            "docker_compose_available": self._check_docker_compose(),
        }

        missing = [k for k, v in prerequisites.items() if not v]

        if missing:
            logger.error(f"❌ Missing prerequisites: {missing}")
            return False

        logger.info("✅ All prerequisites met")
        return True

    def _check_docker(self):
        """Check if Docker is available"""
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    def _check_docker_compose(self):
        """Check if Docker Compose is available"""
        try:
            result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False

    async def start_test_environment(self):
        """Start the test environment"""
        logger.info("🚀 Starting test environment...")

        try:
            # Start core services
            cmd = ["docker-compose", "-f", str(self.docker_compose_test), "up", "-d"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"❌ Failed to start test environment: {result.stderr}")
                return False

            logger.info("⏳ Waiting for services to be ready...")
            await asyncio.sleep(30)

            # Setup test environment
            setup_cmd = ["docker-compose", "-f", str(self.docker_compose_test), "run", "--rm", "test-setup"]
            result = subprocess.run(setup_cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"❌ Test environment setup failed: {result.stderr}")
                return False

            logger.info("✅ Test environment started and ready")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to start test environment: {e}")
            return False

    async def stop_test_environment(self):
        """Stop the test environment"""
        logger.info("⏹️ Stopping test environment...")

        try:
            # Cleanup test data
            cleanup_cmd = ["docker-compose", "-f", str(self.docker_compose_test), "run", "--rm", "test-cleanup"]
            subprocess.run(cleanup_cmd, capture_output=True, text=True)

            # Stop services
            cmd = ["docker-compose", "-f", str(self.docker_compose_test), "down", "-v"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode != 0:
                logger.warning(f"⚠️ Issues stopping test environment: {result.stderr}")
            else:
                logger.info("✅ Test environment stopped")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to stop test environment: {e}")
            return False

    async def run_unit_tests(self):
        """Run unit tests in test environment"""
        logger.info("🧪 Running unit tests...")

        try:
            cmd = [
                "docker-compose",
                "-f",
                str(self.docker_compose_test),
                "run",
                "--rm",
                "-e",
                "TESTING=true",
                "python",
                "-m",
                "pytest",
                "tests/unit/",
                "-v",
                "--tb=short",
                "--cov=backend",
                "--cov-report=html:test_results/coverage_unit",
                "--junit-xml=test_results/unit_results.xml",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Save results
            results = {
                "test_type": "unit",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat(),
            }

            with open(self.results_dir / "unit_test_results.json", "w") as f:
                json.dump(results, f, indent=2)

            success = result.returncode == 0
            if success:
                logger.info("✅ Unit tests completed successfully")
            else:
                logger.error("❌ Unit tests failed")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to run unit tests: {e}")
            return False

    async def run_integration_tests(self):
        """Run integration tests in test environment"""
        logger.info("🔗 Running integration tests...")

        try:
            cmd = [
                "docker-compose",
                "-f",
                str(self.docker_compose_test),
                "run",
                "--rm",
                "-e",
                "TESTING=true",
                "python",
                "-m",
                "pytest",
                "tests/integration/",
                "-v",
                "--tb=short",
                "--cov=backend",
                "--cov-report=html:test_results/coverage_integration",
                "--junit-xml=test_results/integration_results.xml",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Save results
            results = {
                "test_type": "integration",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat(),
            }

            with open(self.results_dir / "integration_test_results.json", "w") as f:
                json.dump(results, f, indent=2)

            success = result.returncode == 0
            if success:
                logger.info("✅ Integration tests completed successfully")
            else:
                logger.error("❌ Integration tests failed")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to run integration tests: {e}")
            return False

    async def run_pipeline_tests(self):
        """Run pipeline tests in test environment"""
        logger.info("🔄 Running pipeline tests...")

        try:
            cmd = [
                "docker-compose",
                "-f",
                str(self.docker_compose_test),
                "run",
                "--rm",
                "-e",
                "TESTING=true",
                "python",
                "scripts/test_full_pipeline_phases_1_6.py",
                "--verbose",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Save results
            results = {
                "test_type": "pipeline",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat(),
            }

            with open(self.results_dir / "pipeline_test_results.json", "w") as f:
                json.dump(results, f, indent=2)

            success = result.returncode == 0
            if success:
                logger.info("✅ Pipeline tests completed successfully")
            else:
                logger.error("❌ Pipeline tests failed")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to run pipeline tests: {e}")
            return False

    async def run_performance_tests(self):
        """Run performance tests in test environment"""
        logger.info("⚡ Running performance tests...")

        try:
            cmd = [
                "docker-compose",
                "-f",
                str(self.docker_compose_test),
                "run",
                "--rm",
                "-e",
                "TESTING=true",
                "python",
                "tests/performance/database_performance_test.py",
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Save results
            results = {
                "test_type": "performance",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat(),
            }

            with open(self.results_dir / "performance_test_results.json", "w") as f:
                json.dump(results, f, indent=2)

            success = result.returncode == 0
            if success:
                logger.info("✅ Performance tests completed successfully")
            else:
                logger.error("❌ Performance tests failed")

            return success

        except Exception as e:
            logger.error(f"❌ Failed to run performance tests: {e}")
            return False

    def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating test report...")

        try:
            report = {
                "test_run": {
                    "timestamp": datetime.now().isoformat(),
                    "environment": "isolated_test",
                    "docker_compose_file": str(self.docker_compose_test),
                },
                "results": {},
            }

            # Collect all test results
            result_files = list(self.results_dir.glob("*_results.json"))

            for result_file in result_files:
                with open(result_file) as f:
                    data = json.load(f)
                    report["results"][data["test_type"]] = {
                        "success": data["return_code"] == 0,
                        "timestamp": data["timestamp"],
                    }

            # Calculate summary
            total_tests = len(report["results"])
            successful_tests = sum(1 for r in report["results"].values() if r["success"])

            report["summary"] = {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": total_tests - successful_tests,
                "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
            }

            # Save report
            report_file = self.results_dir / "test_report.json"
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2)

            logger.info(f"📊 Test report saved to: {report_file}")
            logger.info(
                f"📊 Summary: {successful_tests}/{total_tests} tests passed ({report['summary']['success_rate']:.1f}%)"
            )

            return report

        except Exception as e:
            logger.error(f"❌ Failed to generate test report: {e}")
            return None

    async def run_test_suite(self, test_types=None):
        """Run specified test suite"""
        if test_types is None:
            test_types = ["unit", "integration", "pipeline"]

        logger.info(f"🚀 Running test suite: {test_types}")

        # Check prerequisites
        if not self.check_prerequisites():
            return False

        # Start test environment
        if not await self.start_test_environment():
            return False

        try:
            results = {}

            # Run tests based on specified types
            if "unit" in test_types:
                results["unit"] = await self.run_unit_tests()

            if "integration" in test_types:
                results["integration"] = await self.run_integration_tests()

            if "pipeline" in test_types:
                results["pipeline"] = await self.run_pipeline_tests()

            if "performance" in test_types:
                results["performance"] = await self.run_performance_tests()

            # Generate report
            report = self.generate_test_report()

            # Overall success
            overall_success = all(results.values())

            if overall_success:
                logger.info("🎉 All tests completed successfully!")
            else:
                failed_tests = [k for k, v in results.items() if not v]
                logger.error(f"❌ Some tests failed: {failed_tests}")

            return overall_success

        finally:
            # Always cleanup
            await self.stop_test_environment()


async def main():
    """Main test runner function"""
    parser = argparse.ArgumentParser(description="KRAI Test Runner - Isolated Test Environment")
    parser.add_argument(
        "--tests",
        nargs="+",
        choices=["unit", "integration", "pipeline", "performance"],
        default=["unit", "integration", "pipeline"],
        help="Test types to run",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = TestRunner()

    try:
        success = await runner.run_test_suite(args.tests)

        if success:
            logger.info("🎉 Test suite completed successfully!")
            sys.exit(0)
        else:
            logger.error("❌ Test suite failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("⏹️ Test suite interrupted by user")
        await runner.stop_test_environment()
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error during test suite: {e}")
        await runner.stop_test_environment()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
