#!/usr/bin/env python3
"""
Error Code Extraction Testing Script
Tests extraction quality across different manufacturers and settings
"""

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import uuid4

from backend.processors.error_code_extractor import ErrorCodeExtractor
from backend.processors.text_extractor import extract_text_from_pdf
from backend.utils.colored_logging import setup_colored_logging

logger = setup_colored_logging(__name__)


class ErrorCodeExtractionTester:
    """Test error code extraction with different configurations"""

    def __init__(self):
        self.extractor = ErrorCodeExtractor()
        self.results = []

    def test_pdf(self, pdf_path: str, manufacturer: str = None, test_name: str = None) -> dict[str, Any]:
        """
        Test error code extraction on a PDF

        Args:
            pdf_path: Path to PDF file
            manufacturer: Manufacturer name (for pattern selection)
            test_name: Name for this test

        Returns:
            Test results dict
        """
        logger.info(f"🧪 Testing: {pdf_path}")

        if not os.path.exists(pdf_path):
            logger.error(f"PDF not found: {pdf_path}")
            return {"error": "PDF not found"}

        try:
            # Extract text from PDF
            from pathlib import Path

            document_id = uuid4()
            pdf_text, metadata = extract_text_from_pdf(
                pdf_path=Path(pdf_path), document_id=document_id, engine="pymupdf"
            )

            if not pdf_text:
                logger.error("Failed to extract text from PDF")
                return {"error": "Text extraction failed"}

            # Get manufacturer from filename if not provided
            if not manufacturer:
                manufacturer = self._guess_manufacturer(pdf_path)

            # Extract error codes from each page
            all_error_codes = []
            total_pages = len(pdf_text)

            # Import exception for proper handling
            from backend.processors.exceptions import ManufacturerPatternNotFoundError

            for page_num, page_text in pdf_text.items():
                try:
                    error_codes = self.extractor.extract_from_text(
                        text=page_text, page_number=page_num, manufacturer_name=manufacturer
                    )

                    if error_codes:
                        all_error_codes.extend(error_codes)
                        logger.info(f"  Page {page_num}: Found {len(error_codes)} error codes")

                except ManufacturerPatternNotFoundError as e:
                    # Re-raise pattern errors - these should stop processing
                    logger.error(f"\n{e}")
                    return {"error": str(e), "test_name": test_name or Path(pdf_path).stem}
                except Exception as e:
                    logger.debug(f"  Page {page_num}: Error - {e}")
                    continue

            # Compile results
            result = {
                "test_name": test_name or Path(pdf_path).stem,
                "pdf_path": pdf_path,
                "manufacturer": manufacturer,
                "total_pages": total_pages,
                "error_codes_found": len(all_error_codes),
                "unique_codes": len(set(ec.error_code for ec in all_error_codes)),
                "with_solution": len([ec for ec in all_error_codes if ec.solution_text]),
                "with_description": len([ec for ec in all_error_codes if ec.error_description]),
                "avg_confidence": (
                    sum(ec.confidence for ec in all_error_codes) / len(all_error_codes) if all_error_codes else 0
                ),
                "error_codes": [],
            }

            # Add detailed error code info
            for ec in all_error_codes[:50]:  # Limit to first 50 for readability
                result["error_codes"].append(
                    {
                        "code": ec.error_code,
                        "page": ec.page_number,
                        "description": (
                            ec.error_description[:100] + "..."
                            if len(ec.error_description or "") > 100
                            else ec.error_description
                        ),
                        "solution_length": len(ec.solution_text or ""),
                        "has_solution": bool(ec.solution_text),
                        "confidence": round(ec.confidence, 2),
                        "extraction_method": ec.extraction_method,
                    }
                )

            logger.success(f"✅ Found {len(all_error_codes)} error codes ({result['unique_codes']} unique)")
            logger.info(f"   Solutions: {result['with_solution']}/{len(all_error_codes)}")
            logger.info(f"   Avg Confidence: {result['avg_confidence']:.2f}")

            return result

        except Exception as e:
            logger.error(f"Test failed: {e}")
            traceback.print_exc()
            return {"error": str(e)}

    def test_batch(self, pdf_directory: str, pattern: str = "*.pdf") -> list[dict[str, Any]]:
        """
        Test multiple PDFs in a directory

        Args:
            pdf_directory: Directory containing PDFs
            pattern: Glob pattern for PDF files

        Returns:
            List of test results
        """
        pdf_dir = Path(pdf_directory)

        if not pdf_dir.exists():
            logger.error(f"Directory not found: {pdf_directory}")
            return []

        pdf_files = list(pdf_dir.glob(pattern))
        logger.info(f"📂 Found {len(pdf_files)} PDF files")

        results = []
        for i, pdf_path in enumerate(pdf_files, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"Test {i}/{len(pdf_files)}: {pdf_path.name}")
            logger.info(f"{'='*60}")

            result = self.test_pdf(str(pdf_path))
            results.append(result)

        return results

    def test_single_page_text(self, text: str, manufacturer: str, page_number: int = 1) -> list:
        """
        Test extraction on a single page text

        Args:
            text: Page text content
            manufacturer: Manufacturer name
            page_number: Page number

        Returns:
            Extracted error codes
        """
        try:
            error_codes = self.extractor.extract_error_codes(
                text=text, page_number=page_number, manufacturer=manufacturer
            )

            logger.info(f"Found {len(error_codes)} error codes")

            for ec in error_codes:
                logger.info(f"\n  Code: {ec.error_code}")
                logger.info(f"  Description: {ec.error_description[:80]}...")
                logger.info(f"  Solution: {len(ec.solution_text or 0)} chars")
                logger.info(f"  Confidence: {ec.confidence:.2f}")

            return error_codes

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            traceback.print_exc()
            return []

    def _guess_manufacturer(self, pdf_path: str) -> str:
        """Guess manufacturer from filename"""
        filename = Path(pdf_path).name.lower()

        manufacturers = {
            "hp": ["hp", "hewlett"],
            "canon": ["canon"],
            "konica_minolta": ["konica", "minolta", "bizhub"],
            "ricoh": ["ricoh"],
            "brother": ["brother"],
            "xerox": ["xerox"],
            "lexmark": ["lexmark"],
            "kyocera": ["kyocera"],
            "sharp": ["sharp"],
            "epson": ["epson"],
        }

        for mfr, keywords in manufacturers.items():
            if any(kw in filename for kw in keywords):
                logger.info(f"  Detected manufacturer: {mfr}")
                return mfr

        logger.warning("  Manufacturer not detected, using 'generic'")
        return "generic"

    def generate_report(self, results: list[dict[str, Any]], output_file: str = None):
        """
        Generate test report

        Args:
            results: List of test results
            output_file: Optional output file path
        """
        if not results:
            logger.warning("No results to report")
            return

        # Calculate statistics
        total_pdfs = len(results)
        total_codes = sum(r.get("error_codes_found", 0) for r in results)
        total_unique = sum(r.get("unique_codes", 0) for r in results)
        total_with_solution = sum(r.get("with_solution", 0) for r in results)
        avg_confidence = sum(r.get("avg_confidence", 0) for r in results) / total_pdfs if total_pdfs else 0

        report = f"""
{'='*80}
ERROR CODE EXTRACTION TEST REPORT
{'='*80}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

SUMMARY
-------
Total PDFs tested:        {total_pdfs}
Total error codes found:  {total_codes}
Unique error codes:       {total_unique}
Codes with solutions:     {total_with_solution} ({total_with_solution/total_codes*100 if total_codes else 0:.1f}%)
Average confidence:       {avg_confidence:.2f}

DETAILED RESULTS
----------------
"""

        for i, result in enumerate(results, 1):
            if "error" in result:
                report += f"\n{i}. {result.get('test_name', 'Unknown')} - ERROR: {result['error']}\n"
                continue

            report += f"""
{i}. {result['test_name']}
   Manufacturer:    {result['manufacturer']}
   Pages:           {result['total_pages']}
   Codes found:     {result['error_codes_found']} ({result['unique_codes']} unique)
   With solutions:  {result['with_solution']} ({result['with_solution']/result['error_codes_found']*100 if result['error_codes_found'] else 0:.1f}%)
   With desc.:      {result['with_description']} ({result['with_description']/result['error_codes_found']*100 if result['error_codes_found'] else 0:.1f}%)
   Avg confidence:  {result['avg_confidence']:.2f}
"""

            # Show top 5 error codes
            if result.get("error_codes"):
                report += "   Top codes:\n"
                for ec in result["error_codes"][:5]:
                    solution_status = "✓" if ec["has_solution"] else "✗"
                    report += f"     [{solution_status}] {ec['code']} (p.{ec['page']}, conf: {ec['confidence']})\n"

        report += f"\n{'='*80}\n"

        print(report)

        # Save to file if specified
        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(report)
            logger.success(f"Report saved to: {output_file}")

        # Also save JSON
        if output_file:
            json_file = output_file.replace(".txt", ".json")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)
            logger.success(f"JSON data saved to: {json_file}")


def main():
    """Main test function"""
    import argparse

    parser = argparse.ArgumentParser(description="Test error code extraction")
    parser.add_argument("--pdf", help="Single PDF file to test")
    parser.add_argument("--directory", help="Directory with PDFs to test")
    parser.add_argument("--manufacturer", help="Manufacturer name (hp, konica_minolta, canon, etc.)")
    parser.add_argument("--output", help="Output report file", default="error_code_test_report.txt")
    parser.add_argument("--pattern", help="File pattern for batch test", default="*.pdf")

    args = parser.parse_args()

    tester = ErrorCodeExtractionTester()
    results = []

    if args.pdf:
        # Test single PDF
        result = tester.test_pdf(args.pdf, args.manufacturer)
        results = [result]

    elif args.directory:
        # Test batch
        results = tester.test_batch(args.directory, args.pattern)

    else:
        print("Please specify --pdf or --directory")
        parser.print_help()
        return

    # Generate report
    tester.generate_report(results, args.output)


if __name__ == "__main__":
    main()
