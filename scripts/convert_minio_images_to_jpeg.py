#!/usr/bin/env python3
"""
Convert existing MinIO PNG images to JPEG with white background.

Fetches each PNG from MinIO, converts it, re-uploads as JPEG, and updates
the storage_url in the DB.  Safe to re-run (skips already-JPEG images).

Usage:
    python scripts/convert_minio_images_to_jpeg.py
    python scripts/convert_minio_images_to_jpeg.py --dry-run
    python scripts/convert_minio_images_to_jpeg.py --limit 100
"""

import argparse
import io
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

QUALITY = 85
BUCKET = "images"


def _to_jpeg(raw_bytes: bytes) -> bytes | None:
    """Convert SVG or raster image bytes to JPEG with white background.
    Returns None on failure."""
    try:
        is_svg = raw_bytes.lstrip()[:5].lower().startswith(b"<svg")
        is_raster = raw_bytes[:4] in (b"\x89PNG", b"GIF8", b"RIFF")
        is_jpeg = raw_bytes[:2] == b"\xff\xd8"

        if is_jpeg:
            return raw_bytes  # already JPEG — caller checks magic bytes

        if is_svg:
            from reportlab.graphics import renderPM
            from svglib.svglib import svg2rlg

            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tf:
                tf.write(raw_bytes)
                tmp_path = tf.name
            try:
                drawing = svg2rlg(tmp_path)
            finally:
                os.unlink(tmp_path)

            if not drawing or drawing.width <= 0:
                print("  ✗ svglib: empty drawing")
                return None
            buf = io.BytesIO()
            renderPM.drawToFile(drawing, buf, fmt="JPEG", bg=0xFFFFFF, dpi=150)
            return buf.getvalue() if buf.tell() > 0 else None

        if is_raster:
            img = Image.open(io.BytesIO(raw_bytes))
            if img.mode in ("RGBA", "LA", "P"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=QUALITY, optimize=True)
            return buf.getvalue()

        print("  ✗ Unrecognised format")
        return None
    except Exception as e:
        print(f"  ✗ Conversion error: {e}")
        return None


def _minio_upload(minio_url_base: str, key: str, jpeg_bytes: bytes, access_key: str, secret_key: str) -> str | None:
    """Upload JPEG bytes to MinIO via boto3 S3 client and return the new public URL."""
    try:
        import boto3
        from botocore.client import Config

        endpoint = minio_url_base.rstrip("/")
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=jpeg_bytes,
            ContentType="image/jpeg",
        )
        base = os.getenv(
            "OBJECT_STORAGE_PUBLIC_URL_IMAGES", os.getenv("OBJECT_STORAGE_PUBLIC_URL", minio_url_base + "/" + BUCKET)
        )
        return f"{base.rstrip('/')}/{key}"
    except Exception as e:
        print(f"  ✗ Upload error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    db_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: POSTGRES_URL not set")
        sys.exit(1)

    minio_endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT", "http://krai-minio:9000")
    access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    limit_sql = f"LIMIT {args.limit}" if args.limit else ""
    cur.execute(
        f"""
        SELECT id, storage_url, storage_path, image_format
        FROM krai_content.images
        WHERE storage_url LIKE 'http%'
          AND (image_format ILIKE 'svg' OR storage_url ILIKE '%.svg' OR image_format IS NULL)
        ORDER BY id
        {limit_sql}
    """
    )
    rows = cur.fetchall()
    print(f"Found {len(rows)} SVG images to convert{' (DRY RUN)' if args.dry_run else ''}")

    converted = skipped = failed = 0

    with httpx.Client(timeout=30) as http:
        for i, row in enumerate(rows, 1):
            img_id = row["id"]
            url = row["storage_url"]

            # Derive MinIO object key from URL path
            # URL: http://127.0.0.1:9000/images/<hash>
            from urllib.parse import urlparse

            parsed = urlparse(url)
            path_parts = parsed.path.lstrip("/").split("/", 1)
            key = path_parts[1] if len(path_parts) == 2 else parsed.path.lstrip("/")

            # Fetch image from MinIO (use internal endpoint)
            internal_url = f"{minio_endpoint}/{BUCKET}/{key}"
            try:
                resp = http.get(internal_url)
                if resp.status_code != 200:
                    print(f"  [{i}] HTTP {resp.status_code} for {key[:40]} — skip")
                    skipped += 1
                    continue
                raw_bytes = resp.content
            except Exception as e:
                print(f"  [{i}] Fetch error: {e} — skip")
                skipped += 1
                continue

            # Skip if already JPEG
            if raw_bytes[:2] == b"\xff\xd8":
                skipped += 1
                continue

            jpeg_bytes = _to_jpeg(raw_bytes)
            if not jpeg_bytes or jpeg_bytes[:2] != b"\xff\xd8":
                failed += 1
                continue

            if args.dry_run:
                converted += 1
                if i <= 5:
                    print(f"  [{i}] Would convert {key[:50]} ({len(raw_bytes)}→{len(jpeg_bytes)} bytes)")
                continue

            # Re-upload as JPEG (same key, new content)
            new_url = _minio_upload(minio_endpoint, key, jpeg_bytes, access_key, secret_key)
            if not new_url:
                failed += 1
                continue

            # Update DB
            cur.execute(
                """
                UPDATE krai_content.images
                SET image_format = 'jpeg', storage_url = %s
                WHERE id = %s
            """,
                (new_url, img_id),
            )
            if i % 100 == 0:
                conn.commit()
                print(f"  [{i}/{len(rows)}] converted={converted} skipped={skipped} failed={failed}")
            converted += 1

    conn.commit()
    print(f"\nDone. Converted={converted}  Skipped={skipped}  Failed={failed}  Total={len(rows)}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
