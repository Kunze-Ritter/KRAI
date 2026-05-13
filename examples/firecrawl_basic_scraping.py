#!/usr/bin/env python3
"""
Basic web scraping example demonstrating both Firecrawl and BeautifulSoup backends.

Purpose: Show how to scrape a single URL with automatic backend selection and fallback

Usage Examples:
    # Basic scraping (auto-detect backend)
    python examples/firecrawl_basic_scraping.py --url https://example.com

    # Force Firecrawl backend
    python examples/firecrawl_basic_scraping.py --url https://example.com --backend firecrawl

    # Compare both backends
    python examples/firecrawl_basic_scraping.py --url https://example.com --compare

    # Check backend health
    python examples/firecrawl_basic_scraping.py --health
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.web_scraping_service import FirecrawlUnavailableError, create_web_scraping_service

try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
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


def load_configuration() -> dict[str, str]:
    """Load scraping configuration from environment variables."""
    config = {
        "backend": os.getenv("SCRAPING_BACKEND", "beautifulsoup"),
        "firecrawl_api_url": os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"),
        "firecrawl_llm_provider": os.getenv("FIRECRAWL_LLM_PROVIDER", "ollama"),
        "firecrawl_model_name": os.getenv("FIRECRAWL_MODEL_NAME", "llama3.1:8b"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "firecrawl_max_concurrency": int(os.getenv("FIRECRAWL_MAX_CONCURRENCY", "3")),
        "firecrawl_block_media": os.getenv("FIRECRAWL_BLOCK_MEDIA", "true").lower() == "true",
    }

    # Display configuration summary
    if RICH_AVAILABLE and console:
        config_table = Table(title="🔧 Scraping Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")

        for key, value in config.items():
            if key == "openai_api_key" and value:
                value = f"***{value[-4:]}"  # Show last 4 chars only
            config_table.add_row(key.replace("_", " ").title(), str(value))

        console.print(config_table)
    else:
        print("=== Scraping Configuration ===")
        for key, value in config.items():
            if key == "openai_api_key" and value:
                value = f"***{value[-4:]}"
            print(f"{key.replace('_', ' ').title()}: {value}")
        print()

    return config


async def scrape_url_example(url: str, backend: str | None = None) -> dict[str, any]:
    """
    Scrape a single URL and display results.

    Args:
        url: URL to scrape
        backend: Force specific backend (firecrawl, beautifulsoup)

    Returns:
        Dictionary with scraping results
    """
    start_time = time.time()

    try:
        # Create web scraping service
        scraping_service = create_web_scraping_service(backend=backend)

        print_with_rich(f"🔍 Scraping URL: {url}")
        if backend:
            print_with_rich(f"📋 Using backend: {backend}")

        # Perform scraping
        result = await scraping_service.scrape_url(url)
        duration = time.time() - start_time

        if result.get("success", False):
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            backend_used = result.get("backend", "unknown")
            content_format = metadata.get("format", "text")

            # Display success information
            if RICH_AVAILABLE and console:
                success_panel = Panel(
                    f"✅ **Success**\n"
                    f"📊 Backend: {backend_used}\n"
                    f"📝 Format: {content_format}\n"
                    f"⏱️ Duration: {duration:.2f}s\n"
                    f"📏 Content Length: {len(content)} chars",
                    title="Scraping Results",
                    border_style="green",
                )
                console.print(success_panel)

                # Show content preview
                preview_length = min(500, len(content))
                content_preview = content[:preview_length]
                if len(content) > preview_length:
                    content_preview += "..."

                content_panel = Panel(content_preview, title=f"Content Preview ({content_format})", border_style="blue")
                console.print(content_panel)
            else:
                print("✅ Success!")
                print(f"📊 Backend: {backend_used}")
                print(f"📝 Format: {content_format}")
                print(f"⏱️ Duration: {duration:.2f}s")
                print(f"📏 Content Length: {len(content)} chars")
                print(f"\n--- Content Preview ({content_format}) ---")
                print(content[:500] + ("..." if len(content) > 500 else ""))

            return {
                "success": True,
                "backend": backend_used,
                "format": content_format,
                "duration": duration,
                "content_length": len(content),
                "content": content,
                "metadata": metadata,
            }
        error_msg = result.get("error", "Unknown error")

        if RICH_AVAILABLE and console:
            error_panel = Panel(
                f"❌ **Failed**\n" f"🚨 Error: {error_msg}\n" f"⏱️ Duration: {duration:.2f}s",
                title="Scraping Results",
                border_style="red",
            )
            console.print(error_panel)
        else:
            print("❌ Failed!")
            print(f"🚨 Error: {error_msg}")
            print(f"⏱️ Duration: {duration:.2f}s")

        return {"success": False, "error": error_msg, "duration": duration}

    except FirecrawlUnavailableError as e:
        if RICH_AVAILABLE and console:
            error_panel = Panel(
                "⚠️ **Firecrawl Unavailable**\n"
                "💡 Suggestion: Check Firecrawl services or use BeautifulSoup fallback\n"
                "🔧 Try: docker-compose up -d krai-firecrawl-api krai-firecrawl-worker\n"
                "📋 Or use: --backend beautifulsoup",
                title="Backend Error",
                border_style="yellow",
            )
            console.print(error_panel)
        else:
            print("⚠️ Firecrawl Unavailable")
            print("💡 Suggestion: Check Firecrawl services or use BeautifulSoup fallback")
            print("🔧 Try: docker-compose up -d krai-firecrawl-api krai-firecrawl-worker")
            print("📋 Or use: --backend beautifulsoup")

        return {
            "success": False,
            "error": str(e),
            "suggestion": "Use BeautifulSoup backend or check Firecrawl services",
        }

    except Exception as e:
        if RICH_AVAILABLE and console:
            error_panel = Panel(
                f"❌ **Unexpected Error**\n" f"🚨 {e!s}\n" f"💡 Check URL, network connection, and backend services",
                title="Error",
                border_style="red",
            )
            console.print(error_panel)
        else:
            print(f"❌ Unexpected Error: {e!s}")
            print("💡 Check URL, network connection, and backend services")

        return {"success": False, "error": str(e)}


async def compare_backends(url: str) -> dict[str, any]:
    """
    Compare scraping results from both Firecrawl and BeautifulSoup backends.

    Args:
        url: URL to scrape with both backends

    Returns:
        Dictionary with comparison results
    """
    print_with_rich(f"🔄 Comparing backends for: {url}")

    # Scrape with both backends
    firecrawl_result = await scrape_url_example(url, backend="firecrawl")
    beautifulsoup_result = await scrape_url_example(url, backend="beautifulsoup")

    # Create comparison table
    if RICH_AVAILABLE and console:
        comparison_table = Table(title="📊 Backend Comparison")
        comparison_table.add_column("Metric", style="cyan")
        comparison_table.add_column("Firecrawl", style="green")
        comparison_table.add_column("BeautifulSoup", style="blue")

        metrics = [
            (
                "Success",
                "✅" if firecrawl_result["success"] else "❌",
                "✅" if beautifulsoup_result["success"] else "❌",
            ),
            (
                "Duration",
                f"{firecrawl_result.get('duration', 0):.2f}s",
                f"{beautifulsoup_result.get('duration', 0):.2f}s",
            ),
            (
                "Content Length",
                str(firecrawl_result.get("content_length", 0)),
                str(beautifulsoup_result.get("content_length", 0)),
            ),
            ("Format", firecrawl_result.get("format", "unknown"), beautifulsoup_result.get("format", "unknown")),
            ("Backend", firecrawl_result.get("backend", "unknown"), beautifulsoup_result.get("backend", "unknown")),
        ]

        for metric, firecrawl_val, bs_val in metrics:
            comparison_table.add_row(metric, firecrawl_val, bs_val)

        console.print(comparison_table)
    else:
        print("\n=== Backend Comparison ===")
        print(f"{'Metric':<15} {'Firecrawl':<15} {'BeautifulSoup':<15}")
        print("-" * 45)

        metrics = [
            (
                "Success",
                "✅" if firecrawl_result["success"] else "❌",
                "✅" if beautifulsoup_result["success"] else "❌",
            ),
            (
                "Duration",
                f"{firecrawl_result.get('duration', 0):.2f}s",
                f"{beautifulsoup_result.get('duration', 0):.2f}s",
            ),
            (
                "Content Length",
                str(firecrawl_result.get("content_length", 0)),
                str(beautifulsoup_result.get("content_length", 0)),
            ),
            ("Format", firecrawl_result.get("format", "unknown"), beautifulsoup_result.get("format", "unknown")),
            ("Backend", firecrawl_result.get("backend", "unknown"), beautifulsoup_result.get("backend", "unknown")),
        ]

        for metric, firecrawl_val, bs_val in metrics:
            print(f"{metric:<15} {firecrawl_val:<15} {bs_val:<15}")

    return {"firecrawl": firecrawl_result, "beautifulsoup": beautifulsoup_result, "url": url}


async def check_backend_health() -> dict[str, any]:
    """
    Check the health and availability of both backends.

    Returns:
        Dictionary with health check results
    """
    print_with_rich("🏥 Checking backend health...")

    results = {}

    # Check BeautifulSoup using the same health check service
    try:
        scraping_service = create_web_scraping_service(backend="beautifulsoup")
        health_result = await scraping_service.health_check()

        # Parse the aggregated health check result
        status = health_result.get("status", "unknown")
        backends = health_result.get("backends", {})

        # Extract BeautifulSoup backend status from backends map
        bs_backend = backends.get("beautifulsoup", {})
        bs_status = bs_backend.get("status", "healthy")  # BeautifulSoup should always be healthy
        bs_available = bs_status in ("healthy", "degraded")

        results["beautifulsoup"] = {
            "available": bs_available,
            "status": bs_status,
            "notes": "Always available (built-in)",
            "details": health_result,
        }
    except Exception as e:
        # Fallback - BeautifulSoup should always be available
        results["beautifulsoup"] = {
            "available": True,
            "status": "healthy",
            "notes": "Always available (built-in)",
            "error": str(e),
        }

    # Check Firecrawl
    try:
        scraping_service = create_web_scraping_service(backend="firecrawl")
        health_result = await scraping_service.health_check()

        # Parse the aggregated health check result
        status = health_result.get("status", "unknown")
        backends = health_result.get("backends", {})

        # Extract Firecrawl backend status from backends map
        firecrawl_backend = backends.get("firecrawl", {})
        firecrawl_status = firecrawl_backend.get("status", "unavailable")
        firecrawl_available = firecrawl_status in ("healthy", "degraded")

        results["firecrawl"] = {
            "available": firecrawl_available,
            "status": firecrawl_status,
            "notes": f"Aggregated status: {status}",
            "details": health_result,
        }
    except Exception as e:
        results["firecrawl"] = {"available": False, "status": "unhealthy", "notes": str(e), "error": str(e)}

    # Display results
    if RICH_AVAILABLE and console:
        health_table = Table(title="🏥 Backend Health Status")
        health_table.add_column("Backend", style="cyan")
        health_table.add_column("Status", style="green")
        health_table.add_column("Notes", style="white")

        for backend, info in results.items():
            status_style = "green" if info["available"] else "red"
            status_icon = "✅" if info["available"] else "❌"
            health_table.add_row(backend.title(), f"{status_icon} {info['status']}", info["notes"])

        console.print(health_table)

        # Show default backend
        config = load_configuration()
        default_backend = config["backend"]
        default_available = results.get(default_backend, {}).get("available", False)

        default_status = "✅ Available" if default_available else "❌ Unavailable"
        default_style = "green" if default_available else "red"

        default_panel = Panel(
            f"Default Backend: **{default_backend.title()}**\n" f"Status: {default_status}",
            title="Default Configuration",
            border_style=default_style,
        )
        console.print(default_panel)
    else:
        print("\n=== Backend Health Status ===")
        for backend, info in results.items():
            status_icon = "✅" if info["available"] else "❌"
            print(f"{backend.title()}: {status_icon} {info['status']} - {info['notes']}")

        config = load_configuration()
        default_backend = config["backend"]
        default_available = results.get(default_backend, {}).get("available", False)
        print(
            f"\nDefault Backend: {default_backend.title()} - {'✅ Available' if default_available else '❌ Unavailable'}"
        )

    return results


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Basic web scraping example with Firecrawl and BeautifulSoup backends",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url https://example.com
  %(prog)s --url https://example.com --backend firecrawl
  %(prog)s --url https://example.com --compare
  %(prog)s --health
        """,
    )

    parser.add_argument("--url", type=str, help="URL to scrape (required unless --health is used)")

    parser.add_argument("--backend", choices=["firecrawl", "beautifulsoup"], help="Force specific backend (optional)")

    parser.add_argument("--compare", action="store_true", help="Compare both backends side-by-side")

    parser.add_argument("--health", action="store_true", help="Check backend health and availability")

    args = parser.parse_args()

    # Validate arguments
    if not args.health and not args.url:
        parser.error("--url is required unless --health is used")

    if args.compare and args.backend:
        parser.error("--compare and --backend are mutually exclusive")

    # Load and display configuration
    config = load_configuration()

    # Run the requested operation
    async def run_operation():
        if args.health:
            return await check_backend_health()
        if args.compare:
            return await compare_backends(args.url)
        return await scrape_url_example(args.url, args.backend)

    # Execute operation
    try:
        result = asyncio.run(run_operation())

        # Save results to file for inspection
        if args.url and result.get("success"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"scraping_result_{timestamp}.json"

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
