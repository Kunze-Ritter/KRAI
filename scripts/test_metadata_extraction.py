"""
Test Metadata Extraction Script
================================
Testet die Metadaten-Extraktion aus PDFs:
- Dokumenttyp-Erkennung
- Hersteller-Erkennung
- Modell-Erkennung
- Versions-Extraktion

KEINE ressourcenintensiven Prozesse:
- Keine Embeddings
- Keine Bilder
- Keine Chunks
- Nur Metadaten-Extraktion
"""

import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging

from backend.core.base_processor import ProcessingContext
from backend.processors.classification_processor import ClassificationProcessor
from backend.processors.env_loader import load_all_env_files
from backend.processors.parts_extractor import PartsExtractor
from backend.processors.parts_processor import PartsProcessor
from backend.processors.series_processor import SeriesProcessor
from backend.processors.text_extractor import TextExtractor
from backend.processors.version_extractor import VersionExtractor
from backend.services.ai_service import AIService
from backend.services.config_service import ConfigService
from backend.services.database_service import DatabaseService
from backend.utils.colored_logging import apply_colored_logging_globally


class MetadataExtractionTester:
    """Testet nur die Metadaten-Extraktion aus PDFs"""

    def __init__(self, log_file: str = None):
        """Initialize tester

        Args:
            log_file: Optional path to log file for detailed logging
        """
        apply_colored_logging_globally(level=logging.INFO)
        self.logger = logging.getLogger("metadata_tester")

        # Setup file logging if requested
        self.log_file = log_file
        if log_file:
            file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.info(f"📝 Logging to file: {log_file}")

        # Load environment
        load_all_env_files(PROJECT_ROOT)

        # Initialize services
        self.database_service = None
        self.ai_service = None
        self.config_service = None

        # Initialize extractors
        self.text_extractor = TextExtractor(prefer_engine="pymupdf", enable_ocr_fallback=False)
        self.version_extractor = VersionExtractor()
        self.parts_extractor = PartsExtractor()

        # Initialize processors (will be set up after services)
        self.parts_processor = None
        self.series_processor = None

        self.logger.info("✅ Metadata Extraction Tester initialized")

    async def initialize_services(self):
        """Initialize required services"""
        self.logger.info("Initializing services...")

        try:
            # Database service (optional - for manufacturer lookup)
            self.database_service = DatabaseService()
            await self.database_service.connect()
            self.logger.info("✅ Database service connected")
        except Exception as e:
            self.logger.warning(f"⚠️  Database service not available: {e}")
            self.database_service = None

        try:
            # AI service (for classification)
            self.ai_service = AIService()
            self.logger.info("✅ AI service initialized")
        except Exception as e:
            self.logger.warning(f"⚠️  AI service not available: {e}")
            self.ai_service = None

        try:
            # Config service
            self.config_service = ConfigService()
            self.logger.info("✅ Config service initialized")
        except Exception as e:
            self.logger.warning(f"⚠️  Config service not available: {e}")
            self.config_service = None

        # Initialize parts and series processors
        try:
            if self.database_service:
                self.parts_processor = PartsProcessor(database_adapter=self.database_service)
                self.series_processor = SeriesProcessor(database_service=self.database_service)
                self.logger.info("✅ Parts and Series processors initialized")
        except Exception as e:
            self.logger.warning(f"⚠️  Parts/Series processors not available: {e}")

    async def extract_text(self, pdf_path: Path) -> dict[str, Any]:
        """Extract text from PDF"""
        self.logger.info(f"📄 Extracting text from: {pdf_path.name}")

        try:
            from uuid import uuid4

            # Generate a temporary document_id for extraction
            temp_doc_id = uuid4()
            # extract_text returns tuple: (page_texts_dict, metadata, structured_texts)
            page_texts_dict, metadata, structured_texts = self.text_extractor.extract_text(pdf_path, temp_doc_id)

            # Build full text from pages
            full_text = "\n\n".join([page_texts_dict.get(i, "") for i in sorted(page_texts_dict.keys())])
            total_chars = len(full_text)
            page_count = len(page_texts_dict)

            self.logger.info(f"✅ Extracted {total_chars} characters from {page_count} pages")

            return {
                "full_text": full_text,
                "page_texts": page_texts_dict,
                "page_count": page_count,
                "total_chars": total_chars,
            }
        except Exception as e:
            self.logger.error(f"❌ Text extraction failed: {e}")
            return None

    async def classify_document(self, text_data: dict[str, Any], pdf_path: Path) -> dict[str, Any]:
        """Classify document type, manufacturer, and models"""
        self.logger.info("🔍 Classifying document...")

        if not self.ai_service:
            self.logger.warning("⚠️  AI service not available - skipping classification")
            return {"document_type": "Unknown", "manufacturer": "Unknown", "models": [], "confidence": 0.0}

        try:
            # Initialize classification processor
            classifier = ClassificationProcessor(
                database_service=self.database_service,
                ai_service=self.ai_service,
                features_service=None,  # Not needed for testing
            )

            # Create processing context
            context = ProcessingContext(
                file_path=str(pdf_path),
                document_id="test-doc-id",
                document_type="unknown",  # Will be determined by classifier
                page_texts=text_data["page_texts"],
            )

            # Run classification
            result = await classifier.process(context)

            if result.success:
                data = result.data
                self.logger.info(f"✅ Document Type: {data.get('document_type', 'Unknown')}")
                self.logger.info(f"✅ Manufacturer: {data.get('manufacturer', 'Unknown')}")

                models = data.get("models", [])
                if models:
                    self.logger.info(f"✅ Models: {', '.join(models)}")
                else:
                    self.logger.info("ℹ️  No models detected")

                return {
                    "document_type": data.get("document_type", "Unknown"),
                    "manufacturer": data.get("manufacturer", "Unknown"),
                    "models": models,
                    "confidence": data.get("confidence", 0.0),
                }
            self.logger.warning(f"⚠️  Classification failed: {result.message}")
            return {"document_type": "Unknown", "manufacturer": "Unknown", "models": [], "confidence": 0.0}
        except Exception as e:
            self.logger.error(f"❌ Classification error: {e}")
            return {"document_type": "Unknown", "manufacturer": "Unknown", "models": [], "confidence": 0.0}

    async def extract_version(self, text_data: dict[str, Any], manufacturer: str) -> dict[str, Any]:
        """Extract version information"""
        self.logger.info("📋 Extracting version information...")

        try:
            # Use first 5 pages for version detection
            page_texts = text_data["page_texts"]
            first_pages = sorted(page_texts.keys())[:5]
            version_text = "\n\n".join([page_texts.get(p, "") for p in first_pages if page_texts.get(p)]).strip()

            if not version_text:
                self.logger.warning("⚠️  No text available for version extraction")
                return {"version": None, "confidence": 0.0}

            # Extract version
            best_version = self.version_extractor.extract_best_version(
                version_text, manufacturer=None if manufacturer == "Unknown" else manufacturer
            )

            if best_version:
                self.logger.info(
                    f"✅ Version: {best_version.version_string} (confidence: {best_version.confidence:.2f})"
                )
                return {
                    "version_string": best_version.version_string,
                    "confidence": best_version.confidence,
                    "version_type": best_version.version_type,
                }
            self.logger.info("ℹ️  No version information found")
            return {"version_string": None, "confidence": 0.0, "version_type": None}
        except Exception as e:
            self.logger.error(f"❌ Version extraction error: {e}")
            return {"version_string": None, "confidence": 0.0, "version_type": None}

    async def extract_parts_and_accessories(self, text_data: dict[str, Any], manufacturer: str) -> dict[str, Any]:
        """Extract parts, accessories, and options from document"""
        self.logger.info("🔧 Extracting parts and accessories...")

        try:
            all_parts = []
            page_texts = text_data["page_texts"]

            # Extract parts from each page
            for page_num, page_text in page_texts.items():
                if not page_text or len(page_text.strip()) < 50:
                    continue

                parts = self.parts_extractor.extract_parts(
                    text=page_text,
                    manufacturer_name=manufacturer if manufacturer != "Unknown" else None,
                    page_number=page_num,
                )

                all_parts.extend(parts)

            if all_parts:
                self.logger.info(f"✅ Found {len(all_parts)} parts/accessories")

                # Group by type
                parts_by_type = {}
                for part in all_parts:
                    part_type = getattr(part, "part_type", "unknown")
                    if part_type not in parts_by_type:
                        parts_by_type[part_type] = []
                    parts_by_type[part_type].append(
                        {
                            "part_number": getattr(part, "part_number", ""),
                            "description": getattr(part, "description", ""),
                            "page": getattr(part, "page_number", None),
                        }
                    )

                return {
                    "total_parts": len(all_parts),
                    "parts_by_type": parts_by_type,
                    "parts_list": [
                        {
                            "part_number": getattr(p, "part_number", ""),
                            "description": getattr(p, "description", ""),
                            "type": getattr(p, "part_type", "unknown"),
                            "page": getattr(p, "page_number", None),
                        }
                        for p in all_parts[:20]
                    ],  # Limit to first 20 for display
                }
            self.logger.info("ℹ️  No parts/accessories found")
            return {"total_parts": 0, "parts_by_type": {}, "parts_list": []}
        except Exception as e:
            self.logger.error(f"❌ Parts extraction error: {e}")
            return {"total_parts": 0, "parts_by_type": {}, "parts_list": [], "error": str(e)}

    async def extract_compatibility_info(self, text_data: dict[str, Any], models: list[str]) -> dict[str, Any]:
        """Extract compatibility and relations information"""
        self.logger.info("🔗 Extracting compatibility information...")

        try:
            # Look for compatibility keywords in text
            full_text = text_data["full_text"].lower()

            compatibility_keywords = [
                "compatible",
                "compatibility",
                "works with",
                "supports",
                "for use with",
                "designed for",
                "suitable for",
                "optional",
                "accessory",
                "upgrade",
                "replacement",
            ]

            found_relations = []
            for keyword in compatibility_keywords:
                if keyword in full_text:
                    found_relations.append(keyword)

            # Extract compatibility mentions (simple pattern matching)
            compat_patterns = [
                r"compatible with[:\s]+([^.\n]+)",
                r"works with[:\s]+([^.\n]+)",
                r"for use with[:\s]+([^.\n]+)",
                r"supports[:\s]+([^.\n]+)",
            ]

            compatibility_mentions = []
            for pattern in compat_patterns:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    mention = match.group(1).strip()[:200]  # Limit length
                    if mention:
                        compatibility_mentions.append(mention)

            if found_relations or compatibility_mentions:
                self.logger.info(f"✅ Found {len(compatibility_mentions)} compatibility mentions")
                return {
                    "has_compatibility_info": True,
                    "keywords_found": found_relations,
                    "compatibility_mentions": compatibility_mentions[:10],  # Limit to 10
                    "models_referenced": models,
                }
            self.logger.info("ℹ️  No compatibility information found")
            return {
                "has_compatibility_info": False,
                "keywords_found": [],
                "compatibility_mentions": [],
                "models_referenced": models,
            }
        except Exception as e:
            self.logger.error(f"❌ Compatibility extraction error: {e}")
            return {"has_compatibility_info": False, "error": str(e)}

    async def extract_metadata_from_pdf(self, pdf_path: Path) -> dict[str, Any]:
        """Extract all metadata from a PDF"""
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"🚀 Processing: {pdf_path.name}")
        self.logger.info(f"{'='*80}\n")

        start_time = datetime.now()

        # 1. Extract text
        text_data = await self.extract_text(pdf_path)
        if not text_data:
            return None

        # 2. Classify document
        classification = await self.classify_document(text_data, pdf_path)

        # 3. Extract version
        version_info = await self.extract_version(text_data, classification["manufacturer"])

        # 4. Extract parts and accessories
        parts_info = await self.extract_parts_and_accessories(text_data, classification["manufacturer"])

        # 5. Extract compatibility information
        compatibility_info = await self.extract_compatibility_info(text_data, classification["models"])

        # Calculate processing time
        duration = (datetime.now() - start_time).total_seconds()

        # Compile results
        results = {
            "file_name": pdf_path.name,
            "file_path": str(pdf_path),
            "processing_time": f"{duration:.2f}s",
            "text_extraction": {"page_count": text_data["page_count"], "total_characters": text_data["total_chars"]},
            "classification": {
                "document_type": classification["document_type"],
                "manufacturer": classification["manufacturer"],
                "models": classification["models"],
                "confidence": classification["confidence"],
            },
            "version": {
                "version_string": version_info.get("version"),
                "confidence": version_info.get("confidence", 0.0),
                "pattern": version_info.get("pattern"),
            },
            "parts_and_accessories": parts_info,
            "compatibility": compatibility_info,
        }

        return results

    def print_results(self, results: dict[str, Any]):
        """Print results in a nice format"""
        print(f"\n{'='*80}")
        print("📊 METADATA EXTRACTION RESULTS")
        print(f"{'='*80}\n")

        print(f"📄 File: {results['file_name']}")
        print(f"⏱️  Processing Time: {results['processing_time']}")
        print()

        print("📝 Text Extraction:")
        print(f"   - Pages: {results['text_extraction']['page_count']}")
        print(f"   - Characters: {results['text_extraction']['total_characters']:,}")
        print()

        print("🔍 Classification:")
        print(f"   - Document Type: {results['classification']['document_type']}")
        print(f"   - Manufacturer: {results['classification']['manufacturer']}")
        print(
            f"   - Models: {', '.join(results['classification']['models']) if results['classification']['models'] else 'None'}"
        )
        print(f"   - Confidence: {results['classification']['confidence']:.2%}")
        print()

        print("📋 Version:")
        version = results["version"]["version_string"]
        if version:
            print(f"   - Version: {version}")
            print(f"   - Confidence: {results['version']['confidence']:.2%}")
            print(f"   - Pattern: {results['version']['pattern']}")
        else:
            print("   - Version: Not found")
        print()

        print("🔧 Parts & Accessories:")
        parts = results["parts_and_accessories"]
        if parts.get("total_parts", 0) > 0:
            print(f"   - Total Parts Found: {parts['total_parts']}")
            if parts.get("parts_by_type"):
                print("   - By Type:")
                for part_type, type_parts in parts["parts_by_type"].items():
                    print(f"     • {part_type}: {len(type_parts)} items")
            if parts.get("parts_list"):
                print("   - Sample Parts (first 5):")
                for i, part in enumerate(parts["parts_list"][:5], 1):
                    print(f"     {i}. {part['part_number']} - {part['description'][:60]}...")
        else:
            print("   - No parts/accessories found")
        print()

        print("🔗 Compatibility:")
        compat = results["compatibility"]
        if compat.get("has_compatibility_info"):
            print("   - Has Compatibility Info: Yes")
            if compat.get("keywords_found"):
                print(f"   - Keywords: {', '.join(compat['keywords_found'][:5])}")
            if compat.get("compatibility_mentions"):
                print(f"   - Mentions Found: {len(compat['compatibility_mentions'])}")
                print("   - Sample Mentions:")
                for i, mention in enumerate(compat["compatibility_mentions"][:3], 1):
                    print(f"     {i}. {mention[:80]}...")
        else:
            print("   - No compatibility information found")

        print(f"\n{'='*80}\n")

    async def test_single_pdf(self, pdf_path: str):
        """Test a single PDF file"""
        pdf_file = Path(pdf_path)

        if not pdf_file.exists():
            self.logger.error(f"❌ File not found: {pdf_path}")
            return

        if pdf_file.suffix.lower() != ".pdf":
            self.logger.error(f"❌ Not a PDF file: {pdf_path}")
            return

        # Initialize services
        await self.initialize_services()

        # Extract metadata
        results = await self.extract_metadata_from_pdf(pdf_file)

        if results:
            # Print results
            self.print_results(results)

            # Save to JSON
            output_file = pdf_file.parent / f"{pdf_file.stem}_metadata.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            self.logger.info(f"💾 Results saved to: {output_file}")

        # Cleanup
        if self.database_service:
            await self.database_service.disconnect()

    async def test_directory(self, directory_path: str):
        """Test all PDFs in a directory (including subdirectories)"""
        directory = Path(directory_path)

        if not directory.exists() or not directory.is_dir():
            self.logger.error(f"❌ Directory not found: {directory_path}")
            return

        # Find all PDFs recursively
        pdf_files = list(directory.rglob("*.pdf"))

        if not pdf_files:
            self.logger.warning(f"⚠️  No PDF files found in: {directory_path}")
            return

        self.logger.info(f"📁 Found {len(pdf_files)} PDF files")

        # Initialize services
        await self.initialize_services()

        # Process each PDF
        all_results = []
        for pdf_file in pdf_files:
            results = await self.extract_metadata_from_pdf(pdf_file)
            if results:
                all_results.append(results)
                self.print_results(results)

        # Save combined results
        if all_results:
            output_file = directory / f"metadata_extraction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)

            self.logger.info(f"💾 Combined results saved to: {output_file}")

        # Cleanup
        if self.database_service:
            await self.database_service.disconnect()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test Metadata Extraction from PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test single PDF
  python test_metadata_extraction.py --file path/to/document.pdf

  # Test all PDFs in directory
  python test_metadata_extraction.py --directory path/to/pdfs/

  # Test with input_pdfs directory
  python test_metadata_extraction.py --directory input_pdfs
        """,
    )

    parser.add_argument("--file", type=str, help="Path to a single PDF file to test")

    parser.add_argument("--directory", type=str, help="Path to directory containing PDF files")

    parser.add_argument(
        "--log-file",
        type=str,
        default="metadata_extraction.log",
        help="Path to log file (default: metadata_extraction.log)",
    )

    args = parser.parse_args()

    if not args.file and not args.directory:
        parser.print_help()
        print("\n❌ Error: Please specify either --file or --directory")
        sys.exit(1)

    tester = MetadataExtractionTester(log_file=args.log_file)

    if args.file:
        await tester.test_single_pdf(args.file)
    elif args.directory:
        await tester.test_directory(args.directory)


if __name__ == "__main__":
    asyncio.run(main())
