"""
Lokaler Agent-Test (Windows, ohne Docker-Rebuild)
==================================================
Testet den KRAI LangGraph-Agent direkt gegen die laufenden Docker-Services
(PostgreSQL und Ollama sind über localhost erreichbar).

Voraussetzung:
    Zuerst einmalig ausführen:  install_agent_deps.bat

Dann:
    backend\venv\\Scripts\\python.exe test_agent_local.py
"""

import asyncio
import os
import sys

# Pfad zum Backend-Code
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

# Docker-Hostnamen durch localhost ersetzen
os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
os.environ.setdefault("OLLAMA_MODEL_CHAT", "llama3.2:3b")
os.environ.setdefault("OLLAMA_MODEL_EMBED", "nomic-embed-text")

from pathlib import Path

# .env laden für DB-Credentials
from processors.env_loader import load_all_env_files

load_all_env_files(Path(__file__).parent)
# Hostname-Überschreibung (Docker-intern → Windows-localhost)
os.environ["OLLAMA_URL"] = "http://localhost:11434"

import asyncpg

POSTGRES_URL = (os.getenv("POSTGRES_URL") or "postgresql://krai_user:Krai_Secure_Pass123!@localhost:5432/krai").replace(
    "krai-postgres", "localhost"
)


TEST_CASES = [
    ("test-1", "Hallo! Was kannst du?"),
    ("test-1", "Gibt es den Fehlercode C9402?"),
    ("test-1", "Zeig mir Ersatzteile für Lexmark"),
    ("test-2", "Suche Videos zum Fuser tauschen bei HP"),
]


async def run():
    print("=" * 60)
    print("  KRAI Agent – Lokaler Test")
    print("=" * 60)

    # DB-Verbindung prüfen
    print(f"\n📦 Verbinde mit PostgreSQL: {POSTGRES_URL[:50]}...")
    try:
        pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=3)
        row = await pool.fetchval("SELECT COUNT(*) FROM krai_intelligence.error_codes")
        print(f"   ✅ DB OK – {row} Fehlercodes in der Datenbank")
    except Exception as e:
        print(f"   ❌ DB-Fehler: {e}")
        print("   Läuft der Docker-Container? docker-compose -f docker-compose.simple.yml up -d krai-postgres")
        return

    # Ollama-Verbindung prüfen
    import httpx

    print(f"\n🤖 Verbinde mit Ollama: {os.environ['OLLAMA_URL']} ...")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{os.environ['OLLAMA_URL']}/api/tags")
        models = [m["name"] for m in resp.json().get("models", [])]
        print(f"   ✅ Ollama OK – verfügbare Modelle: {', '.join(models[:5])}")
        chat_model = os.environ["OLLAMA_MODEL_CHAT"]
        if not any(chat_model in m for m in models):
            print(f"   ⚠️  Modell '{chat_model}' nicht geladen! Prüfe: ollama pull {chat_model}")
    except Exception as e:
        print(f"   ❌ Ollama-Fehler: {e}")
        print("   Läuft Ollama? docker-compose -f docker-compose.simple.yml up -d krai-ollama")
        return

    # Agent initialisieren
    print("\n🚀 Initialisiere Agent...")
    try:
        from api.agent_api import KRAIAgent

        agent = KRAIAgent(pool, ollama_base_url=os.environ["OLLAMA_URL"])
        print("   ✅ Agent initialisiert")
    except Exception as e:
        print(f"   ❌ Agent-Fehler: {e}")
        import traceback

        traceback.print_exc()
        return

    # Test-Gespräche
    print("\n" + "=" * 60)
    print("  Test-Gespräche")
    print("=" * 60)

    for session_id, message in TEST_CASES:
        print(f"\n[Session: {session_id}] 👤 User: {message}")
        try:
            response = await agent.chat(message, session_id)
            print(f"               🤖 Agent: {response[:300]}")
            if len(response) > 300:
                print(f"                         ... ({len(response)} Zeichen gesamt)")
        except Exception as e:
            print(f"               ❌ Fehler: {e}")

    await pool.close()
    print("\n✅ Test abgeschlossen!")


if __name__ == "__main__":
    asyncio.run(run())
