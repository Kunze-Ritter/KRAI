# KRAI Schema (Live-DB)

Die **laufende PostgreSQL-Datenbank** ist die einzige Wahrheitsquelle. Dieser Ordner enthält generierte und manuell gepflegte Artefakte.

**Agent-Pflicht:** Nach jeder Schema-Änderung Docs regenerieren — siehe [`AGENTS.md`](../AGENTS.md) und [`CLAUDE.md`](../CLAUDE.md).

## Dateien

| Datei | Beschreibung |
|-------|--------------|
| `krai.dbml` | ERD für [dbdiagram.io](https://dbdiagram.io) — **automatisch generiert** |
| `column-traps.yaml` | Bekannte Spaltenfallen & Pipeline-Mapping — **manuell** |
| `.schema-hash` | Fingerprint der Live-DB (für CI-Drift-Check) |

## Dokumentation regenerieren

```bash
# Standard: introspect via Docker (krai-postgres-prod)
python scripts/generate_schema_docs.py

# Direktverbindung (.env / DATABASE_URL)
python scripts/generate_schema_docs.py --no-docker

# Prüfen ob Docs aktuell sind (Exit 1 = veraltet)
python scripts/generate_schema_docs.py --check
```

Ausgabe:

- `schema/krai.dbml`
- `DATABASE_SCHEMA.md` (Root)
- `DB_QUICK_REFERENCE.md` (Root)

## Visuelles ERD

1. [dbdiagram.io](https://dbdiagram.io) öffnen
2. **Import** → `schema/krai.dbml` hochladen
3. Layout anpassen, exportieren (PNG/PDF) optional

Änderungen an Tabellen/Spalten immer zuerst in der DB (Migration), dann Generator laufen lassen — **nicht** DBML als Schema-Wahrheit verwenden.

## Traps pflegen

Nach Umbenennungen oder JSONB-Fallen `column-traps.yaml` anpassen und Generator erneut ausführen.
