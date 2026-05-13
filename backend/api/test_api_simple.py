"""
Einfacher API Tester - Ohne Browser!

Testet alle API Endpoints direkt in Python.
"""

from pathlib import Path
from time import sleep

import requests


class SimpleAPITester:
    """Einfacher API Tester"""

    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.document_id = None

    def print_header(self, title):
        """Print schöner Header"""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80)

    def print_result(self, success, message):
        """Print Result"""
        if success:
            print(f"  ✅ {message}")
        else:
            print(f"  ❌ {message}")

    def test_connection(self):
        """Test 1: Ist die API erreichbar?"""
        self.print_header("TEST 1: API Connection")

        try:
            response = requests.get(f"{self.base_url}/")
            if response.status_code == 200:
                data = response.json()
                self.print_result(True, "API ist erreichbar!")
                print(f"      Service: {data['service']}")
                print(f"      Version: {data['version']}")
                return True
            self.print_result(False, f"API antwortet nicht richtig: {response.status_code}")
            return False
        except Exception as e:
            self.print_result(False, f"Kann API nicht erreichen: {e}")
            print("\n  💡 Tipp: Ist die API gestartet? Führe aus: python app.py")
            return False

    def test_health(self):
        """Test 2: Health Check"""
        self.print_header("TEST 2: Health Check")

        try:
            response = requests.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.print_result(True, f"Overall Status: {data['status']}")

                print("\n  📊 Service Status:")
                for service, status in data["services"].items():
                    icon = "✅" if status["status"] in ["healthy", "configured"] else "⚠️"
                    print(f"      {icon} {service}: {status['message']}")

                return True
            self.print_result(False, f"Health check failed: {response.status_code}")
            return False
        except Exception as e:
            self.print_result(False, f"Error: {e}")
            return False

    def test_upload(self, pdf_path=None):
        """Test 3: Document Upload"""
        self.print_header("TEST 3: Document Upload")

        # Find test PDF
        if pdf_path is None:
            test_paths = [
                Path("../../AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"),
                Path(
                    "C:/Users/haast/Docker/KRAI-minimal/AccurioPress_C4080_C4070_C84hc_C74hc_AccurioPrint_C4065_C4065P_SM_EN_20250127.pdf"
                ),
            ]

            for path in test_paths:
                if path.exists():
                    pdf_path = path
                    break

        if pdf_path is None or not Path(pdf_path).exists():
            self.print_result(False, "Kein Test-PDF gefunden!")
            print("\n  💡 Tipp: Gib den Pfad zu einem PDF an:")
            print("      tester.test_upload('pfad/zu/deinem.pdf')")
            return False

        print(f"\n  📄 Uploading: {Path(pdf_path).name}")

        try:
            with open(pdf_path, "rb") as f:
                files = {"file": (Path(pdf_path).name, f, "application/pdf")}
                data = {"document_type": "service_manual", "force_reprocess": "false"}

                response = requests.post(f"{self.base_url}/upload", files=files, data=data)

            if response.status_code == 200:
                result = response.json()

                if result["success"]:
                    self.print_result(True, "Upload erfolgreich!")
                    self.document_id = result["document_id"]

                    print("\n  📋 Details:")
                    print(f"      Document ID: {result['document_id']}")
                    print(f"      Status: {result['status']}")

                    if result.get("metadata"):
                        meta = result["metadata"]
                        print(f"      Seiten: {meta.get('page_count', 'N/A')}")
                        print(f"      Größe: {meta.get('file_size_bytes', 0) / (1024*1024):.1f} MB")

                    return True
                self.print_result(False, f"Upload fehlgeschlagen: {result.get('message', 'Unknown error')}")
                return False
            self.print_result(False, f"Server error: {response.status_code}")
            print(f"      Response: {response.text[:200]}")
            return False

        except Exception as e:
            self.print_result(False, f"Error: {e}")
            return False

    def test_status(self):
        """Test 4: Document Status"""
        self.print_header("TEST 4: Document Status")

        if not self.document_id:
            self.print_result(False, "Keine Document ID! Führe erst test_upload() aus.")
            return False

        try:
            response = requests.get(f"{self.base_url}/status/{self.document_id}")

            if response.status_code == 200:
                data = response.json()
                self.print_result(True, "Status abgerufen!")

                print("\n  📊 Processing Status:")
                print(f"      Status: {data['status']}")
                print(f"      Current Stage: {data['current_stage']}")
                print(f"      Progress: {data['progress']:.1f}%")

                # Progress Bar
                progress_bar_length = 40
                filled = int(progress_bar_length * data["progress"] / 100)
                bar = "█" * filled + "░" * (progress_bar_length - filled)
                print(f"      [{bar}] {data['progress']:.1f}%")

                if data.get("error"):
                    print(f"\n      ⚠️ Error: {data['error']}")

                return True
            if response.status_code == 404:
                self.print_result(False, "Dokument nicht gefunden!")
                return False
            self.print_result(False, f"Server error: {response.status_code}")
            return False

        except Exception as e:
            self.print_result(False, f"Error: {e}")
            return False

    def test_pipeline_status(self):
        """Test 5: Pipeline Overview"""
        self.print_header("TEST 5: Pipeline Overview")

        try:
            response = requests.get(f"{self.base_url}/status")

            if response.status_code == 200:
                data = response.json()
                self.print_result(True, "Pipeline Status abgerufen!")

                print("\n  📊 Pipeline Statistics:")
                print(f"      Total Documents: {data['total_documents']}")
                print(f"      In Queue: {data['in_queue']}")
                print(f"      Processing: {data['processing']}")
                print(f"      Completed: {data['completed']}")
                print(f"      Failed: {data['failed']}")

                if "by_task_type" in data:
                    print("\n  📋 Documents by Stage:")
                    for task_type, count in data["by_task_type"].items():
                        if count > 0:
                            print(f"      • {task_type}: {count}")

                return True
            self.print_result(False, f"Server error: {response.status_code}")
            return False

        except Exception as e:
            self.print_result(False, f"Error: {e}")
            return False

    def run_all_tests(self, pdf_path=None):
        """Alle Tests ausführen"""
        print("\n" + "🚀" * 40)
        print("\n   KRAI API - Einfacher Test Runner")
        print("\n" + "🚀" * 40)

        # Test 1: Connection
        if not self.test_connection():
            print("\n❌ API ist nicht erreichbar. Tests abgebrochen.")
            return

        # Test 2: Health
        self.test_health()

        # Test 3: Upload
        if self.test_upload(pdf_path):
            # Wait a bit
            print("\n  ⏳ Warte 2 Sekunden...")
            sleep(2)

            # Test 4: Status
            self.test_status()

        # Test 5: Pipeline
        self.test_pipeline_status()

        # Summary
        print("\n" + "=" * 80)
        print("  ✅ Alle Tests abgeschlossen!")
        print("=" * 80)

        if self.document_id:
            print(f"\n  💡 Deine Document ID: {self.document_id}")
            print(f"  💡 Status abrufen: http://localhost:8000/status/{self.document_id}")
            print("  💡 Swagger UI: http://localhost:8000/docs")

        print("\n")


def main():
    """Main function"""
    tester = SimpleAPITester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
