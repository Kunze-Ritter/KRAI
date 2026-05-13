"""
File Locator Service - Intelligently finds document files
Cross-platform support for Windows, Mac, Linux
"""

import logging
import os
from pathlib import Path


class FileLocatorService:
    """
    Intelligent file location service

    Searches for documents in multiple locations:
    - Environment variable path
    - Project relative paths
    - Common system paths
    - Custom configured paths
    """

    def __init__(self):
        self.logger = logging.getLogger("krai.file_locator")

        # Get search paths from environment or use defaults
        custom_path = os.getenv("DOCUMENT_STORAGE_PATH")

        # Build search paths (in priority order)
        self.search_paths = []

        # 1. Custom path from environment
        if custom_path:
            self.search_paths.append(custom_path)

        # 2. Project-relative paths
        script_dir = Path(__file__).parent.parent.parent.resolve()
        self.search_paths.extend(
            [script_dir / "service_documents", script_dir / "documents", script_dir / "pdfs", script_dir / "uploads"]
        )

        # 3. Common system paths (cross-platform)
        if os.name == "nt":  # Windows
            self.search_paths.extend(
                [
                    Path("C:/service_documents"),
                    Path("C:/documents"),
                    Path.home() / "Documents" / "service_documents",
                    Path.home() / "Desktop" / "service_documents",
                ]
            )
        else:  # Linux/Mac
            self.search_paths.extend(
                [
                    Path("/var/data/service_documents"),
                    Path("/opt/service_documents"),
                    Path.home() / "service_documents",
                    Path.home() / "Documents" / "service_documents",
                ]
            )

        # 4. Docker/Container paths
        self.search_paths.extend(
            [Path("/app/service_documents"), Path("/data/service_documents"), Path("/mnt/documents")]
        )

        # Convert all to absolute paths and deduplicate
        self.search_paths = list(dict.fromkeys([Path(p).resolve() for p in self.search_paths if p]))

        self.logger.info(f"File Locator initialized with {len(self.search_paths)} search paths")

    def find_file(self, filename: str) -> str | None:
        """
        Find a file by searching all configured paths

        Args:
            filename: Name of the file to find

        Returns:
            Absolute path to file, or None if not found
        """
        if not filename:
            return None

        # If filename is already an absolute path that exists, return it
        if os.path.isabs(filename) and os.path.exists(filename):
            self.logger.debug(f"File already absolute and exists: {filename}")
            return filename

        # Search in all configured paths
        for search_path in self.search_paths:
            file_path = search_path / filename

            if file_path.exists() and file_path.is_file():
                self.logger.info(f"Found file: {filename} at {file_path}")
                return str(file_path)

        # Not found
        self.logger.warning(f"File not found: {filename}")
        self.logger.debug(f"Searched in: {[str(p) for p in self.search_paths[:5]]}")
        return None

    def find_directory(self, directory_hint: str | None = None) -> str | None:
        """
        Find the main documents directory

        Args:
            directory_hint: Optional hint for directory name

        Returns:
            Path to documents directory, or None
        """
        for search_path in self.search_paths:
            if search_path.exists() and search_path.is_dir():
                # Check if it has PDF files
                pdf_files = list(search_path.glob("*.pdf"))
                if pdf_files:
                    self.logger.info(f"Found documents directory: {search_path} ({len(pdf_files)} PDFs)")
                    return str(search_path)

        self.logger.warning("No documents directory found with PDF files")
        return None

    def list_search_paths(self) -> list[str]:
        """Get list of all search paths being used"""
        return [str(p) for p in self.search_paths]

    def add_search_path(self, path: str):
        """Add a custom search path"""
        path_obj = Path(path).resolve()
        if path_obj not in self.search_paths:
            self.search_paths.insert(0, path_obj)  # Add at beginning (highest priority)
            self.logger.info(f"Added search path: {path_obj}")

    def get_statistics(self) -> dict:
        """Get statistics about search paths"""
        stats = {
            "total_paths": len(self.search_paths),
            "existing_paths": 0,
            "paths_with_pdfs": 0,
            "total_pdfs": 0,
            "paths": [],
        }

        for search_path in self.search_paths:
            path_info = {
                "path": str(search_path),
                "exists": search_path.exists(),
                "is_dir": search_path.is_dir() if search_path.exists() else False,
                "pdf_count": 0,
            }

            if path_info["exists"]:
                stats["existing_paths"] += 1

            if path_info["is_dir"]:
                pdf_files = list(search_path.glob("*.pdf"))
                path_info["pdf_count"] = len(pdf_files)

                if pdf_files:
                    stats["paths_with_pdfs"] += 1
                    stats["total_pdfs"] += len(pdf_files)

            stats["paths"].append(path_info)

        return stats

    def print_debug_info(self):
        """Print debug information about file locations"""
        print("\n" + "=" * 60)
        print("🔍 FILE LOCATOR DEBUG INFO")
        print("=" * 60)

        stats = self.get_statistics()

        print(f"\nSearch Paths: {stats['total_paths']}")
        print(f"Existing Paths: {stats['existing_paths']}")
        print(f"Paths with PDFs: {stats['paths_with_pdfs']}")
        print(f"Total PDFs Found: {stats['total_pdfs']}")

        print("\nSearch Path Details:")
        for i, path_info in enumerate(stats["paths"][:10], 1):  # Show first 10
            status = "✅" if path_info["exists"] else "❌"
            pdf_info = f" ({path_info['pdf_count']} PDFs)" if path_info["pdf_count"] > 0 else ""
            print(f"{i:2}. {status} {path_info['path']}{pdf_info}")

        if len(stats["paths"]) > 10:
            print(f"    ... and {len(stats['paths']) - 10} more paths")

        # Environment variables
        print("\nEnvironment Variables:")
        doc_path = os.getenv("DOCUMENT_STORAGE_PATH")
        if doc_path:
            print(f"  DOCUMENT_STORAGE_PATH = {doc_path}")
        else:
            print("  DOCUMENT_STORAGE_PATH = (not set)")

        print("\nTo set custom path:")
        print("  Windows: set DOCUMENT_STORAGE_PATH=C:\\your\\path")
        print("  Linux/Mac: export DOCUMENT_STORAGE_PATH=/your/path")
        print("  .env file: DOCUMENT_STORAGE_PATH=/your/path")

        print("=" * 60 + "\n")
