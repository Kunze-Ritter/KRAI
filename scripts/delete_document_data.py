"""
Delete Document Data Script
============================
Deletes ALL data associated with one or more document IDs from PostgreSQL.

This includes:
- Products
- Error Codes
- Parts
- Chunks
- Document Metadata
- All related junction tables

Usage:
    python scripts/delete_document_data.py <document_id1> [<document_id2> ...]

Examples:
    # Delete single document
    python scripts/delete_document_data.py f05a555b-626b-4e90-990e-f1108a43eccf

    # Delete multiple documents
    python scripts/delete_document_data.py f05a555b-626b-4e90-990e-f1108a43eccf 379da86a-7294-4692-99ef-8f34e8ad17ec

    # Interactive mode (prompts for confirmation)
    python scripts/delete_document_data.py --interactive
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.services.database_factory import create_database_adapter


def validate_uuid(uuid_string: str) -> bool:
    """Validate UUID format"""
    try:
        UUID(uuid_string)
        return True
    except ValueError:
        return False


async def get_document_info(adapter, document_id: str) -> dict | None:
    """Get document information"""
    try:
        doc = await adapter.get_document(document_id)
        if doc is None:
            return None

        # Convert possible Pydantic model or other representations to dict
        if hasattr(doc, "model_dump"):
            return doc.model_dump(mode="python")  # type: ignore[call-arg]
        if isinstance(doc, dict):
            return doc
        try:
            return dict(doc)
        except Exception:
            return None
    except Exception as e:
        print(f"❌ Error fetching document info: {e}")
        return None


async def count_related_data(adapter, document_id: str) -> dict:
    """Count all related data for a document"""
    counts = {}

    # Only use documented tables/columns from DATABASE_SCHEMA.md
    queries = {
        "chunks": "SELECT COUNT(*) AS count FROM krai_intelligence.chunks WHERE document_id = $1",
        "images": "SELECT COUNT(*) AS count FROM krai_content.images WHERE document_id = $1",
        "links": "SELECT COUNT(*) AS count FROM krai_content.links WHERE document_id = $1",
    }

    for key, query in queries.items():
        try:
            async with adapter.pool.acquire() as conn:
                row = await conn.fetchrow(query, document_id)
                counts[key] = row["count"] if row else 0
        except Exception as e:
            counts[key] = 0
            print(f"⚠️  Warning: Could not count {key}: {e}")

    return counts


async def delete_document_data(adapter, document_id: str, dry_run: bool = False) -> bool:
    """
    Delete all data associated with a document

    Args:
        document_id: UUID of document to delete
        dry_run: If True, only show what would be deleted

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Processing document: {document_id}")

    # Validate UUID
    if not validate_uuid(document_id):
        print(f"❌ Invalid UUID format: {document_id}")
        return False

    # Get document info
    doc_info = await get_document_info(adapter, document_id)
    if not doc_info:
        print(f"❌ Document not found: {document_id}")
        return False

    print(f"📄 Document: {doc_info.get('filename', doc_info.get('original_filename', 'Unknown'))}")
    print(f"   Manufacturer: {doc_info.get('manufacturer', 'Unknown')}")
    print(f"   Uploaded: {doc_info.get('created_at', 'Unknown')}")

    # Count related data
    print("\n📊 Related data:")
    counts = await count_related_data(adapter, document_id)
    total_items = sum(counts.values())

    for table, count in counts.items():
        if count > 0:
            print(f"   - {table}: {count} items")

    print(f"\n   Total items to delete: {total_items}")

    if dry_run:
        print("\n✓ Dry run complete (no data deleted)")
        return True

    # Delete data in correct order
    # Strategy: Delete parent first, let CASCADE handle children (faster!)
    # This avoids timeout issues with large tables like chunks
    print("\n🗑️  Deleting data...")

    try:
        async with adapter.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM krai_core.documents WHERE id = $1",
                document_id,
            )
            deleted_count = int(result.split()[-1]) if result else 0
            if deleted_count == 0:
                print(f"   ⚠️  No document row deleted for id: {document_id}")
            else:
                print(f"   ✓ Deleted document row (and cascading related data) for {document_id}")
    except Exception as e:
        print(f"   ⚠️  Error deleting document {document_id}: {e}")
        return False

    print(f"\n✅ Successfully deleted all data for document: {document_id}")
    return True


async def interactive_mode(adapter):
    """Interactive mode with document selection"""
    print("=" * 80)
    print("Interactive Document Deletion")
    print("=" * 80)

    try:
        while True:
            print("\nEnter one or more document IDs (comma-separated), or 'q' to quit.")
            user_input = input("Your selection: ").strip()

            if not user_input or user_input.lower() == "q":
                print("Cancelled.")
                return

            # Parse IDs
            raw_ids = [part.strip() for part in user_input.split(",") if part.strip()]
            if not raw_ids:
                print("❌ No valid document IDs provided")
                continue

            print("\n⚠️  WARNING: This will permanently delete all data for these documents!")
            for doc_id in raw_ids:
                print(f"  - {doc_id}")

            confirm = input("Type 'DELETE' to confirm: ").strip()
            if confirm != "DELETE":
                print("Cancelled.")
                continue

            for doc_id in raw_ids:
                await delete_document_data(adapter, doc_id, dry_run=False)

    except Exception as e:
        print(f"❌ Error in interactive mode: {e}")


async def main():
    """Main entry point"""
    try:
        adapter = create_database_adapter(database_type="postgresql")
        await adapter.initialize()
    except Exception as e:
        print(f"❌ Failed to create database adapter: {e}")
        sys.exit(1)

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nNo arguments provided. Starting interactive mode...\n")
        await interactive_mode(adapter)
        return

    # Parse arguments
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    interactive = "--interactive" in args

    if interactive:
        await interactive_mode(adapter)
        return

    # Remove flags from document IDs
    document_ids = [arg for arg in args if not arg.startswith("--")]

    if not document_ids:
        print("❌ No document IDs provided")
        print(__doc__)
        sys.exit(1)

    print("=" * 80)
    print(f"Document Data Deletion {'(DRY RUN)' if dry_run else ''}")
    print("=" * 80)

    # Process each document
    success_count = 0
    for doc_id in document_ids:
        if await delete_document_data(adapter, doc_id, dry_run=dry_run):
            success_count += 1

    # Summary
    print("\n" + "=" * 80)
    print(f"Summary: {success_count}/{len(document_ids)} documents processed successfully")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
