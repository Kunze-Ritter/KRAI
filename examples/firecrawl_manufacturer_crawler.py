#!/usr/bin/env python3
"""
Manufacturer crawler example demonstrating scheduled crawling and monitoring.

Purpose: Show how to set up and manage periodic manufacturer website crawling for new documents and error codes

Usage Examples:
    # Create crawl schedule
    python examples/firecrawl_manufacturer_crawler.py --create-schedule \
      --manufacturer "Konica Minolta" --crawl-type support_pages \
      --schedule "0 2 * * 0"

    # Start manual crawl
    python examples/firecrawl_manufacturer_crawler.py --start-crawl schedule-id

    # Show statistics
    python examples/firecrawl_manufacturer_crawler.py --stats
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.web_scraping_service import WebScrapingService, create_web_scraping_service

try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Rich library not available. Install with: pip install rich")
    print("Falling back to basic console output")

console = Console() if RICH_AVAILABLE else None


def print_with_rich(content):
    """Print using rich if available, otherwise regular print."""
    if RICH_AVAILABLE and console:
        console.print(content)
    else:
        print(content)


def load_crawler_configuration() -> dict[str, str]:
    """Load manufacturer crawler configuration from environment variables."""
    config = {
        "enable_manufacturer_crawling": os.getenv("ENABLE_MANUFACTURER_CRAWLING", "false").lower() == "true",
        "crawler_max_concurrent_jobs": int(os.getenv("CRAWLER_MAX_CONCURRENT_JOBS", "1")),
        "crawler_default_max_pages": int(os.getenv("CRAWLER_DEFAULT_MAX_PAGES", "100")),
        "crawler_default_max_depth": int(os.getenv("CRAWLER_DEFAULT_MAX_DEPTH", "2")),
        "backend": os.getenv("SCRAPING_BACKEND", "firecrawl"),
        "firecrawl_api_url": os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"),
    }

    # Display configuration summary
    if RICH_AVAILABLE and console:
        config_table = Table(title="🔧 Manufacturer Crawler Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")

        for key, value in config.items():
            status_style = (
                "green"
                if (key == "enable_manufacturer_crawling" and value)
                else "yellow"
                if key == "enable_manufacturer_crawling"
                else "white"
            )
            config_table.add_row(key.replace("_", " ").title(), str(value), style=status_style)

        console.print(config_table)

        if not config["enable_manufacturer_crawling"]:
            warning_panel = Panel(
                "⚠️ **Manufacturer Crawling Disabled**\n"
                "💡 Set ENABLE_MANUFACTURER_CRAWLING=true in your .env file\n"
                "🔧 This example will work but won't affect real data",
                title="Configuration Warning",
                border_style="yellow",
            )
            console.print(warning_panel)
    else:
        print("=== Manufacturer Crawler Configuration ===")
        for key, value in config.items():
            print(f"{key.replace('_', ' ').title()}: {value}")

        if not config["enable_manufacturer_crawling"]:
            print("\n⚠️ Manufacturer Crawling Disabled")
            print("💡 Set ENABLE_MANUFACTURER_CRAWLING=true in your .env file")
            print("🔧 This example will work but won't affect real data")
        print()

    return config


def get_manufacturer_template(manufacturer: str) -> dict[str, Any]:
    """Get pre-configured crawl settings for common manufacturers."""
    templates = {
        "Konica Minolta": {
            "name": "Konica Minolta",
            "base_url": "https://kmbs.konicaminolta.us",
            "products_url": "https://kmbs.konicaminolta.us/products/",
            "support_url": "https://kmbs.konicaminolta.us/support/",
            "url_patterns": [r".*bizhub.*", r".*accurio.*", r".*product.*", r".*support.*"],
            "exclude_patterns": [r".*login.*", r".*cart.*", r".*checkout.*"],
            "recommended_schedule": "0 2 * * 0",  # Weekly Sunday 2am
            "recommended_max_pages": 100,
            "recommended_max_depth": 2,
        },
        "HP": {
            "name": "HP",
            "base_url": "https://support.hp.com",
            "products_url": "https://www.hp.com/us-en/printers/",
            "support_url": "https://support.hp.com/us-en/products/",
            "url_patterns": [r".*laserjet.*", r".*officejet.*", r".*product.*", r".*support.*"],
            "exclude_patterns": [r".*login.*", r".*cart.*", r".*store.*"],
            "recommended_schedule": "0 3 * * 1",  # Weekly Monday 3am
            "recommended_max_pages": 150,
            "recommended_max_depth": 2,
        },
        "Canon": {
            "name": "Canon",
            "base_url": "https://www.usa.canon.com",
            "products_url": "https://www.usa.canon.com/products/",
            "support_url": "https://www.usa.canon.com/support/",
            "url_patterns": [r".*imagerunner.*", r".*imageclass.*", r".*product.*", r".*support.*"],
            "exclude_patterns": [r".*login.*", r".*cart.*", r".*shop.*"],
            "recommended_schedule": "0 4 * * 2",  # Weekly Tuesday 4am
            "recommended_max_pages": 120,
            "recommended_max_depth": 2,
        },
        "Lexmark": {
            "name": "Lexmark",
            "base_url": "https://support.lexmark.com",
            "products_url": "https://www.lexmark.com/us_en/products/",
            "support_url": "https://support.lexmark.com/",
            "url_patterns": [r".*product.*", r".*support.*", r".*manual.*"],
            "exclude_patterns": [r".*login.*", r".*cart.*"],
            "recommended_schedule": "0 5 * * 3",  # Weekly Wednesday 5am
            "recommended_max_pages": 80,
            "recommended_max_depth": 2,
        },
    }

    return templates.get(manufacturer, {})


class MockManufacturerCrawler:
    """Mock manufacturer crawler service for demonstration purposes."""

    def __init__(self, scraping_service: WebScrapingService):
        self.scraping_service = scraping_service
        self.logger = __import__("logging").getLogger("krai.mock.manufacturer_crawler")

        # Mock data storage
        self.schedules = {}
        self.jobs = {}
        self.crawl_results = {}

    async def create_crawl_schedule(self, manufacturer_id: str, crawl_config: dict[str, Any]) -> dict[str, Any]:
        """Create a crawl schedule for a manufacturer."""
        schedule_id = str(uuid.uuid4())

        schedule = {
            "id": schedule_id,
            "manufacturer_id": manufacturer_id,
            "crawl_type": crawl_config.get("crawl_type", "full_site"),
            "start_url": crawl_config.get("start_url"),
            "url_patterns": crawl_config.get("url_patterns", []),
            "exclude_patterns": crawl_config.get("exclude_patterns", []),
            "max_depth": crawl_config.get("max_depth", 2),
            "max_pages": crawl_config.get("max_pages", 100),
            "schedule_cron": crawl_config.get("schedule_cron", "0 2 * * 0"),
            "enabled": True,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "next_run": self._calculate_next_run(crawl_config.get("schedule_cron", "0 2 * * 0")),
        }

        self.schedules[schedule_id] = schedule

        print_with_rich(f"✅ Created crawl schedule: {schedule_id}")
        print_with_rich(f"🏭 Manufacturer: {manufacturer_id}")
        print_with_rich(f"📋 Type: {schedule['crawl_type']}")
        print_with_rich(f"🌐 Start URL: {schedule['start_url']}")
        print_with_rich(f"⏰ Schedule: {schedule['schedule_cron']}")
        print_with_rich(f"📊 Next run: {schedule['next_run']}")

        return {"success": True, "schedule_id": schedule_id, "schedule": schedule}

    async def start_crawl_job(self, schedule_id: str) -> dict[str, Any]:
        """Start a manual crawl job for a schedule."""
        if schedule_id not in self.schedules:
            return {"success": False, "error": f"Schedule not found: {schedule_id}"}

        schedule = self.schedules[schedule_id]
        job_id = str(uuid.uuid4())

        job = {
            "id": job_id,
            "schedule_id": schedule_id,
            "status": "queued",
            "started_at": None,
            "completed_at": None,
            "duration": 0,
            "pages_discovered": 0,
            "pages_scraped": 0,
            "pages_failed": 0,
            "created_at": datetime.now().isoformat(),
        }

        self.jobs[job_id] = job

        print_with_rich(f"🚀 Started crawl job: {job_id}")
        print_with_rich(f"📋 Schedule: {schedule_id}")
        print_with_rich(f"🏭 Manufacturer: {schedule['manufacturer_id']}")
        print_with_rich(f"🌐 URL: {schedule['start_url']}")
        print_with_rich(f"📊 Status: {job['status']}")

        return {"success": True, "job_id": job_id, "job": job}

    async def execute_crawl_job(self, job_id: str) -> dict[str, Any]:
        """Execute a crawl job with real-time progress."""
        if job_id not in self.jobs:
            return {"success": False, "error": f"Job not found: {job_id}"}

        job = self.jobs[job_id]
        schedule = self.schedules.get(job["schedule_id"], {})

        # Update job status
        job["status"] = "running"
        job["started_at"] = datetime.now().isoformat()

        print_with_rich(f"🕷️ Executing crawl job: {job_id}")
        print_with_rich(f"🌐 Crawling: {schedule.get('start_url', 'Unknown URL')}")

        # Simulate crawl progress
        max_pages = schedule.get("max_pages", 100)
        start_time = time.time()

        if RICH_AVAILABLE and console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Crawling pages...", total=max_pages)

                # Simulate crawling progress
                for i in range(max_pages):
                    await asyncio.sleep(0.05)  # Simulate crawl time
                    progress.update(task, advance=1)

                    # Update job progress periodically
                    if i % 10 == 0:
                        job["pages_discovered"] = i + 1
                        job["pages_scraped"] = i  # Some might fail

        else:
            print("🕷️ Crawling pages...")
            for i in range(max_pages):
                await asyncio.sleep(0.05)
                if i % 20 == 0:
                    print(f"  📄 Processed {i}/{max_pages} pages")

            job["pages_discovered"] = max_pages
            job["pages_scraped"] = int(max_pages * 0.95)  # Simulate 95% success rate
            job["pages_failed"] = max_pages - job["pages_scraped"]

        # Complete job
        duration = time.time() - start_time
        job["status"] = "completed"
        job["completed_at"] = datetime.now().isoformat()
        job["duration"] = duration
        job["pages_discovered"] = max_pages
        job["pages_scraped"] = int(max_pages * 0.95)
        job["pages_failed"] = max_pages - job["pages_scraped"]

        # Store mock crawl results
        self.crawl_results[job_id] = {
            "job_id": job_id,
            "pages": [
                {
                    "url": f'{schedule.get("start_url")}/page{i}',
                    "title": f"Page {i}",
                    "content": f"Content for page {i}",
                    "depth": 1,
                    "page_type": "product" if i % 3 == 0 else "support",
                }
                for i in range(job["pages_scraped"])
            ],
        }

        # Display crawl summary
        if RICH_AVAILABLE and console:
            summary_panel = Panel(
                f"✅ **Crawl Job Complete**\n"
                f"🆔 Job ID: {job_id}\n"
                f"📄 Pages Discovered: {job['pages_discovered']}\n"
                f"✅ Pages Scraped: {job['pages_scraped']}\n"
                f"❌ Pages Failed: {job['pages_failed']}\n"
                f"⏱️ Duration: {duration:.2f}s\n"
                f"📊 Success Rate: {(job['pages_scraped']/job['pages_discovered']*100):.1f}%",
                title="Crawl Summary",
                border_style="green",
            )
            console.print(summary_panel)
        else:
            print("\n✅ Crawl Job Complete!")
            print(f"🆔 Job ID: {job_id}")
            print(f"📄 Pages Discovered: {job['pages_discovered']}")
            print(f"✅ Pages Scraped: {job['pages_scraped']}")
            print(f"❌ Pages Failed: {job['pages_failed']}")
            print(f"⏱️ Duration: {duration:.2f}s")
            print(f"📊 Success Rate: {(job['pages_scraped']/job['pages_discovered']*100):.1f}%")

        return {"success": True, "job_id": job_id, "job": job, "duration": duration}

    async def process_crawled_pages(self, job_id: str) -> dict[str, Any]:
        """Process crawled pages with structured extraction."""
        if job_id not in self.crawl_results:
            return {"success": False, "error": f"No crawl results found for job: {job_id}"}

        crawl_data = self.crawl_results[job_id]
        pages = crawl_data["pages"]

        print_with_rich(f"🔍 Processing {len(pages)} crawled pages from job: {job_id}")

        # Simulate processing
        processing_results = {
            "product_specs_extracted": 0,
            "error_codes_found": 0,
            "service_manuals_discovered": 0,
            "parts_catalogs_identified": 0,
        }

        for page in pages:
            page_type = page.get("page_type", "other")

            if page_type == "product":
                processing_results["product_specs_extracted"] += 1
            elif page_type == "support":
                processing_results["error_codes_found"] += 2  # Mock: 2 error codes per support page
                processing_results["service_manuals_discovered"] += 1

        # Display processing results
        if RICH_AVAILABLE and console:
            processing_panel = Panel(
                f"✅ **Page Processing Complete**\n"
                f"📄 Pages Processed: {len(pages)}\n"
                f"🏭 Product Specs: {processing_results['product_specs_extracted']}\n"
                f"⚠️ Error Codes: {processing_results['error_codes_found']}\n"
                f"📚 Service Manuals: {processing_results['service_manuals_discovered']}\n"
                f"🔧 Parts Catalogs: {processing_results['parts_catalogs_identified']}",
                title="Processing Results",
                border_style="green",
            )
            console.print(processing_panel)
        else:
            print("\n✅ Page Processing Complete!")
            print(f"📄 Pages Processed: {len(pages)}")
            print(f"🏭 Product Specs: {processing_results['product_specs_extracted']}")
            print(f"⚠️ Error Codes: {processing_results['error_codes_found']}")
            print(f"📚 Service Manuals: {processing_results['service_manuals_discovered']}")
            print(f"🔧 Parts Catalogs: {processing_results['parts_catalogs_identified']}")

        return {"success": True, "job_id": job_id, "pages_processed": len(pages), "extractions": processing_results}

    async def list_crawl_schedules(self, manufacturer_id: str | None = None) -> dict[str, Any]:
        """List all crawl schedules."""
        schedules = list(self.schedules.values())

        if manufacturer_id:
            schedules = [s for s in schedules if s["manufacturer_id"] == manufacturer_id]

        print_with_rich(f"📋 Found {len(schedules)} crawl schedules")

        if RICH_AVAILABLE and console and schedules:
            schedule_table = Table(title="📋 Crawl Schedules")
            schedule_table.add_column("Schedule ID", style="cyan")
            schedule_table.add_column("Manufacturer", style="green")
            schedule_table.add_column("Type", style="white")
            schedule_table.add_column("Schedule", style="yellow")
            schedule_table.add_column("Next Run", style="blue")
            schedule_table.add_column("Enabled", style="red")

            for schedule in schedules:
                schedule_table.add_row(
                    schedule["id"][:8] + "...",
                    schedule["manufacturer_id"],
                    schedule["crawl_type"],
                    schedule["schedule_cron"],
                    schedule["next_run"] or "Never",
                    "✅" if schedule["enabled"] else "❌",
                )

            console.print(schedule_table)
        elif schedules:
            print("\n=== Crawl Schedules ===")
            for schedule in schedules:
                enabled = "✅" if schedule["enabled"] else "❌"
                print(
                    f"{schedule['id'][:8]}... | {schedule['manufacturer_id']} | {schedule['crawl_type']} | {schedule['schedule_cron']} | {enabled}"
                )

        return {"success": True, "schedules": schedules, "total": len(schedules)}

    async def list_crawl_jobs(self, schedule_id: str | None = None, limit: int = 10) -> dict[str, Any]:
        """List crawl jobs with history."""
        jobs = list(self.jobs.values())

        if schedule_id:
            jobs = [j for j in jobs if j["schedule_id"] == schedule_id]

        # Sort by created_at (newest first)
        jobs.sort(key=lambda x: x["created_at"], reverse=True)
        jobs = jobs[:limit]

        print_with_rich(f"📊 Found {len(jobs)} crawl jobs")

        if RICH_AVAILABLE and console and jobs:
            job_table = Table(title="📊 Crawl Job History")
            job_table.add_column("Job ID", style="cyan")
            job_table.add_column("Schedule", style="green")
            job_table.add_column("Status", style="white")
            job_table.add_column("Started", style="yellow")
            job_table.add_column("Duration", style="blue")
            job_table.add_column("Pages", style="red")
            job_table.add_column("Success Rate", style="green")

            for job in jobs:
                status_icon = {"queued": "⏳", "running": "🏃", "completed": "✅", "failed": "❌"}.get(
                    job["status"], "❓"
                )

                duration = f"{job['duration']:.1f}s" if job["duration"] > 0 else "N/A"
                pages = f"{job['pages_scraped']}/{job['pages_discovered']}"
                success_rate = (
                    f"{(job['pages_scraped']/job['pages_discovered']*100):.1f}%"
                    if job["pages_discovered"] > 0
                    else "N/A"
                )

                job_table.add_row(
                    job["id"][:8] + "...",
                    job["schedule_id"][:8] + "...",
                    f"{status_icon} {job['status']}",
                    job["started_at"][:10] if job["started_at"] else "N/A",
                    duration,
                    pages,
                    success_rate,
                )

            console.print(job_table)
        elif jobs:
            print("\n=== Crawl Job History ===")
            for job in jobs:
                status_icon = {"queued": "⏳", "running": "🏃", "completed": "✅", "failed": "❌"}.get(
                    job["status"], "❓"
                )
                duration = f"{job['duration']:.1f}s" if job["duration"] > 0 else "N/A"
                pages = f"{job['pages_scraped']}/{job['pages_discovered']}"
                print(f"{job['id'][:8]}... | {status_icon} {job['status']} | {duration} | {pages}")

        return {"success": True, "jobs": jobs, "total": len(jobs)}

    async def get_crawler_stats(self) -> dict[str, Any]:
        """Get crawler statistics."""
        schedules = list(self.schedules.values())
        jobs = list(self.jobs.values())

        active_schedules = sum(1 for s in schedules if s["enabled"])
        completed_jobs = sum(1 for j in jobs if j["status"] == "completed")
        running_jobs = sum(1 for j in jobs if j["status"] == "running")
        failed_jobs = sum(1 for j in jobs if j["status"] == "failed")

        total_pages_crawled = sum(j["pages_scraped"] for j in jobs if j["status"] == "completed")
        total_duration = sum(j["duration"] for j in jobs if j["status"] == "completed")

        stats = {
            "total_schedules": len(schedules),
            "active_schedules": active_schedules,
            "total_jobs": len(jobs),
            "completed_jobs": completed_jobs,
            "running_jobs": running_jobs,
            "failed_jobs": failed_jobs,
            "total_pages_crawled": total_pages_crawled,
            "total_duration": total_duration,
            "average_pages_per_job": total_pages_crawled / max(completed_jobs, 1),
            "average_duration": total_duration / max(completed_jobs, 1),
        }

        # Display statistics
        if RICH_AVAILABLE and console:
            stats_table = Table(title="📊 Crawler Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="green")

            stats_table.add_row("Total Schedules", str(stats["total_schedules"]))
            stats_table.add_row("Active Schedules", str(stats["active_schedules"]))
            stats_table.add_row("Total Jobs", str(stats["total_jobs"]))
            stats_table.add_row("Completed Jobs", str(stats["completed_jobs"]))
            stats_table.add_row("Running Jobs", str(stats["running_jobs"]))
            stats_table.add_row("Failed Jobs", str(stats["failed_jobs"]))
            stats_table.add_row("Total Pages Crawled", str(stats["total_pages_crawled"]))
            stats_table.add_row("Total Duration", f"{stats['total_duration']:.1f}s")
            stats_table.add_row("Avg Pages per Job", f"{stats['average_pages_per_job']:.1f}")
            stats_table.add_row("Avg Duration", f"{stats['average_duration']:.1f}s")

            console.print(stats_table)
        else:
            print("=== Crawler Statistics ===")
            print(f"Total Schedules: {stats['total_schedules']}")
            print(f"Active Schedules: {stats['active_schedules']}")
            print(f"Total Jobs: {stats['total_jobs']}")
            print(f"Completed Jobs: {stats['completed_jobs']}")
            print(f"Running Jobs: {stats['running_jobs']}")
            print(f"Failed Jobs: {stats['failed_jobs']}")
            print(f"Total Pages Crawled: {stats['total_pages_crawled']}")
            print(f"Total Duration: {stats['total_duration']:.1f}s")
            print(f"Avg Pages per Job: {stats['average_pages_per_job']:.1f}")
            print(f"Avg Duration: {stats['average_duration']:.1f}s")

        return stats

    async def check_scheduled_crawls(self) -> dict[str, Any]:
        """Check for scheduled crawls that are due to run."""
        now = datetime.now()
        due_schedules = []

        for schedule in self.schedules.values():
            if not schedule["enabled"]:
                continue

            # Simple check - in real implementation would parse cron expression
            # For demo, we'll just check if next_run is in the past
            if schedule["next_run"]:
                next_run_time = datetime.fromisoformat(schedule["next_run"].replace("Z", "+00:00"))
                if next_run_time <= now:
                    due_schedules.append(schedule)

        print_with_rich(f"⏰ Found {len(due_schedules)} schedules due to run")

        # Start crawl jobs for due schedules
        started_jobs = []
        for schedule in due_schedules:
            job_result = await self.start_crawl_job(schedule["id"])
            if job_result.get("success"):
                started_jobs.append(job_result["job_id"])

        if RICH_AVAILABLE and console:
            check_panel = Panel(
                f"✅ **Scheduled Crawl Check Complete**\n"
                f"⏰ Due Schedules: {len(due_schedules)}\n"
                f"🚀 Jobs Started: {len(started_jobs)}\n"
                f"📊 Job IDs: {', '.join([j[:8] + '...' for j in started_jobs])}",
                title="Scheduled Check Results",
                border_style="green" if due_schedules else "blue",
            )
            console.print(check_panel)
        else:
            print("\n✅ Scheduled Crawl Check Complete!")
            print(f"⏰ Due Schedules: {len(due_schedules)}")
            print(f"🚀 Jobs Started: {len(started_jobs)}")
            if started_jobs:
                print(f"📊 Job IDs: {', '.join([j[:8] + '...' for j in started_jobs])}")

        return {
            "success": True,
            "due_schedules": len(due_schedules),
            "started_jobs": len(started_jobs),
            "job_ids": started_jobs,
        }

    def _calculate_next_run(self, cron_expression: str) -> str:
        """Calculate next run time from cron expression (simplified)."""
        # For demo, just return tomorrow at 2am
        tomorrow = datetime.now() + timedelta(days=1)
        tomorrow = tomorrow.replace(hour=2, minute=0, second=0, microsecond=0)
        return tomorrow.isoformat()


def validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression format."""
    # Simple validation - should have 5 parts
    parts = cron_expr.split()
    if len(parts) != 5:
        return False

    # Basic pattern check
    for part in parts:
        if part == "*":
            continue
        if part.isdigit():
            continue
        if "*/" in part:
            try:
                int(part.split("/")[1])
                continue
            except (ValueError, IndexError):
                return False
        return False

    return True


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Manufacturer crawler example demonstrating scheduled crawling and monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --create-schedule --manufacturer "Konica Minolta" --crawl-type support_pages --schedule "0 2 * * 0"
  %(prog)s --start-crawl schedule-id
  %(prog)s --job-id job-id
  %(prog)s --process-pages job-id
  %(prog)s --list-schedules
  %(prog)s --history schedule-id
  %(prog)s --stats
  %(prog)s --check-scheduled
        """,
    )

    # Operation options
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument("--create-schedule", action="store_true", help="Create new crawl schedule")
    operation_group.add_argument("--start-crawl", type=str, help="Start manual crawl for schedule ID")
    operation_group.add_argument("--job-id", type=str, help="Monitor crawl job ID")
    operation_group.add_argument("--process-pages", type=str, help="Process crawled pages for job ID")
    operation_group.add_argument("--list-schedules", action="store_true", help="List all schedules")
    operation_group.add_argument("--history", type=str, help="View crawl history for schedule ID")
    operation_group.add_argument("--stats", action="store_true", help="Show crawler statistics")
    operation_group.add_argument("--check-scheduled", action="store_true", help="Check and run scheduled crawls")

    # Schedule creation options
    parser.add_argument(
        "--manufacturer", type=str, choices=["Konica Minolta", "HP", "Canon", "Lexmark"], help="Manufacturer name"
    )

    parser.add_argument(
        "--crawl-type",
        choices=["full_site", "product_pages", "support_pages", "error_codes", "manuals"],
        default="support_pages",
        help="Type of crawl (default: support_pages)",
    )

    parser.add_argument("--start-url", type=str, help="Start URL for crawl")

    parser.add_argument(
        "--schedule", type=str, default="0 2 * * 0", help='Cron expression (default: "0 2 * * 0" - weekly Sunday 2am)'
    )

    parser.add_argument("--max-pages", type=int, default=100, help="Maximum pages to crawl (default: 100)")

    parser.add_argument("--max-depth", type=int, default=2, help="Maximum crawl depth (default: 2)")

    args = parser.parse_args()

    # Validate arguments
    if args.create_schedule:
        if not args.manufacturer:
            parser.error("--manufacturer is required when creating schedule")

        if not validate_cron_expression(args.schedule):
            parser.error(f"Invalid cron expression: {args.schedule}")

    # Load configuration
    config = load_crawler_configuration()

    # Run the requested operation
    async def run_operation():
        # Create services
        scraping_service = create_web_scraping_service(backend=config["backend"])
        crawler = MockManufacturerCrawler(scraping_service)

        if args.create_schedule:
            # Create crawl schedule
            template = get_manufacturer_template(args.manufacturer)
            if not template:
                return {"success": False, "error": f"Unknown manufacturer: {args.manufacturer}"}

            # Determine start URL
            start_url = args.start_url
            if not start_url:
                if args.crawl_type in ["product_pages", "full_site"]:
                    start_url = template["products_url"]
                else:
                    start_url = template["support_url"]

            # Build crawl configuration
            crawl_config = {
                "crawl_type": args.crawl_type,
                "start_url": start_url,
                "url_patterns": template.get("url_patterns", []),
                "exclude_patterns": template.get("exclude_patterns", []),
                "max_depth": args.max_depth,
                "max_pages": args.max_pages,
                "schedule_cron": args.schedule,
            }

            return await crawler.create_crawl_schedule(args.manufacturer, crawl_config)

        if args.start_crawl:
            # Start manual crawl
            result = await crawler.start_crawl_job(args.start_crawl)
            if result.get("success"):
                # Automatically execute the job
                job_id = result["job_id"]
                execution_result = await crawler.execute_crawl_job(job_id)
                result["execution"] = execution_result
            return result

        if args.job_id:
            # Execute and monitor crawl job
            return await crawler.execute_crawl_job(args.job_id)

        if args.process_pages:
            # Process crawled pages
            return await crawler.process_crawled_pages(args.process_pages)

        if args.list_schedules:
            # List all schedules
            return await crawler.list_crawl_schedules()

        if args.history:
            # View crawl history
            return await crawler.list_crawl_jobs(args.history)

        if args.stats:
            # Show statistics
            return await crawler.get_crawler_stats()

        if args.check_scheduled:
            # Check scheduled crawls
            return await crawler.check_scheduled_crawls()

    # Execute operation
    try:
        result = asyncio.run(run_operation())

        # Save results to file
        if result and result.get("success"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crawler_result_{timestamp}.json"

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print_with_rich(f"💾 Results saved to: {filename}")

        return result

    except KeyboardInterrupt:
        print_with_rich("\n⚠️ Operation cancelled by user")
        return None
    except Exception as e:
        print_with_rich(f"❌ Fatal error: {e!s}")
        return None


if __name__ == "__main__":
    main()
