#!/usr/bin/env python3
"""
Site crawling example demonstrating manufacturer website crawling with URL filtering and depth control.

Purpose: Show how to crawl multiple pages from a manufacturer website with URL filtering and depth control

Usage Examples:
    # Crawl manufacturer site
    python examples/firecrawl_site_crawling.py --url https://kmbs.konicaminolta.us/products/ --max-pages 20

    # Crawl with manufacturer shortcut
    python examples/firecrawl_site_crawling.py --manufacturer "Konica Minolta" --max-pages 50

    # Crawl and filter product pages
    python examples/firecrawl_site_crawling.py --url https://example.com --filter ".*product.*" --analyze

    # Export results
    python examples/firecrawl_site_crawling.py --url https://example.com --export json
"""

import argparse
import asyncio
import json
import os
import re
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


def load_crawl_configuration() -> dict[str, any]:
    """Load crawling configuration from environment variables."""
    config = {
        "backend": os.getenv("SCRAPING_BACKEND", "firecrawl"),  # Firecrawl recommended for crawling
        "firecrawl_api_url": os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"),
        "max_pages": int(os.getenv("FIRECRAWL_MAX_PAGES", "10")),
        "max_depth": int(os.getenv("FIRECRAWL_MAX_DEPTH", "2")),
        "max_concurrency": int(os.getenv("FIRECRAWL_MAX_CONCURRENCY", "3")),
        "block_media": os.getenv("FIRECRAWL_BLOCK_MEDIA", "true").lower() == "true",
    }

    # Display configuration summary
    if RICH_AVAILABLE and console:
        config_table = Table(title="🔧 Crawling Configuration")
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="green")

        for key, value in config.items():
            config_table.add_row(key.replace("_", " ").title(), str(value))

        console.print(config_table)
    else:
        print("=== Crawling Configuration ===")
        for key, value in config.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        print()

    return config


def get_manufacturer_urls() -> dict[str, dict[str, str]]:
    """Get pre-configured manufacturer URLs and patterns."""
    return {
        "Konica Minolta": {
            "base_url": "https://kmbs.konicaminolta.us",
            "products_url": "https://kmbs.konicaminolta.us/products/",
            "support_url": "https://kmbs.konicaminolta.us/support/",
            "patterns": [r".*bizhub.*", r".*accurio.*", r".*product.*", r".*support.*"],
            "name": "Konica Minolta",
        },
        "HP": {
            "base_url": "https://support.hp.com",
            "products_url": "https://www.hp.com/us-en/printers/",
            "support_url": "https://support.hp.com/us-en/products/",
            "patterns": [r".*laserjet.*", r".*officejet.*", r".*product.*", r".*support.*"],
            "name": "HP",
        },
        "Canon": {
            "base_url": "https://www.usa.canon.com",
            "products_url": "https://www.usa.canon.com/products/",
            "support_url": "https://www.usa.canon.com/support/",
            "patterns": [r".*imagerunner.*", r".*imageclass.*", r".*product.*", r".*support.*"],
            "name": "Canon",
        },
        "Lexmark": {
            "base_url": "https://support.lexmark.com",
            "products_url": "https://www.lexmark.com/us_en/products/",
            "support_url": "https://support.lexmark.com/",
            "patterns": [r".*product.*", r".*support.*", r".*manual.*"],
            "name": "Lexmark",
        },
    }


async def crawl_manufacturer_site(start_url: str, options: dict | None = None) -> dict[str, any]:
    """
    Crawl a manufacturer website with depth control and URL filtering.

    Args:
        start_url: Starting URL for crawling
        options: Crawl options (max_pages, max_depth, etc.)

    Returns:
        Dictionary with crawl results and pages
    """
    start_time = time.time()

    # Default options
    default_options = {
        "limit": 10,
        "maxDepth": 2,
        "allowBackwardLinks": False,  # Stay within site
        "includeHtml": False,
        "waitFor": 2000,  # Wait 2 seconds for JavaScript
        "screenshot": False,
        "removeTags": ["script", "style", "nav", "footer", "header"],
    }

    if options:
        default_options.update(options)

    try:
        # Create web scraping service
        scraping_service = create_web_scraping_service(backend="firecrawl")

        print_with_rich(f"🕷️ Starting crawl: {start_url}")
        print_with_rich(f"📊 Options: {default_options}")

        # Perform crawling with progress tracking
        if RICH_AVAILABLE and console:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Crawling pages...", total=None)

                # Start crawl
                result = await scraping_service.crawl_site(start_url, default_options)

                progress.update(task, completed=100, description="Crawl completed")
        else:
            print("🕷️ Crawling pages...")
            result = await scraping_service.crawl_site(start_url, default_options)

        duration = time.time() - start_time

        if result.get("success", False):
            pages = result.get("pages", [])
            metadata = result.get("metadata", {})

            # Display crawl results
            if RICH_AVAILABLE and console:
                success_panel = Panel(
                    f"✅ **Crawl Successful**\n"
                    f"📄 Pages Discovered: {len(pages)}\n"
                    f"⏱️ Duration: {duration:.2f}s\n"
                    f"📊 Average Content Length: {sum(len(p.get('content', '')) for p in pages) / max(len(pages), 1):.0f} chars",
                    title="Crawl Results",
                    border_style="green",
                )
                console.print(success_panel)
            else:
                print("✅ Crawl Successful!")
                print(f"📄 Pages Discovered: {len(pages)}")
                print(f"⏱️ Duration: {duration:.2f}s")
                avg_length = sum(len(p.get("content", "")) for p in pages) / max(len(pages), 1)
                print(f"📊 Average Content Length: {avg_length:.0f} chars")

            # Display crawl tree (URL hierarchy by depth)
            display_crawl_tree(pages)

            # Save results to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crawl_results_{timestamp}.json"

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "start_url": start_url,
                        "options": default_options,
                        "metadata": metadata,
                        "pages": pages,
                        "duration": duration,
                        "timestamp": timestamp,
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            print_with_rich(f"💾 Results saved to: {filename}")

            return {"success": True, "pages": pages, "metadata": metadata, "duration": duration, "filename": filename}
        error_msg = result.get("error", "Unknown error")

        if RICH_AVAILABLE and console:
            error_panel = Panel(
                f"❌ **Crawl Failed**\n" f"🚨 Error: {error_msg}\n" f"⏱️ Duration: {duration:.2f}s",
                title="Crawl Results",
                border_style="red",
            )
            console.print(error_panel)
        else:
            print("❌ Crawl Failed!")
            print(f"🚨 Error: {error_msg}")
            print(f"⏱️ Duration: {duration:.2f}s")

        return {"success": False, "error": error_msg, "duration": duration}

    except FirecrawlUnavailableError as e:
        if RICH_AVAILABLE and console:
            error_panel = Panel(
                "⚠️ **Firecrawl Unavailable**\n"
                "💡 Crawling requires Firecrawl for JavaScript rendering\n"
                "🔧 Try: docker-compose up -d krai-firecrawl-api krai-firecrawl-worker",
                title="Backend Error",
                border_style="yellow",
            )
            console.print(error_panel)
        else:
            print("⚠️ Firecrawl Unavailable")
            print("💡 Crawling requires Firecrawl for JavaScript rendering")
            print("🔧 Try: docker-compose up -d krai-firecrawl-api krai-firecrawl-worker")

        return {"success": False, "error": str(e), "suggestion": "Firecrawl is required for crawling"}

    except Exception as e:
        if RICH_AVAILABLE and console:
            error_panel = Panel(
                f"❌ **Unexpected Error**\n" f"🚨 {e!s}\n" f"💡 Check URL, network connection, and Firecrawl services",
                title="Error",
                border_style="red",
            )
            console.print(error_panel)
        else:
            print(f"❌ Unexpected Error: {e!s}")
            print("💡 Check URL, network connection, and Firecrawl services")

        return {"success": False, "error": str(e)}


def display_crawl_tree(pages: list[dict]) -> None:
    """Display crawled pages as a tree structure showing URL hierarchy."""
    if not pages:
        return

    if RICH_AVAILABLE and console:
        tree = Tree("🌳 Crawl Tree (URL Hierarchy)")

        # Group pages by depth
        pages_by_depth = {}
        for page in pages:
            depth = page.get("metadata", {}).get("depth", 0)
            if depth not in pages_by_depth:
                pages_by_depth[depth] = []
            pages_by_depth[depth].append(page)

        # Build tree structure
        max_depth = max(pages_by_depth.keys()) if pages_by_depth else 0

        for depth in range(max_depth + 1):
            depth_pages = pages_by_depth.get(depth, [])
            if depth == 0:
                # Root URLs
                for page in depth_pages:
                    url = page.get("url", "")[:60] + ("..." if len(page.get("url", "")) > 60 else "")
                    content_len = len(page.get("content", ""))
                    node = tree.add(f"📄 {url} ({content_len} chars)")
            else:
                # Child URLs - add to appropriate parent (simplified)
                parent_node = tree.children[0] if tree.children else tree
                for page in depth_pages:
                    url = page.get("url", "")[:60] + ("..." if len(page.get("url", "")) > 60 else "")
                    content_len = len(page.get("content", ""))
                    parent_node.add(f"📄 {url} ({content_len} chars)")

        console.print(tree)
    else:
        print("\n=== Crawl Tree (URL Hierarchy) ===")

        # Group by depth and display
        pages_by_depth = {}
        for page in pages:
            depth = page.get("metadata", {}).get("depth", 0)
            if depth not in pages_by_depth:
                pages_by_depth[depth] = []
            pages_by_depth[depth].append(page)

        for depth in sorted(pages_by_depth.keys()):
            print(f"\nDepth {depth}:")
            for page in pages_by_depth[depth]:
                url = page.get("url", "")
                content_len = len(page.get("content", ""))
                print(f"  📄 {url} ({content_len} chars)")


def filter_urls_by_pattern(pages: list[dict], patterns: list[str]) -> list[dict]:
    """
    Filter crawled pages by URL patterns.

    Args:
        pages: List of crawled pages
        patterns: List of regex patterns to match URLs

    Returns:
        Filtered list of pages
    """
    filtered_pages = []

    for page in pages:
        url = page.get("url", "")

        for pattern in patterns:
            try:
                if re.search(pattern, url, re.IGNORECASE):
                    filtered_pages.append(page)
                    break
            except re.error as e:
                print(f"⚠️ Invalid regex pattern '{pattern}': {e}")
                continue

    return filtered_pages


async def analyze_crawled_content(pages: list[dict]) -> dict[str, any]:
    """
    Analyze crawled pages to detect types, patterns, and resources.

    Args:
        pages: List of crawled pages

    Returns:
        Analysis results
    """
    if not pages:
        return {"error": "No pages to analyze"}

    print_with_rich("🔍 Analyzing crawled content...")

    analysis = {
        "total_pages": len(pages),
        "page_types": {"product": 0, "support": 0, "manual": 0, "error_code": 0, "other": 0},
        "detected_products": set(),
        "detected_error_codes": set(),
        "downloadable_resources": [],
        "common_patterns": {},
    }

    # Analyze each page
    for page in pages:
        url = page.get("url", "").lower()
        content = page.get("content", "").lower()

        # Detect page types
        if any(keyword in url for keyword in ["product", "model", "spec"]):
            analysis["page_types"]["product"] += 1
        elif any(keyword in url for keyword in ["support", "help", "troubleshoot"]):
            analysis["page_types"]["support"] += 1
        elif any(keyword in url for keyword in ["manual", "guide", "handbook"]):
            analysis["page_types"]["manual"] += 1
        elif any(keyword in url for keyword in ["error", "code", "fault"]):
            analysis["page_types"]["error_code"] += 1
        else:
            analysis["page_types"]["other"] += 1

        # Extract product models (basic pattern matching)
        product_patterns = [
            r"\b(bizhub|accurio|laserjet|officejet|imagerunner|imageclass)\s*[a-z0-9-]+\b",
            r"\bmodel\s*[a-z0-9-]+\b",
            r"\b[a-z]{1,3}\d{3,4}[a-z]?\b",  # Common model pattern
        ]

        for pattern in product_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            analysis["detected_products"].update(matches)

        # Extract error codes
        error_patterns = [
            r"\b[0-9]{2,4}\.[0-9]{2}\b",  # Format like 900.01
            r"\b[a-z]-\d{4}\b",  # Format like C-2801
            r"\berror\s+\d+\b",
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            analysis["detected_error_codes"].update(matches)

        # Find downloadable resources
        resource_patterns = [r'\b[^"\'>]*\.pdf\b', r'\b[^"\'>]*\.docx?\b', r'\b[^"\'>]*\.xlsx?\b']

        for pattern in resource_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if match.startswith(("http", "/")):
                    analysis["downloadable_resources"].append(match)

    # Convert sets to lists for JSON serialization
    analysis["detected_products"] = list(analysis["detected_products"])
    analysis["detected_error_codes"] = list(analysis["detected_error_codes"])

    # Display analysis results
    if RICH_AVAILABLE and console:
        # Page type distribution
        type_table = Table(title="📊 Page Type Distribution")
        type_table.add_column("Type", style="cyan")
        type_table.add_column("Count", style="green")
        type_table.add_column("Percentage", style="yellow")

        total = analysis["total_pages"]
        for page_type, count in analysis["page_types"].items():
            percentage = (count / total * 100) if total > 0 else 0
            type_table.add_row(page_type.title(), str(count), f"{percentage:.1f}%")

        console.print(type_table)

        # Detected items
        if analysis["detected_products"]:
            products_panel = Panel(
                ", ".join(analysis["detected_products"][:10])
                + ("..." if len(analysis["detected_products"]) > 10 else ""),
                title=f"🏭 Detected Products ({len(analysis['detected_products'])})",
                border_style="blue",
            )
            console.print(products_panel)

        if analysis["detected_error_codes"]:
            errors_panel = Panel(
                ", ".join(analysis["detected_error_codes"][:10])
                + ("..." if len(analysis["detected_error_codes"]) > 10 else ""),
                title=f"⚠️ Detected Error Codes ({len(analysis['detected_error_codes'])})",
                border_style="yellow",
            )
            console.print(errors_panel)

        if analysis["downloadable_resources"]:
            resources_panel = Panel(
                f"{len(analysis['downloadable_resources'])} downloadable files found",
                title="📁 Downloadable Resources",
                border_style="green",
            )
            console.print(resources_panel)
    else:
        print("\n=== Content Analysis ===")
        print(f"Total Pages: {analysis['total_pages']}")

        print("\nPage Type Distribution:")
        for page_type, count in analysis["page_types"].items():
            percentage = (count / total * 100) if total > 0 else 0
            print(f"  {page_type.title()}: {count} ({percentage:.1f}%)")

        if analysis["detected_products"]:
            print(f"\nDetected Products ({len(analysis['detected_products'])}):")
            print(
                "  "
                + ", ".join(analysis["detected_products"][:10])
                + ("..." if len(analysis["detected_products"]) > 10 else "")
            )

        if analysis["detected_error_codes"]:
            print(f"\nDetected Error Codes ({len(analysis['detected_error_codes'])}):")
            print(
                "  "
                + ", ".join(analysis["detected_error_codes"][:10])
                + ("..." if len(analysis["detected_error_codes"]) > 10 else "")
            )

        if analysis["downloadable_resources"]:
            print(f"\nDownloadable Resources: {len(analysis['downloadable_resources'])} files found")

    return analysis


async def crawl_manufacturer_products(
    manufacturer: str, product_series: str = None, max_pages: int = 50
) -> dict[str, any]:
    """
    Crawl manufacturer-specific pages with pre-configured settings.

    Args:
        manufacturer: Manufacturer name
        product_series: Optional product series filter
        max_pages: Maximum pages to crawl

    Returns:
        Crawl results
    """
    manufacturers = get_manufacturer_urls()

    if manufacturer not in manufacturers:
        available = ", ".join(manufacturers.keys())
        return {"success": False, "error": f"Unknown manufacturer: {manufacturer}. Available: {available}"}

    mfg_config = manufacturers[manufacturer]

    # Choose start URL
    if product_series:
        start_url = mfg_config["products_url"]
        print_with_rich(f"🏭 Crawling {manufacturer} {product_series} products")
    else:
        start_url = mfg_config["products_url"]
        print_with_rich(f"🏭 Crawling {manufacturer} products")

    # Configure crawl options
    options = {
        "limit": max_pages,
        "maxDepth": 2,
        "allowBackwardLinks": False,
        "includeHtml": False,
        "waitFor": 2000,
        "screenshot": False,
    }

    # Perform crawl
    result = await crawl_manufacturer_site(start_url, options)

    if result.get("success"):
        # Filter by manufacturer patterns
        pages = result.get("pages", [])
        filtered_pages = filter_urls_by_pattern(pages, mfg_config["patterns"])

        print_with_rich(f"🔍 Filtered {len(pages)} pages to {len(filtered_pages)} relevant pages")

        # Update result with filtered pages
        result["pages"] = filtered_pages
        result["filtered_count"] = len(filtered_pages)
        result["original_count"] = len(pages)

    return result


def export_crawl_results(pages: list[dict], format_type: str = "json", filename: str = None) -> str:
    """
    Export crawled data to file in specified format.

    Args:
        pages: List of crawled pages
        format_type: Export format (json, csv, markdown)
        filename: Optional custom filename

    Returns:
        Filename of exported file
    """
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"crawl_export_{timestamp}.{format_type}"

    if format_type == "json":
        export_data = {"export_timestamp": datetime.now().isoformat(), "total_pages": len(pages), "pages": pages}

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    elif format_type == "csv":
        import csv

        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["URL", "Title", "Content Length", "Depth", "Timestamp"])

            for page in pages:
                writer.writerow(
                    [
                        page.get("url", ""),
                        page.get("title", ""),
                        len(page.get("content", "")),
                        page.get("metadata", {}).get("depth", 0),
                        page.get("timestamp", ""),
                    ]
                )

    elif format_type == "markdown":
        with open(filename, "w", encoding="utf-8") as f:
            f.write("# Crawl Results Export\n\n")
            f.write(f"**Exported:** {datetime.now().isoformat()}\n")
            f.write(f"**Total Pages:** {len(pages)}\n\n")

            for i, page in enumerate(pages, 1):
                f.write(f"## {i}. {page.get('title', 'Untitled')}\n\n")
                f.write(f"**URL:** {page.get('url', '')}\n")
                f.write(f"**Content Length:** {len(page.get('content', ''))} chars\n")
                f.write(f"**Depth:** {page.get('metadata', {}).get('depth', 0)}\n\n")

                content = page.get("content", "")
                preview = content[:500] + ("..." if len(content) > 500 else "")
                f.write(f"**Content Preview:**\n\n```\n{preview}\n```\n\n")
                f.write("---\n\n")

    print_with_rich(f"💾 Exported {len(pages)} pages to: {filename}")
    return filename


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Site crawling example with URL filtering and content analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --url https://kmbs.konicaminolta.us/products/ --max-pages 20
  %(prog)s --manufacturer "Konica Minolta" --max-pages 50
  %(prog)s --url https://example.com --filter ".*product.*" --analyze
  %(prog)s --url https://example.com --export json
        """,
    )

    # URL input options
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("--url", type=str, help="Start URL for crawling")
    url_group.add_argument(
        "--manufacturer",
        type=str,
        choices=["Konica Minolta", "HP", "Canon", "Lexmark"],
        help="Manufacturer name for pre-configured crawling",
    )

    # Crawl options
    parser.add_argument("--max-pages", type=int, default=10, help="Maximum pages to crawl (default: 10)")

    parser.add_argument("--max-depth", type=int, default=2, help="Maximum crawl depth (default: 2)")

    parser.add_argument("--filter", type=str, help="URL pattern filter (regex)")

    parser.add_argument("--analyze", action="store_true", help="Analyze crawled content after crawling")

    parser.add_argument("--export", choices=["json", "csv", "markdown"], help="Export results to file")

    args = parser.parse_args()

    # Load configuration
    config = load_crawl_configuration()

    # Run the crawl operation
    async def run_crawl():
        if args.manufacturer:
            # Use manufacturer pre-configuration
            result = await crawl_manufacturer_products(args.manufacturer, max_pages=args.max_pages)
        else:
            # Use custom URL
            options = {"limit": args.max_pages, "maxDepth": args.max_depth}
            result = await crawl_manufacturer_site(args.url, options)

        if not result.get("success"):
            return result

        # Apply URL filtering if specified
        if args.filter:
            pages = result.get("pages", [])
            filtered_pages = filter_urls_by_pattern(pages, [args.filter])

            print_with_rich(f"🔍 Filtered {len(pages)} pages to {len(filtered_pages)} pages matching '{args.filter}'")
            result["pages"] = filtered_pages
            result["original_count"] = len(pages)
            result["filtered_count"] = len(filtered_pages)

        # Analyze content if requested
        if args.analyze:
            pages = result.get("pages", [])
            analysis = await analyze_crawled_content(pages)
            result["analysis"] = analysis

        # Export if requested
        if args.export:
            pages = result.get("pages", [])
            filename = export_crawl_results(pages, args.export)
            result["export_filename"] = filename

        return result

    # Execute operation
    try:
        result = asyncio.run(run_crawl())
        return result

    except KeyboardInterrupt:
        print_with_rich("\n⚠️ Crawl cancelled by user")
        return None
    except Exception as e:
        print_with_rich(f"❌ Fatal error: {e!s}")
        return None


if __name__ == "__main__":
    main()
