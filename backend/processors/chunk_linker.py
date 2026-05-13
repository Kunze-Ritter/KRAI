"""
Chunk Linker Module
Verknüpft Error Codes mit Intelligence Chunks für Bilder-Support

Wiederverwendbar für:
- Error Code Processing
- Video Processing
- Parts Processing
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def find_chunk_for_error_code(
    error_code: str, page_number: int, chunks: list[dict[str, Any]], verbose: bool = False
) -> str | None:
    """
    Findet den Intelligence Chunk der diesen Error Code enthält

    Strategie:
    1. Bevorzuge Chunks auf gleicher Seite die den Error Code enthalten
    2. Fallback: Beliebiger Chunk der den Error Code enthält
    3. None wenn nicht gefunden

    Args:
        error_code: Der Error Code (z.B. "66.60.32")
        page_number: Seite wo Error Code gefunden wurde
        chunks: Liste von Chunk-Dicts aus DB
        verbose: Logging aktivieren

    Returns:
        chunk_id (UUID als String) oder None

    Example:
        >>> chunks = db.table('vw_intelligence_chunks').select('id, text_chunk, page_start').execute()
        >>> chunk_id = find_chunk_for_error_code("66.60.32", 43, chunks.data)
        >>> if chunk_id:
        >>>     error_code.chunk_id = chunk_id
    """
    if not chunks:
        if verbose:
            logger.debug(f"No chunks provided for {error_code}")
        return None

    # Strategie 1: Gleiche Seite + enthält Error Code
    for chunk in chunks:
        chunk_page = chunk.get("page_start") or chunk.get("page_number")
        chunk_text = chunk.get("text_chunk", "")
        chunk_id = chunk.get("id")

        if chunk_page == page_number and error_code in chunk_text and chunk_id:
            if verbose:
                logger.info(f"✅ Found chunk for {error_code} on page {page_number}")
            return str(chunk_id)

    # Strategie 2: Beliebiger Chunk mit Error Code
    for chunk in chunks:
        chunk_text = chunk.get("text_chunk", "")
        chunk_id = chunk.get("id")

        if error_code in chunk_text and chunk_id:
            chunk_page = chunk.get("page_start") or chunk.get("page_number")
            if verbose:
                logger.info(f"✅ Found chunk for {error_code} on page {chunk_page} (different from {page_number})")
            return str(chunk_id)

    if verbose:
        logger.warning(f"⚠️ No chunk found for {error_code}")
    return None


def link_error_codes_to_chunks(error_codes: list[Any], chunks: list[dict[str, Any]], verbose: bool = False) -> int:
    """
    Verknüpft eine Liste von Error Codes mit ihren Chunks

    Setzt error_code.chunk_id für jeden Error Code der einen passenden Chunk hat.

    Args:
        error_codes: Liste von ExtractedErrorCode Objekten
        chunks: Liste von Chunk-Dicts aus DB
        verbose: Logging aktivieren

    Returns:
        Anzahl der erfolgreich verknüpften Error Codes

    Example:
        >>> error_codes = extractor.extract_from_text(text, page)
        >>> chunks = db.table('vw_intelligence_chunks').select('*').execute()
        >>> linked_count = link_error_codes_to_chunks(error_codes, chunks.data)
        >>> print(f"Linked {linked_count}/{len(error_codes)} error codes")
    """
    if not error_codes or not chunks:
        return 0

    linked_count = 0

    for error_code in error_codes:
        # Skip if already has chunk_id
        if hasattr(error_code, "chunk_id") and error_code.chunk_id:
            continue

        chunk_id = find_chunk_for_error_code(
            error_code=error_code.error_code, page_number=error_code.page_number, chunks=chunks, verbose=verbose
        )

        if chunk_id:
            error_code.chunk_id = chunk_id
            linked_count += 1
            if verbose:
                logger.debug(f"Linked {error_code.error_code} → chunk {chunk_id[:8]}...")

    if verbose:
        logger.info(f"📎 Linked {linked_count}/{len(error_codes)} error codes to chunks")

    return linked_count


def find_chunks_with_images(chunks: list[dict[str, Any]], images_table_data: list[dict[str, Any]]) -> list[str]:
    """
    Findet alle Chunk IDs die Bilder haben

    Nützlich um zu prüfen welche Chunks Bilder haben bevor man verknüpft.

    Args:
        chunks: Liste von Chunk-Dicts
        images_table_data: Liste von Image-Dicts aus krai_content.images

    Returns:
        Liste von chunk_ids (als Strings) die Bilder haben

    Example:
        >>> chunks = db.table('vw_intelligence_chunks').select('id').execute()
        >>> images = db.table('vw_images').select('chunk_id').execute()
        >>> chunk_ids_with_images = find_chunks_with_images(chunks.data, images.data)
        >>> print(f"{len(chunk_ids_with_images)} chunks have images")
    """
    # Extrahiere alle chunk_ids aus images
    image_chunk_ids = set()
    for img in images_table_data:
        chunk_id = img.get("chunk_id")
        if chunk_id:
            image_chunk_ids.add(str(chunk_id))

    # Finde chunks die in diesem Set sind
    chunks_with_images = []
    for chunk in chunks:
        chunk_id = chunk.get("id")
        if chunk_id and str(chunk_id) in image_chunk_ids:
            chunks_with_images.append(str(chunk_id))

    return chunks_with_images


def validate_chunk_linking(
    error_codes: list[Any], chunks: list[dict[str, Any]], images_table_data: list[dict[str, Any]]
) -> dict[str, int]:
    """
    Validiert die Chunk-Verknüpfung und gibt Statistiken zurück

    Args:
        error_codes: Liste von ExtractedErrorCode Objekten
        chunks: Liste von Chunk-Dicts
        images_table_data: Liste von Image-Dicts

    Returns:
        Dict mit Statistiken:
        - total_errors: Gesamtzahl Error Codes
        - with_chunk_id: Anzahl mit chunk_id
        - without_chunk_id: Anzahl ohne chunk_id
        - chunks_with_images: Anzahl Chunks die Bilder haben
        - errors_with_images: Anzahl Error Codes die Bilder haben (via chunk_id)

    Example:
        >>> stats = validate_chunk_linking(error_codes, chunks.data, images.data)
        >>> print(f"{stats['errors_with_images']} error codes have images")
    """
    chunks_with_images = set(find_chunks_with_images(chunks, images_table_data))

    total_errors = len(error_codes)
    with_chunk_id = sum(1 for ec in error_codes if hasattr(ec, "chunk_id") and ec.chunk_id)
    without_chunk_id = total_errors - with_chunk_id

    errors_with_images = sum(
        1 for ec in error_codes if hasattr(ec, "chunk_id") and ec.chunk_id and ec.chunk_id in chunks_with_images
    )

    return {
        "total_errors": total_errors,
        "with_chunk_id": with_chunk_id,
        "without_chunk_id": without_chunk_id,
        "chunks_with_images": len(chunks_with_images),
        "errors_with_images": errors_with_images,
        "linking_rate": (with_chunk_id / total_errors * 100) if total_errors > 0 else 0,
        "image_rate": (errors_with_images / total_errors * 100) if total_errors > 0 else 0,
    }


# Convenience function für schnellen Import
__all__ = [
    "find_chunk_for_error_code",
    "find_chunks_with_images",
    "link_error_codes_to_chunks",
    "validate_chunk_linking",
]
