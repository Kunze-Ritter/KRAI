"""
Product Research Module
=======================

AI-powered online research for automatic product specs extraction. Supports
Firecrawl (JavaScript rendering, Markdown output) with automatic fallback to
BeautifulSoup.
"""

from .product_researcher import ProductResearcher
from .research_integration import ResearchIntegration

__all__ = ["ProductResearcher", "ResearchIntegration"]
