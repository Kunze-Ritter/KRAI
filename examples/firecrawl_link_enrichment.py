#!/usr/bin/env python3
"""
Link enrichment workflow example demonstrating complete link enrichment pipeline.

Purpose: Show the complete link enrichment pipeline from extraction to structured data extraction

Usage Examples:
    # Enrich all links in document
    python examples/firecrawl_link_enrichment.py --document-id abc-123-def

    # Enrich single link
    python examples/firecrawl_link_enrichment.py --link-id xyz-789-uvw

    # Batch enrichment
    python examples/firecrawl_link_enrichment.py --batch link_ids.txt

    # Retry failed links
    python examples/firecrawl_link_enrichment.py --retry-failed

    # Show statistics
    python examples/firecrawl_link_enrichment.py --stats
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

from backend.services.structured_extraction_service import StructuredExtractionService
from backend.services.web_scraping_service import WebScrapingService, create_web_scraping_service

try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
    from rich.table import Table

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


def load_link_enrichment_configuration() -> dict[str, str]:
    """Load link enrichment configuration from environment variables."""
    config = {
        "enable_link_enrichment": os.getenv("ENABLE_LINK_ENRICHMENT", "false").lower() == "true",
        "backend": os.getenv("SCRAPING_BACKEND", "firecrawl"),
        "firecrawl_api_url": os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"),
        "firecrawl_llm_provider": os.getenv("FIRECRAWL_LLM_PROVIDER", "ollama"),
        "max_concurrent": int(os.getenv("LINK_ENRICHMENT_MAX_CONCURRENT", "3")),
        "retry_limit": int(os.getenv("LINK_ENRICHMENT_RETRY_LIMIT", "3")),
        "stale_days": int(os.getenv("LINK_ENRICHMENT_STALE_DAYS", "90")),
    }

    # Display configuration summary
    if RICH_AVAILABLE and console:
        config_table = Table(title="🔧 Link Enrichment Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")

        for key, value in config.items():
            status_style = (
                "green"
                if (key == "enable_link_enrichment" and value)
                else "yellow"
                if key == "enable_link_enrichment"
                else "white"
            )
            config_table.add_row(key.replace("_", " ").title(), str(value), style=status_style)

        console.print(config_table)

        if not config["enable_link_enrichment"]:
            warning_panel = Panel(
                "⚠️ **Link Enrichment Disabled**\n"
                "💡 Set ENABLE_LINK_ENRICHMENT=true in your .env file\n"
                "🔧 This example will work but won't affect real data",
                title="Configuration Warning",
                border_style="yellow",
            )
            console.print(warning_panel)
    else:
        print("=== Link Enrichment Configuration ===")
        for key, value in config.items():
            print(f"{key.replace('_', ' ').title()}: {value}")

        if not config["enable_link_enrichment"]:
            print("\n⚠️ Link Enrichment Disabled")
            print("💡 Set ENABLE_LINK_ENRICHMENT=true in your .env file")
            print("🔧 This example will work but won't affect real data")
        print()

    return config


class MockLinkEnrichmentService:
    """Mock link enrichment service for demonstration purposes."""

    def __init__(self, scraping_service: WebScrapingService):
        self.scraping_service = scraping_service
        self.logger = __import__("logging").getLogger("krai.mock.link_enrichment")

    async def enrich_document_links(self, document_id: str) -> dict[str, Any]:
        """Enrich all links for a document."""
        # Mock data - in real implementation this would query database
        mock_links = [
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/product/specs",
                "link_type": "product",
                "scrape_status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/support/error-codes",
                "link_type": "support",
                "scrape_status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/manuals/service-guide",
                "link_type": "manual",
                "scrape_status": "pending",
            },
        ]

        print_with_rich(f"📄 Found {len(mock_links)} links to enrich for document: {document_id}")

        # Enrich each link
        results = []
        for link in mock_links:
            result = await self.enrich_link(link["id"], link["url"])
            results.append(result)

        successful = sum(1 for r in results if r.get("success", False))

        return {
            "success": True,
            "document_id": document_id,
            "total_links": len(mock_links),
            "successful": successful,
            "failed": len(mock_links) - successful,
            "results": results,
        }

    async def enrich_link(self, link_id: str, url: str) -> dict[str, Any]:
        """Enrich a single link."""
        start_time = time.time()

        try:
            print_with_rich(f"🔗 Enriching link: {url}")

            # Scrape the URL
            result = await self.scraping_service.scrape_url(url)
            duration = time.time() - start_time

            if result.get("success", False):
                content = result.get("content", "")
                metadata = result.get("metadata", {})
                backend_used = metadata.get("backend", "unknown")

                print_with_rich("✅ Link enriched successfully")
                print_with_rich(f"📊 Backend: {backend_used}, Content length: {len(content)} chars")

                return {
                    "success": True,
                    "link_id": link_id,
                    "url": url,
                    "content": content,
                    "metadata": metadata,
                    "duration": duration,
                    "backend": backend_used,
                }
            error_msg = result.get("error", "Unknown error")
            print_with_rich(f"❌ Link enrichment failed: {error_msg}")

            return {"success": False, "link_id": link_id, "url": url, "error": error_msg, "duration": duration}

        except Exception as e:
            print_with_rich(f"❌ Error enriching link: {e!s}")
            return {"success": False, "link_id": link_id, "url": url, "error": str(e)}

    async def enrich_links_batch(self, link_ids: list[str], max_concurrent: int = 3) -> dict[str, Any]:
        """Enrich multiple links concurrently."""
        print_with_rich(f"🚀 Batch enriching {len(link_ids)} links (max concurrent: {max_concurrent})")

        # Mock URL generation for demo
        mock_urls = [f"https://example.com/link/{i}" for i in range(len(link_ids))]

        # Create semaphore to limit concurrent operations
        semaphore = asyncio.Semaphore(max_concurrent)

        async def enrich_with_semaphore(link_id: str, url: str):
            async with semaphore:
                return await self.enrich_link(link_id, url)

        # Process with progress tracking
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
                task = progress.add_task("Enriching links...", total=len(link_ids))

                # Create tasks
                tasks = []
                for link_id, url in zip(link_ids, mock_urls):
                    task_coro = enrich_with_semaphore(link_id, url)
                    task_future = asyncio.create_task(task_coro)
                    tasks.append(task_future)

                # Process results
                results = []
                for task_future in tasks:
                    try:
                        result = await task_future
                        results.append(result)
                        progress.advance(task, 1)
                    except Exception as e:
                        results.append({"success": False, "error": str(e)})
                        progress.advance(task, 1)
        else:
            print("🚀 Enriching links...")
            results = []
            for link_id, url in zip(link_ids, mock_urls):
                try:
                    result = await enrich_with_semaphore(link_id, url)
                    results.append(result)
                    print(f"  ✅ Processed: {link_id}")
                except Exception as e:
                    results.append({"success": False, "error": str(e)})
                    print(f"  ❌ Failed: {link_id}")

        duration = time.time() - start_time
        successful = sum(1 for r in results if r.get("success", False))
        failed = len(results) - successful

        # Display batch results
        if RICH_AVAILABLE and console:
            batch_panel = Panel(
                f"✅ **Batch Enrichment Complete**\n"
                f"📊 Total Links: {len(link_ids)}\n"
                f"✅ Successful: {successful}\n"
                f"❌ Failed: {failed}\n"
                f"⏱️ Duration: {duration:.2f}s\n"
                f"📊 Average per link: {duration/len(link_ids):.2f}s",
                title="Batch Results",
                border_style="green" if successful == len(link_ids) else "yellow",
            )
            console.print(batch_panel)
        else:
            print("\n✅ Batch Enrichment Complete!")
            print(f"📊 Total Links: {len(link_ids)}")
            print(f"✅ Successful: {successful}")
            print(f"❌ Failed: {failed}")
            print(f"⏱️ Duration: {duration:.2f}s")
            print(f"📊 Average per link: {duration/len(link_ids):.2f}s")

        return {
            "success": True,
            "total_links": len(link_ids),
            "successful": successful,
            "failed": failed,
            "duration": duration,
            "results": results,
        }

    async def retry_failed_links(self, max_retries: int = 3) -> dict[str, Any]:
        """Retry failed links."""
        print_with_rich(f"🔄 Retrying failed links (max retries: {max_retries})")

        # Mock failed links
        mock_failed_links = [
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/failed/link1",
                "scrape_error": "Connection timeout",
                "retry_count": 1,
            },
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/failed/link2",
                "scrape_error": "404 Not Found",
                "retry_count": 0,
            },
        ]

        # Filter links that haven't exceeded retry limit
        retryable_links = [link for link in mock_failed_links if link["retry_count"] < max_retries]

        print_with_rich(f"📊 Found {len(retryable_links)} retryable links out of {len(mock_failed_links)} failed")

        if not retryable_links:
            return {
                "success": True,
                "total_failed": len(mock_failed_links),
                "retryable": 0,
                "retried": 0,
                "now_successful": 0,
                "still_failing": 0,
            }

        # Retry the links
        results = []
        for link in retryable_links:
            result = await self.enrich_link(link["id"], link["url"])
            results.append(result)

        now_successful = sum(1 for r in results if r.get("success", False))
        still_failing = len(results) - now_successful

        # Display retry results
        if RICH_AVAILABLE and console:
            retry_panel = Panel(
                f"✅ **Retry Operation Complete**\n"
                f"📊 Links Retried: {len(retryable_links)}\n"
                f"✅ Now Successful: {now_successful}\n"
                f"❌ Still Failing: {still_failing}",
                title="Retry Results",
                border_style="green" if now_successful == len(retryable_links) else "yellow",
            )
            console.print(retry_panel)
        else:
            print("\n✅ Retry Operation Complete!")
            print(f"📊 Links Retried: {len(retryable_links)}")
            print(f"✅ Now Successful: {now_successful}")
            print(f"❌ Still Failing: {still_failing}")

        return {
            "success": True,
            "total_failed": len(mock_failed_links),
            "retryable": len(retryable_links),
            "retried": len(retryable_links),
            "now_successful": now_successful,
            "still_failing": still_failing,
            "results": results,
        }

    async def refresh_stale_links(self, days_old: int = 90) -> dict[str, Any]:
        """Refresh stale content."""
        print_with_rich(f"🔄 Refreshing stale content (older than {days_old} days)")

        # Mock stale links
        stale_date = datetime.now() - timedelta(days=days_old + 10)
        mock_stale_links = [
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/stale/link1",
                "scraped_at": stale_date.isoformat(),
                "content_hash": "old_hash_123",
            },
            {
                "id": str(uuid.uuid4()),
                "url": "https://example.com/stale/link2",
                "scraped_at": stale_date.isoformat(),
                "content_hash": "old_hash_456",
            },
        ]

        print_with_rich(f"📊 Found {len(mock_stale_links)} stale links to refresh")

        # Refresh each stale link
        results = []
        content_changed = 0

        for link in mock_stale_links:
            result = await self.enrich_link(link["id"], link["url"])

            # Simulate content change detection
            if result.get("success", False):
                result["content_changed"] = True  # Mock: content changed
                content_changed += 1
            else:
                result["content_changed"] = False

            results.append(result)

        successful = sum(1 for r in results if r.get("success", False))

        # Display refresh results
        if RICH_AVAILABLE and console:
            refresh_panel = Panel(
                f"✅ **Stale Content Refresh Complete**\n"
                f"📊 Links Refreshed: {len(mock_stale_links)}\n"
                f"✅ Successful: {successful}\n"
                f"🔄 Content Changed: {content_changed}\n"
                f"📊 Content Unchanged: {successful - content_changed}",
                title="Refresh Results",
                border_style="green",
            )
            console.print(refresh_panel)
        else:
            print("\n✅ Stale Content Refresh Complete!")
            print(f"📊 Links Refreshed: {len(mock_stale_links)}")
            print(f"✅ Successful: {successful}")
            print(f"🔄 Content Changed: {content_changed}")
            print(f"📊 Content Unchanged: {successful - content_changed}")

        return {
            "success": True,
            "total_stale": len(mock_stale_links),
            "successful": successful,
            "content_changed": content_changed,
            "content_unchanged": successful - content_changed,
            "results": results,
        }

    async def get_enrichment_stats(self) -> dict[str, Any]:
        """Get enrichment statistics."""
        # Mock statistics
        stats = {
            "total_links": 150,
            "enriched_links": 120,
            "pending_links": 20,
            "failed_links": 10,
            "average_content_length": 2500,
            "backend_distribution": {"firecrawl": 85, "beautifulsoup": 35},
        }

        enrichment_coverage = (stats["enriched_links"] / stats["total_links"]) * 100

        # Display statistics
        if RICH_AVAILABLE and console:
            stats_table = Table(title="📊 Link Enrichment Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Value", style="green")
            stats_table.add_column("Percentage", style="yellow")

            stats_table.add_row("Total Links", str(stats["total_links"]), "100%")
            stats_table.add_row("Enriched Links", str(stats["enriched_links"]), f"{enrichment_coverage:.1f}%")
            stats_table.add_row(
                "Pending Links",
                str(stats["pending_links"]),
                f"{(stats['pending_links']/stats['total_links']*100):.1f}%",
            )
            stats_table.add_row(
                "Failed Links", str(stats["failed_links"]), f"{(stats['failed_links']/stats['total_links']*100):.1f}%"
            )
            stats_table.add_row("Avg Content Length", f"{stats['average_content_length']} chars", "-")

            console.print(stats_table)

            # Backend distribution
            backend_table = Table(title="🔧 Backend Distribution")
            backend_table.add_column("Backend", style="cyan")
            backend_table.add_column("Count", style="green")
            backend_table.add_column("Percentage", style="yellow")

            total_backend = sum(stats["backend_distribution"].values())
            for backend, count in stats["backend_distribution"].items():
                percentage = (count / total_backend) * 100
                backend_table.add_row(backend.title(), str(count), f"{percentage:.1f}%")

            console.print(backend_table)
        else:
            print("=== Link Enrichment Statistics ===")
            print(f"Total Links: {stats['total_links']}")
            print(f"Enriched Links: {stats['enriched_links']} ({enrichment_coverage:.1f}%)")
            print(f"Pending Links: {stats['pending_links']} ({(stats['pending_links']/stats['total_links']*100):.1f}%)")
            print(f"Failed Links: {stats['failed_links']} ({(stats['failed_links']/stats['total_links']*100):.1f}%)")
            print(f"Average Content Length: {stats['average_content_length']} chars")

            print("\n=== Backend Distribution ===")
            for backend, count in stats["backend_distribution"].items():
                percentage = (count / total_backend) * 100
                print(f"{backend.title()}: {count} ({percentage:.1f}%)")

        return stats


async def process_enriched_links(document_id: str) -> dict[str, Any]:
    """
    Process enriched links with structured extraction.

    Args:
        document_id: Document ID to process links for

    Returns:
        Processing results
    """
    print_with_rich(f"🔍 Processing enriched links for document: {document_id}")

    # Mock enriched links
    mock_enriched_links = [
        {
            "id": str(uuid.uuid4()),
            "url": "https://example.com/product/bizhub-c750i",
            "content": "bizhub C750i specifications: 75 ppm, 1200x1200 dpi, 8GB memory",
            "link_type": "product",
        },
        {
            "id": str(uuid.uuid4()),
            "url": "https://example.com/support/errors",
            "content": "Error codes: C-2801 Fuser unit failure, C-2552 Transfer belt failure",
            "link_type": "support",
        },
        {
            "id": str(uuid.uuid4()),
            "url": "https://example.com/manuals/service",
            "content": "Service manual for bizhub series, 500 pages, revision 2.1",
            "link_type": "manual",
        },
    ]

    # Create structured extraction service
    scraping_service = create_web_scraping_service(backend="firecrawl")

    class MockDatabaseService:
        async def insert_structured_extraction(self, data):
            return True

    db_service = MockDatabaseService()
    extraction_service = StructuredExtractionService(web_scraping_service=scraping_service, database_service=db_service)

    processing_results = []

    for link in mock_enriched_links:
        link_type = link["link_type"]
        url = link["url"]

        print_with_rich(f"🔍 Processing {link_type} link: {url}")

        # Process based on link type
        if link_type == "product":
            # Extract product specs (mock - would use real extraction)
            result = {
                "success": True,
                "link_id": link["id"],
                "extraction_type": "product_specs",
                "data": {"model_number": "bizhub C750i", "speed": "75 ppm", "resolution": "1200x1200 dpi"},
            }
        elif link_type == "support":
            # Extract error codes (mock)
            result = {
                "success": True,
                "link_id": link["id"],
                "extraction_type": "error_codes",
                "data": {
                    "error_codes": [
                        {"code": "C-2801", "description": "Fuser unit failure"},
                        {"code": "C-2552", "description": "Transfer belt failure"},
                    ]
                },
            }
        elif link_type == "manual":
            # Extract manual metadata (mock)
            result = {
                "success": True,
                "link_id": link["id"],
                "extraction_type": "service_manual",
                "data": {"manual_type": "service_manual", "page_count": 500, "version": "2.1"},
            }
        else:
            result = {"success": False, "link_id": link["id"], "error": f"Unknown link type: {link_type}"}

        processing_results.append(result)

        if result.get("success"):
            print_with_rich(f"✅ Extracted {result['extraction_type']} from link")
        else:
            print_with_rich(f"❌ Failed to process link: {result.get('error')}")

    # Summarize processing results
    successful = sum(1 for r in processing_results if r.get("success", False))
    extractions_by_type = {}

    for result in processing_results:
        if result.get("success"):
            extraction_type = result.get("extraction_type", "unknown")
            extractions_by_type[extraction_type] = extractions_by_type.get(extraction_type, 0) + 1

    # Display processing summary
    if RICH_AVAILABLE and console:
        processing_panel = Panel(
            f"✅ **Link Processing Complete**\n"
            f"📊 Total Links: {len(mock_enriched_links)}\n"
            f"✅ Processed: {successful}\n"
            f"❌ Failed: {len(mock_enriched_links) - successful}\n"
            f"🔍 Extractions: {', '.join([f'{k}({v})' for k, v in extractions_by_type.items()])}",
            title="Processing Results",
            border_style="green",
        )
        console.print(processing_panel)
    else:
        print("\n✅ Link Processing Complete!")
        print(f"📊 Total Links: {len(mock_enriched_links)}")
        print(f"✅ Processed: {successful}")
        print(f"❌ Failed: {len(mock_enriched_links) - successful}")
        print(f"🔍 Extractions: {', '.join([f'{k}({v})' for k, v in extractions_by_type.items()])}")

    return {
        "success": True,
        "document_id": document_id,
        "total_links": len(mock_enriched_links),
        "successful": successful,
        "failed": len(mock_enriched_links) - successful,
        "extractions_by_type": extractions_by_type,
        "results": processing_results,
    }


async def complete_enrichment_workflow(document_id: str) -> dict[str, Any]:
    """
    Run the complete enrichment workflow: enrichment -> processing -> results.

    Args:
        document_id: Document ID to run workflow for

    Returns:
        Complete workflow results
    """
    print_with_rich(f"🚀 Starting complete enrichment workflow for document: {document_id}")

    workflow_results = {"document_id": document_id, "steps": {}}

    try:
        # Step 1: Enrich document links
        print_with_rich("\n📋 Step 1: Enriching document links...")
        scraping_service = create_web_scraping_service(backend="firecrawl")
        enrichment_service = MockLinkEnrichmentService(scraping_service)

        enrichment_result = await enrichment_service.enrich_document_links(document_id)
        workflow_results["steps"]["enrichment"] = enrichment_result

        if not enrichment_result.get("success"):
            print_with_rich("❌ Enrichment step failed, stopping workflow")
            return workflow_results

        # Step 2: Process enriched links
        print_with_rich("\n🔍 Step 2: Processing enriched links...")
        processing_result = await process_enriched_links(document_id)
        workflow_results["steps"]["processing"] = processing_result

        # Step 3: Display final results
        print_with_rich("\n📊 Step 3: Final workflow results...")

        total_enriched = enrichment_result.get("successful", 0)
        total_processed = processing_result.get("successful", 0)
        extractions = processing_result.get("extractions_by_type", {})

        if RICH_AVAILABLE and console:
            final_panel = Panel(
                f"✅ **Complete Workflow Successful**\n"
                f"📄 Document: {document_id}\n"
                f"🔗 Links Enriched: {total_enriched}\n"
                f"🔍 Links Processed: {total_processed}\n"
                f"📋 Extractions Found: {', '.join([f'{k}({v})' for k, v in extractions.items()]) or 'None'}\n"
                f"🎯 Pipeline: PDF → Links → Scraping → Extraction → Database",
                title="Workflow Complete",
                border_style="green",
            )
            console.print(final_panel)
        else:
            print("\n✅ Complete Workflow Successful!")
            print(f"📄 Document: {document_id}")
            print(f"🔗 Links Enriched: {total_enriched}")
            print(f"🔍 Links Processed: {total_processed}")
            print(f"📋 Extractions Found: {', '.join([f'{k}({v})' for k, v in extractions.items()]) or 'None'}")
            print("🎯 Pipeline: PDF → Links → Scraping → Extraction → Database")

        workflow_results["success"] = True
        workflow_results["summary"] = {
            "total_enriched": total_enriched,
            "total_processed": total_processed,
            "extractions": extractions,
        }

        return workflow_results

    except Exception as e:
        print_with_rich(f"❌ Workflow failed: {e!s}")
        workflow_results["success"] = False
        workflow_results["error"] = str(e)
        return workflow_results


def load_link_ids_from_file(filename: str) -> list[str]:
    """Load link IDs from a text file."""
    try:
        with open(filename, encoding="utf-8") as f:
            link_ids = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        return link_ids
    except FileNotFoundError:
        print_with_rich(f"❌ File not found: {filename}")
        return []
    except Exception as e:
        print_with_rich(f"❌ Error reading file: {e!s}")
        return []


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Link enrichment workflow example demonstrating complete link enrichment pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --document-id abc-123-def
  %(prog)s --link-id xyz-789-uvw
  %(prog)s --batch link_ids.txt
  %(prog)s --retry-failed
  %(prog)s --refresh-stale --days-old 30
  %(prog)s --stats
  %(prog)s --document-id abc-123-def --workflow
        """,
    )

    # Operation options
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument("--document-id", type=str, help="Document UUID to enrich links for")
    operation_group.add_argument("--link-id", type=str, help="Single link UUID to enrich")
    operation_group.add_argument("--batch", type=str, help="File with link IDs for batch enrichment")
    operation_group.add_argument("--retry-failed", action="store_true", help="Retry failed links")
    operation_group.add_argument("--refresh-stale", action="store_true", help="Refresh old content")
    operation_group.add_argument("--stats", action="store_true", help="Show enrichment statistics")

    # Additional options
    parser.add_argument("--days-old", type=int, default=90, help="Days threshold for stale content (default: 90)")

    parser.add_argument(
        "--workflow", action="store_true", help="Run complete enrichment workflow (only with --document-id)"
    )

    args = parser.parse_args()

    # Validate arguments
    if args.workflow and not args.document_id:
        parser.error("--workflow requires --document-id")

    # Load configuration
    config = load_link_enrichment_configuration()

    # Run the requested operation
    async def run_operation():
        # Create services
        scraping_service = create_web_scraping_service(backend=config["backend"])
        enrichment_service = MockLinkEnrichmentService(scraping_service)

        if args.document_id:
            if args.workflow:
                # Complete workflow
                return await complete_enrichment_workflow(args.document_id)
            # Enrich document links
            return await enrichment_service.enrich_document_links(args.document_id)

        if args.link_id:
            # Enrich single link
            return await enrichment_service.enrich_link(args.link_id, f"https://example.com/link/{args.link_id}")

        if args.batch:
            # Batch enrichment
            link_ids = load_link_ids_from_file(args.batch)
            if not link_ids:
                return {"success": False, "error": "No link IDs found in batch file"}

            return await enrichment_service.enrich_links_batch(link_ids, max_concurrent=config["max_concurrent"])

        if args.retry_failed:
            # Retry failed links
            return await enrichment_service.retry_failed_links(max_retries=config["retry_limit"])

        if args.refresh_stale:
            # Refresh stale content
            return await enrichment_service.refresh_stale_links(days_old=args.days_old)

        if args.stats:
            # Show statistics
            return await enrichment_service.get_enrichment_stats()

    # Execute operation
    try:
        result = asyncio.run(run_operation())

        # Save results to file
        if result and result.get("success"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"link_enrichment_result_{timestamp}.json"

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
