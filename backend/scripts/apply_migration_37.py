#!/usr/bin/env python3
"""Apply migration 37: error_code_images junction table"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

print("=" * 80)
print("APPLYING MIGRATION 37: error_code_images junction table")
print("=" * 80)

# Read migration file
migration_file = (
    Path(__file__).parent.parent.parent / "database" / "migrations" / "37_create_error_code_images_junction.sql"
)

if not migration_file.exists():
    print(f"❌ Migration file not found: {migration_file}")
    sys.exit(1)

with open(migration_file, encoding="utf-8") as f:
    sql = f.read()

print(f"\n📝 Migration file: {migration_file.name}")
print(f"   Size: {len(sql)} bytes")

# Try psycopg2
try:
    import psycopg2

    # Get connection string
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")

    if not db_url:
        print("\n❌ No DATABASE_URL or SUPABASE_DB_URL found in .env")
        print("\n💡 Add to .env:")
        print("   DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres")
        sys.exit(1)

    print("\n🚀 Connecting to database...")
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    print("✅ Connected!")
    print("\n🔧 Executing migration...")

    cur.execute(sql)
    conn.commit()

    print("✅ Migration executed successfully!")

    # Verify table exists
    cur.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.tables
        WHERE table_schema = 'krai_intelligence'
        AND table_name = 'error_code_images'
    """
    )

    count = cur.fetchone()[0]
    if count > 0:
        print("\n✅ Table 'error_code_images' created successfully!")
    else:
        print("\n⚠️  Table verification failed")

    cur.close()
    conn.close()

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. Run: python scripts/link_error_codes_to_images.py")
    print("2. Update N8N workflow to use new junction table")
    print("=" * 80)

except ImportError:
    print("\n❌ psycopg2 not installed")
    print("\n💡 Install with:")
    print("   pip install psycopg2-binary")
    print("\n📋 Or run SQL manually in PostgreSQL client (psql or pgAdmin):")
    print(f"   File: {migration_file}")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    print("\n📋 Please run SQL manually in PostgreSQL client (psql or pgAdmin):")
    print(f"   File: {migration_file}")
    sys.exit(1)
