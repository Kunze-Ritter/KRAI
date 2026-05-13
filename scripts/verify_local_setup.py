#!/usr/bin/env python3
"""
Local Docker Setup Verification Script for KRAI

This script verifies that all local Docker services are running and accessible.
It generates a comprehensive health report for the entire KRAI stack.

Usage:
    python scripts/verify_local_setup.py              # Check all services
    python scripts/verify_local_setup.py --verbose    # Detailed output
    python scripts/verify_local_setup.py --service postgres  # Check specific service
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    PSYCOPG2_AVAILABLE = False

try:
    import boto3
    from botocore.exceptions import ClientError, EndpointConnectionError

    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None
    BOTO3_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None
    REQUESTS_AVAILABLE = False

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class LocalSetupVerifier:
    """Verifies local Docker setup for KRAI"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.console = Console() if RICH_AVAILABLE else None
        self.results = {}

        # Service configuration
        self.services = {
            "postgresql": {
                "host": os.getenv("DATABASE_HOST", "localhost"),
                "port": int(os.getenv("DATABASE_PORT", "5432")),
                "database": os.getenv("DATABASE_NAME", "krai"),
                "user": os.getenv("DATABASE_USER", "krai_user"),
                "password": os.getenv("DATABASE_PASSWORD", "krai_secure_password"),
            },
            "minio": {
                "endpoint": os.getenv("OBJECT_STORAGE_ENDPOINT", "http://localhost:9000"),
                "access_key": os.getenv("OBJECT_STORAGE_ACCESS_KEY", "minioadmin"),
                "secret_key": os.getenv("OBJECT_STORAGE_SECRET_KEY", "minioadmin123"),
                "buckets": {
                    "documents": os.getenv("OBJECT_STORAGE_BUCKET_DOCUMENTS", "documents"),
                    "images": os.getenv("OBJECT_STORAGE_BUCKET_IMAGES", "images"),
                    "videos": os.getenv("OBJECT_STORAGE_BUCKET_VIDEOS", "videos"),
                    "temp": os.getenv("OBJECT_STORAGE_BUCKET_TEMP", "temp"),
                },
            },
            "ollama": {
                "url": os.getenv("AI_SERVICE_URL", "http://localhost:11434"),
                "models": {
                    "embedding": os.getenv("AI_EMBEDDING_MODEL", "nomic-embed-text:latest"),
                    "text": os.getenv("AI_TEXT_MODEL", "llama3.2:latest"),
                    "vision": os.getenv("AI_VISION_MODEL", "llava-phi3:latest"),
                },
            },
            "pgadmin": {"url": "http://localhost:5050"},
            "n8n": {"url": "http://localhost:5678"},
            "minio_console": {"url": "http://localhost:9001"},
            "backend": {"url": os.getenv("BACKEND_URL", "http://localhost:8000")},
            "laravel": {"url": os.getenv("LARAVEL_URL", "http://localhost:8080")},
        }

        # Expected values for validation
        self.expected_values = {
            "schemas": 6,
            "tables": 44,
            "manufacturers": 14,
            "retry_policies": 4,
            "embedding_dim": 768,
        }

    def print_status(self, message: str, status: str = "info"):
        """Print status message with appropriate formatting"""
        if self.console:
            color = {"success": "green", "warning": "yellow", "error": "red", "info": "blue"}.get(status, "white")

            icon = {"success": "✅", "warning": "⚠️", "error": "❌", "info": "ℹ️"}.get(status, "•")

            self.console.print(f"{icon} {message}", style=color)
        else:
            print(f"{message}")

    async def check_docker_services(self) -> dict[str, any]:
        """Check if Docker containers are running"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{json .}}"], capture_output=True, text=True, timeout=10
            )

            if result.returncode != 0:
                return {"status": "error", "error": "Docker command failed", "details": result.stderr}

            containers = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            expected_containers = ["krai-postgres", "krai-minio", "krai-ollama", "krai-pgadmin", "krai-n8n-chat-agent"]

            running_containers = [c["Name"] for c in containers]
            missing_containers = [c for c in expected_containers if c not in running_containers]

            if missing_containers:
                return {
                    "status": "warning",
                    "running": running_containers,
                    "missing": missing_containers,
                    "message": f"Missing containers: {', '.join(missing_containers)}",
                }
            return {
                "status": "success",
                "running": running_containers,
                "message": f"All {len(expected_containers)} containers running",
            }

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Docker command timed out"}
        except FileNotFoundError:
            return {"status": "error", "error": "Docker not found or not in PATH"}
        except Exception as e:
            return {"status": "error", "error": f"Unexpected error: {e}"}

    async def check_postgresql(self) -> dict[str, any]:
        """Check PostgreSQL connectivity and schema"""
        if not PSYCOPG2_AVAILABLE:
            return {"status": "error", "error": "psycopg2 not available. Install with: pip install psycopg2-binary"}

        config = self.services["postgresql"]

        try:
            # Test connection
            conn = psycopg2.connect(
                host=config["host"],
                port=config["port"],
                database=config["database"],
                user=config["user"],
                password=config["password"],
                connect_timeout=10,
            )

            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check pgvector extension
                cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                vector_result = cur.fetchone()

                # Check schemas
                cur.execute(
                    """
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name LIKE 'krai_%'
                    ORDER BY schema_name
                """
                )
                schemas = [row["schema_name"] for row in cur.fetchall()]
                schema_count = len(schemas)

                # Expected schemas
                expected_schemas = [
                    "krai_core",
                    "krai_content",
                    "krai_intelligence",
                    "krai_system",
                    "krai_parts",
                    "krai_users",
                ]

                missing_schemas = [s for s in expected_schemas if s not in schemas]

                # Count total tables
                cur.execute(
                    """
                    SELECT COUNT(*) as count
                    FROM information_schema.tables
                    WHERE table_schema LIKE 'krai_%' AND table_type = 'BASE TABLE'
                """
                )
                total_tables = cur.fetchone()["count"]

                # Count tables in each schema
                table_counts = {}
                for schema in schemas:
                    cur.execute(
                        """
                        SELECT COUNT(*) as count
                        FROM information_schema.tables
                        WHERE table_schema = %s AND table_type = 'BASE TABLE'
                    """,
                        (schema,),
                    )
                    table_counts[schema] = cur.fetchone()["count"]

                # Check manufacturers count
                manufacturers_count = 0
                try:
                    cur.execute("SELECT COUNT(*) as count FROM krai_core.manufacturers")
                    manufacturers_count = cur.fetchone()["count"]
                except Exception:
                    pass

                # Check retry policies count
                retry_policies_count = 0
                try:
                    cur.execute("SELECT COUNT(*) as count FROM krai_system.retry_policies")
                    retry_policies_count = cur.fetchone()["count"]
                except Exception:
                    pass

                conn.close()

                # Determine status based on validations
                issues = []
                if schema_count != self.expected_values["schemas"]:
                    issues.append(f"Schema count: {schema_count} (expected: {self.expected_values['schemas']})")
                if total_tables != self.expected_values["tables"]:
                    issues.append(f"Table count: {total_tables} (expected: {self.expected_values['tables']})")
                if manufacturers_count < self.expected_values["manufacturers"]:
                    issues.append(
                        f"Manufacturers: {manufacturers_count} (expected: >={self.expected_values['manufacturers']})"
                    )
                if retry_policies_count < self.expected_values["retry_policies"]:
                    issues.append(
                        f"Retry policies: {retry_policies_count} (expected: >={self.expected_values['retry_policies']})"
                    )

                if missing_schemas or issues:
                    status = "warning" if not missing_schemas else "error"
                    message = "; ".join(issues) if issues else f"Missing schemas: {', '.join(missing_schemas)}"
                    return {
                        "status": status,
                        "vector_version": vector_result["extversion"] if vector_result else None,
                        "schemas": schemas,
                        "schema_count": schema_count,
                        "total_tables": total_tables,
                        "manufacturers_count": manufacturers_count,
                        "retry_policies_count": retry_policies_count,
                        "missing_schemas": missing_schemas,
                        "table_counts": table_counts,
                        "message": message,
                        "recommendation": "Run database migrations: docker exec krai-postgres psql -U krai_user -d krai -f /docker-entrypoint-initdb.d/001_core_schema.sql",
                    }
                return {
                    "status": "success",
                    "vector_version": vector_result["extversion"] if vector_result else None,
                    "schemas": schemas,
                    "schema_count": schema_count,
                    "total_tables": total_tables,
                    "manufacturers_count": manufacturers_count,
                    "retry_policies_count": retry_policies_count,
                    "table_counts": table_counts,
                    "message": f"PostgreSQL healthy - {schema_count} schemas, {total_tables} tables, vector extension v{vector_result['extversion'] if vector_result else 'N/A'}",
                }

        except psycopg2.OperationalError as e:
            return {
                "status": "error",
                "error": f"Connection failed: {e}",
                "message": "Check if PostgreSQL is running and credentials are correct",
            }
        except Exception as e:
            return {"status": "error", "error": f"Unexpected error: {e}"}

    async def check_minio(self) -> dict[str, any]:
        """Check MinIO connectivity and buckets"""
        if not BOTO3_AVAILABLE:
            return {"status": "error", "error": "boto3 not available. Install with: pip install boto3"}

        config = self.services["minio"]

        try:
            # Create S3 client
            client = boto3.client(
                "s3",
                endpoint_url=config["endpoint"],
                aws_access_key_id=config["access_key"],
                aws_secret_access_key=config["secret_key"],
                region_name="us-east-1",
            )

            # List buckets
            response = client.list_buckets()
            existing_buckets = [bucket["Name"] for bucket in response["Buckets"]]

            # Check expected buckets
            expected_buckets = list(config["buckets"].values())
            missing_buckets = [b for b in expected_buckets if b not in existing_buckets]

            # Test upload/download to first bucket
            test_result = None
            if existing_buckets:
                try:
                    test_bucket = existing_buckets[0]
                    test_content = b"KRAI verification test"
                    test_key = "verification-test.txt"

                    # Upload
                    client.put_object(Bucket=test_bucket, Key=test_key, Body=test_content)

                    # Download
                    response = client.get_object(Bucket=test_bucket, Key=test_key)
                    downloaded_content = response["Body"].read()

                    # Cleanup
                    client.delete_object(Bucket=test_bucket, Key=test_key)

                    if downloaded_content == test_content:
                        test_result = "success"
                    else:
                        test_result = "failed"

                except Exception as e:
                    test_result = f"error: {e}"

            if missing_buckets:
                return {
                    "status": "warning",
                    "endpoint": config["endpoint"],
                    "existing_buckets": existing_buckets,
                    "missing_buckets": missing_buckets,
                    "test_upload": test_result,
                    "message": f"Missing buckets: {', '.join(missing_buckets)}",
                }
            return {
                "status": "success",
                "endpoint": config["endpoint"],
                "existing_buckets": existing_buckets,
                "test_upload": test_result,
                "message": f"MinIO healthy - {len(existing_buckets)} buckets, read/write working",
            }

        except EndpointConnectionError:
            return {
                "status": "error",
                "error": f'Cannot connect to MinIO at {config["endpoint"]}',
                "message": "Check if MinIO container is running",
            }
        except Exception as e:
            return {"status": "error", "error": f"Unexpected error: {e}"}

    async def check_ollama(self) -> dict[str, any]:
        """Check Ollama connectivity and models"""
        if not REQUESTS_AVAILABLE:
            return {"status": "error", "error": "requests not available. Install with: pip install requests"}

        config = self.services["ollama"]

        try:
            # Check service health
            response = requests.get(f"{config['url']}/api/tags", timeout=10)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Ollama API returned status {response.status_code}",
                    "message": "Check if Ollama container is running",
                }

            data = response.json()
            available_models = [model["name"] for model in data.get("models", [])]

            # Check required models
            required_models = list(config["models"].values())
            missing_models = [m for m in required_models if m not in available_models]

            # Test embedding generation if embedding model is available
            embedding_test_result = None
            embedding_model = config["models"]["embedding"]
            if embedding_model in available_models or any(embedding_model.split(":")[0] in m for m in available_models):
                try:
                    embed_response = requests.post(
                        f"{config['url']}/api/embeddings",
                        json={"model": embedding_model.split(":")[0], "prompt": "test"},
                        timeout=30,
                    )
                    if embed_response.status_code == 200:
                        embed_data = embed_response.json()
                        if "embedding" in embed_data:
                            embedding_dim = len(embed_data["embedding"])
                            if embedding_dim == self.expected_values["embedding_dim"]:
                                embedding_test_result = f"success (dim: {embedding_dim})"
                            else:
                                embedding_test_result = f"dimension mismatch: {embedding_dim} (expected: {self.expected_values['embedding_dim']})"
                        else:
                            embedding_test_result = "no embedding in response"
                    else:
                        embedding_test_result = f"failed (status: {embed_response.status_code})"
                except Exception as e:
                    embedding_test_result = f"error: {str(e)[:50]}"

            if missing_models:
                return {
                    "status": "warning",
                    "endpoint": config["url"],
                    "available_models": available_models,
                    "missing_models": missing_models,
                    "embedding_test": embedding_test_result,
                    "message": f"Missing models: {', '.join(missing_models)}",
                    "recommendation": f"Pull model: docker exec krai-ollama ollama pull {missing_models[0]}",
                }
            return {
                "status": "success",
                "endpoint": config["url"],
                "available_models": available_models,
                "embedding_test": embedding_test_result,
                "message": f"Ollama healthy - {len(available_models)} models available, embedding test: {embedding_test_result or 'skipped'}",
            }

        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "error": f'Cannot connect to Ollama at {config["url"]}',
                "message": "Check if Ollama container is running",
            }
        except Exception as e:
            return {"status": "error", "error": f"Unexpected error: {e}"}

    async def check_backend_api(self) -> dict[str, any]:
        """Check FastAPI backend endpoints"""
        if not REQUESTS_AVAILABLE:
            return {"status": "error", "error": "requests not available. Install with: pip install requests"}

        config = self.services["backend"]
        base_url = config["url"]

        try:
            # Test /health endpoint
            health_response = requests.get(f"{base_url}/health", timeout=10)

            if health_response.status_code != 200:
                return {
                    "status": "error",
                    "error": f"Backend /health returned status {health_response.status_code}",
                    "message": "Check backend logs: docker logs krai-engine",
                }

            health_data = health_response.json()

            # Test documentation endpoints
            docs_accessible = False
            redoc_accessible = False

            try:
                docs_response = requests.get(f"{base_url}/docs", timeout=5)
                docs_accessible = docs_response.status_code == 200
            except Exception:
                pass

            try:
                redoc_response = requests.get(f"{base_url}/redoc", timeout=5)
                redoc_accessible = redoc_response.status_code == 200
            except Exception:
                pass

            # Check health status details
            db_status = health_data.get("database", "unknown")
            storage_status = health_data.get("storage", "unknown")
            ai_status = health_data.get("ai", "unknown")

            issues = []
            if db_status != "healthy":
                issues.append(f"database: {db_status}")
            if storage_status != "healthy":
                issues.append(f"storage: {storage_status}")
            if not docs_accessible:
                issues.append("docs not accessible")
            if not redoc_accessible:
                issues.append("redoc not accessible")

            if issues:
                return {
                    "status": "warning",
                    "url": base_url,
                    "health": health_data,
                    "docs_accessible": docs_accessible,
                    "redoc_accessible": redoc_accessible,
                    "message": f"Backend issues: {', '.join(issues)}",
                }
            return {
                "status": "success",
                "url": base_url,
                "health": health_data,
                "docs_accessible": docs_accessible,
                "redoc_accessible": redoc_accessible,
                "message": f"Backend healthy - database: {db_status}, storage: {storage_status}, docs: accessible",
            }

        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "error": f"Cannot connect to backend at {base_url}",
                "message": "Check if backend container is running",
                "recommendation": "Check backend logs: docker logs krai-engine",
            }
        except Exception as e:
            return {"status": "error", "error": f"Unexpected error: {e}"}

    async def check_laravel_admin(self) -> dict[str, any]:
        """Check Laravel admin dashboard and Filament"""
        if not REQUESTS_AVAILABLE:
            return {"status": "error", "error": "requests not available. Install with: pip install requests"}

        config = self.services["laravel"]
        base_url = config["url"]

        try:
            # Test dashboard accessibility
            dashboard_response = requests.get(f"{base_url}/kradmin", timeout=10, allow_redirects=True)

            if dashboard_response.status_code not in [200, 302]:
                return {
                    "status": "error",
                    "error": f"Laravel dashboard returned status {dashboard_response.status_code}",
                    "message": "Check nginx logs: docker logs krai-laravel-nginx",
                    "recommendation": "Check Laravel logs: docker logs krai-laravel-admin",
                }

            # Test login page
            login_accessible = False
            try:
                login_response = requests.get(f"{base_url}/kradmin/login", timeout=5)
                login_accessible = login_response.status_code in [200, 302]
            except Exception:
                pass

            # Test database connection via artisan
            db_connection_ok = False
            try:
                result = subprocess.run(
                    ["docker", "exec", "krai-laravel-admin", "php", "artisan", "db:show"],
                    capture_output=True,
                    timeout=10,
                )
                db_connection_ok = result.returncode == 0
            except Exception:
                pass

            # Check Filament resources
            resources = ["documents", "products", "manufacturers", "users", "pipeline-errors", "alert-configurations"]
            accessible_resources = 0

            for resource in resources:
                try:
                    response = requests.get(f"{base_url}/kradmin/{resource}", timeout=3, allow_redirects=False)
                    if response.status_code in [200, 302]:
                        accessible_resources += 1
                except Exception:
                    try:
                        response = requests.get(
                            f"{base_url}/kradmin/resources/{resource}", timeout=3, allow_redirects=False
                        )
                        if response.status_code in [200, 302]:
                            accessible_resources += 1
                    except Exception:
                        pass

            issues = []
            if not login_accessible:
                issues.append("login page not accessible")
            if not db_connection_ok:
                issues.append("database connection failed")
            if accessible_resources < 3:
                issues.append(f"limited resources accessible ({accessible_resources}/{len(resources)})")

            if issues:
                return {
                    "status": "warning",
                    "url": base_url,
                    "login_accessible": login_accessible,
                    "db_connection": db_connection_ok,
                    "accessible_resources": accessible_resources,
                    "total_resources": len(resources),
                    "message": f"Laravel issues: {', '.join(issues)}",
                    "recommendation": "Check .env configuration in laravel-admin/",
                }
            return {
                "status": "success",
                "url": base_url,
                "login_accessible": login_accessible,
                "db_connection": db_connection_ok,
                "accessible_resources": accessible_resources,
                "total_resources": len(resources),
                "message": f"Laravel healthy - dashboard accessible, {accessible_resources} Filament resources available",
            }

        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "error": f"Cannot connect to Laravel at {base_url}",
                "message": "Check if Laravel container is running",
                "recommendation": "Check nginx logs: docker logs krai-laravel-nginx",
            }
        except Exception as e:
            return {"status": "error", "error": f"Unexpected error: {e}"}

    async def check_web_interface(self, name: str, url: str) -> dict[str, any]:
        """Check if web interface is accessible"""
        if not REQUESTS_AVAILABLE:
            return {"status": "error", "error": "requests not available"}

        try:
            response = requests.get(url, timeout=10, allow_redirects=True)

            if response.status_code in [200, 302, 401]:  # Accept auth required as healthy
                return {
                    "status": "success",
                    "url": url,
                    "status_code": response.status_code,
                    "message": f"{name} interface accessible",
                }
            return {
                "status": "warning",
                "url": url,
                "status_code": response.status_code,
                "message": f"{name} returned unexpected status code",
            }

        except requests.exceptions.ConnectionError:
            return {
                "status": "error",
                "url": url,
                "error": f"Cannot connect to {name}",
                "message": f"Check if {name.lower()} container is running",
            }
        except Exception as e:
            return {"status": "error", "url": url, "error": f"Unexpected error: {e}"}

    async def run_verification(self, service_filter: str | None = None) -> dict[str, any]:
        """Run complete verification"""
        start_time = time.time()

        # Define all checks
        checks = {
            "docker": self.check_docker_services(),
            "postgresql": self.check_postgresql(),
            "backend": self.check_backend_api(),
            "laravel": self.check_laravel_admin(),
            "minio": self.check_minio(),
            "ollama": self.check_ollama(),
            "pgadmin": self.check_web_interface("pgAdmin", self.services["pgadmin"]["url"]),
            "n8n": self.check_web_interface("n8n", self.services["n8n"]["url"]),
            "minio_console": self.check_web_interface("MinIO Console", self.services["minio_console"]["url"]),
        }

        # Filter checks if specified
        if service_filter:
            if service_filter in checks:
                checks = {service_filter: checks[service_filter]}
            else:
                self.print_status(f"Unknown service: {service_filter}", "error")
                return {}

        # Execute all checks
        results = {}
        for name, check in checks.items():
            if self.verbose:
                self.print_status(f"Checking {name}...", "info")
            results[name] = await check

        # Calculate summary
        total_checks = len(results)
        success_count = sum(1 for r in results.values() if r["status"] == "success")
        warning_count = sum(1 for r in results.values() if r["status"] == "warning")
        error_count = sum(1 for r in results.values() if r["status"] == "error")

        # Determine overall status: error if any errors, warning if only warnings, otherwise success
        if error_count > 0:
            overall_status = "error"
        elif warning_count > 0:
            overall_status = "warning"
        else:
            overall_status = "success"

        duration = time.time() - start_time

        summary = {
            "overall_status": overall_status,
            "total_checks": total_checks,
            "success_count": success_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now().isoformat(),
            "services": results,
        }

        return summary

    def print_results(self, results: dict[str, any]):
        """Print formatted results"""
        if self.console:
            self.print_rich_results(results)
        else:
            self.print_plain_results(results)

    def print_rich_results(self, results: dict[str, any]):
        """Print results with rich formatting"""
        # Summary panel
        summary_text = f"""
Overall Status: {results['overall_status'].upper()}
✅ Success: {results['success_count']}
⚠️  Warnings: {results['warning_count']}
❌ Errors: {results['error_count']}
⏱️  Duration: {results['duration_seconds']}s
        """.strip()

        self.console.print(Panel(summary_text, title="🔍 KRAI Setup Verification", border_style="blue"))

        # Services table
        table = Table(title="Service Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Details", style="white")

        status_icons = {"success": "✅", "warning": "⚠️", "error": "❌"}

        for service, result in results["services"].items():
            status = result["status"]
            icon = status_icons.get(status, "❓")

            details = result.get("message", result.get("error", "No details"))
            if len(details) > 60:
                details = details[:57] + "..."

            table.add_row(service, f"{icon} {status}", details)

        self.console.print(table)

        # Recommendations
        if results["warning_count"] > 0 or results["error_count"] > 0:
            recommendations = []

            for service, result in results["services"].items():
                if result["status"] in ["warning", "error"]:
                    if "recommendation" in result:
                        recommendations.append(f"• {result['recommendation']}")
                    elif service == "postgresql" and "schemas" in result:
                        recommendations.append("• Run database migrations: Check /docker-entrypoint-initdb.d/")
                    elif service == "minio" and "missing_buckets" in result:
                        recommendations.append("• Initialize MinIO: python scripts/init_minio.py")
                    elif service == "ollama" and "missing_models" in result:
                        model = result["missing_models"][0] if result["missing_models"] else "nomic-embed-text:latest"
                        recommendations.append(f"• Pull Ollama model: docker exec krai-ollama ollama pull {model}")
                    elif service == "docker":
                        recommendations.append("• Start Docker services: docker-compose up -d")
                    elif service == "backend":
                        recommendations.append("• Check backend logs: docker logs krai-engine")
                    elif service == "laravel":
                        recommendations.append("• Check Laravel logs: docker logs krai-laravel-admin")

            if recommendations:
                self.console.print(Panel("\n".join(recommendations), title="💡 Recommendations", border_style="yellow"))

    def print_plain_results(self, results: dict[str, any]):
        """Print results in plain text"""
        print("\n🔍 KRAI Setup Verification Results")
        print("=" * 50)
        print(f"Overall Status: {results['overall_status'].upper()}")
        print(f"✅ Success: {results['success_count']}")
        print(f"⚠️  Warnings: {results['warning_count']}")
        print(f"❌ Errors: {results['error_count']}")
        print(f"⏱️  Duration: {results['duration_seconds']}s")
        print(f"🕐 Timestamp: {results['timestamp']}")
        print()

        print("Service Details:")
        print("-" * 30)

        for service, result in results["services"].items():
            status = result["status"].upper()
            details = result.get("message", result.get("error", "No details"))

            print(f"{service}: {status}")
            print(f"  {details}")
            print()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Verify KRAI local Docker setup")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--service", type=str, help="Check specific service only")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output for CI/CD")

    args = parser.parse_args()

    # Disable rich output if no-color flag is set
    if args.no_color and RICH_AVAILABLE:
        verifier = LocalSetupVerifier(verbose=args.verbose)
        verifier.console = None
    else:
        verifier = LocalSetupVerifier(verbose=args.verbose)

    results = await verifier.run_verification(args.service)

    if not results:
        sys.exit(1)

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        verifier.print_results(results)

    # Exit code based on overall status
    if results["overall_status"] == "success":
        sys.exit(0)
    elif results["overall_status"] == "warning":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
