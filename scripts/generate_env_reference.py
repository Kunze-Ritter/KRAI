#!/usr/bin/env python3
"""
Generate Environment Variables Reference Documentation

This script generates a comprehensive environment variables reference
from the .env.example template, creating structured documentation with
consistent formatting.
"""

from pathlib import Path

# Variable definitions with metadata
VARIABLES = {
    "Application Settings": [
        {
            "name": "ENV",
            "required": False,
            "default": "production",
            "example": "ENV=development",
            "description": "Runtime environment identifier (production, staging, development)",
            "used_by": "Application startup, logging configuration, feature flags",
            "notes": "Affects default log levels and debug behavior",
        },
        {
            "name": "API_HOST",
            "required": False,
            "default": "0.0.0.0",
            "example": "API_HOST=0.0.0.0",
            "description": "Backend API host binding address (0.0.0.0 for Docker, 127.0.0.1 for local only)",
            "used_by": "FastAPI/Uvicorn server",
            "notes": "Use 0.0.0.0 in Docker to allow external connections",
        },
        {
            "name": "API_PORT",
            "required": False,
            "default": "8000",
            "example": "API_PORT=8000",
            "description": "Backend API port for FastAPI/Uvicorn",
            "used_by": "FastAPI/Uvicorn server, Docker Compose port mapping",
            "notes": "Must match Docker Compose port configuration",
        },
        {
            "name": "LOG_LEVEL",
            "required": False,
            "default": "INFO",
            "example": "LOG_LEVEL=DEBUG",
            "description": "Global log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
            "used_by": "Python logging configuration across all modules",
            "notes": "Use DEBUG for development, INFO for production",
        },
    ],
    "Database Configuration": [
        {
            "name": "DATABASE_TYPE",
            "required": True,
            "default": "postgresql",
            "example": "DATABASE_TYPE=postgresql",
            "description": "Database backend type (postgresql or sqlite)",
            "used_by": "Database adapter factory",
            "notes": "PostgreSQL recommended for production; sqlite for testing only",
        },
        {
            "name": "DATABASE_HOST",
            "required": "Yes (for PostgreSQL)",
            "default": None,
            "example": "DATABASE_HOST=krai-postgres",
            "description": "PostgreSQL server hostname (Docker service name or IP)",
            "used_by": "Database connection string builder",
            "notes": "Use Docker service name for container networking",
        },
        {
            "name": "DATABASE_PORT",
            "required": False,
            "default": "5432",
            "example": "DATABASE_PORT=5432",
            "description": "PostgreSQL service port",
            "used_by": "Database connection string builder",
            "notes": "Standard PostgreSQL port is 5432",
        },
        {
            "name": "DATABASE_NAME",
            "required": True,
            "default": None,
            "example": "DATABASE_NAME=krai",
            "description": "PostgreSQL database name",
            "used_by": "Database connection string builder",
            "notes": "Must match database created during initialization",
        },
        {
            "name": "DATABASE_USER",
            "required": True,
            "default": None,
            "example": "DATABASE_USER=krai_user",
            "description": "PostgreSQL username for application connections",
            "used_by": "Database connection string builder",
            "notes": "Should have appropriate schema permissions",
        },
        {
            "name": "DATABASE_PASSWORD",
            "required": True,
            "default": None,
            "example": "DATABASE_PASSWORD=krai_secure_password",
            "description": "PostgreSQL password for application user",
            "used_by": "Database connection string builder",
            "notes": "Change for production! Use strong passwords",
        },
        {
            "name": "DATABASE_CONNECTION_URL",
            "required": "No (constructed from above if missing)",
            "default": "Constructed from DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD",
            "example": "DATABASE_CONNECTION_URL=postgresql://krai_user:password@krai-postgres:5432/krai",
            "description": "Complete PostgreSQL connection string",
            "used_by": "Database adapters, migration scripts",
            "notes": "Overrides individual DATABASE_* variables if set",
        },
    ],
    "Object Storage Configuration": [
        {
            "name": "OBJECT_STORAGE_TYPE",
            "required": True,
            "default": "s3",
            "example": "OBJECT_STORAGE_TYPE=s3",
            "description": "Object storage implementation (s3-compatible for MinIO and R2)",
            "used_by": "Storage adapter factory",
            "notes": "Currently only s3 is supported",
        },
        {
            "name": "OBJECT_STORAGE_ENDPOINT",
            "required": True,
            "default": None,
            "example": "OBJECT_STORAGE_ENDPOINT=http://krai-minio:9000",
            "description": "S3-compatible endpoint URL (MinIO or R2)",
            "used_by": "Storage adapter, upload handlers",
            "notes": "Use Docker service name for internal connections",
        },
        {
            "name": "OBJECT_STORAGE_ACCESS_KEY",
            "required": True,
            "default": None,
            "example": "OBJECT_STORAGE_ACCESS_KEY=minioadmin",
            "description": "S3 access key ID (MinIO or R2)",
            "used_by": "Storage adapter authentication",
            "notes": "Change default for production!",
        },
        {
            "name": "OBJECT_STORAGE_SECRET_KEY",
            "required": True,
            "default": None,
            "example": "OBJECT_STORAGE_SECRET_KEY=minioadmin123",
            "description": "S3 secret access key (MinIO or R2)",
            "used_by": "Storage adapter authentication",
            "notes": "Change default for production!",
        },
        {
            "name": "OBJECT_STORAGE_REGION",
            "required": False,
            "default": "us-east-1",
            "example": "OBJECT_STORAGE_REGION=us-east-1",
            "description": "AWS region identifier (MinIO accepts any string)",
            "used_by": "S3 client configuration",
            "notes": "Use 'auto' for S3-compatible storage",
        },
        {
            "name": "OBJECT_STORAGE_USE_SSL",
            "required": False,
            "default": "false",
            "example": "OBJECT_STORAGE_USE_SSL=false",
            "description": "Enable HTTPS for storage endpoint",
            "used_by": "S3 client configuration",
            "notes": "Set true for production with SSL certificates",
        },
        {
            "name": "OBJECT_STORAGE_PUBLIC_URL",
            "required": False,
            "default": None,
            "example": "OBJECT_STORAGE_PUBLIC_URL=http://localhost:9000",
            "description": "Public URL for frontend to access stored files",
            "used_by": "Frontend image loading, CDN configuration",
            "notes": "Must be accessible from user browsers",
        },
    ],
}


def format_variable(var: dict) -> str:
    """Format a single variable entry."""
    lines = [
        f"### {var['name']}",
        f"- **Required:** {var['required']}",
        f"- **Default:** `{var['default']}`" if var["default"] else "- **Default:** None",
        f"- **Example:** `{var['example']}`",
        f"- **Description:** {var['description']}",
        f"- **Used by:** {var['used_by']}",
        f"- **Notes:** {var['notes']}",
        "",
    ]
    return "\n".join(lines)


def generate_documentation():
    """Generate the complete documentation file."""

    header = """# Environment Variables Reference

## Overview

This document provides a comprehensive reference for all environment variables used in the KRAI system. Environment variables are used to configure services, enable/disable features, and manage deployment settings across different environments.

**Current Configuration Approach:** All environment variables are consolidated in a single root `.env` file. Legacy modular files (`.env.database`, `.env.storage`, etc.) are deprecated.

## Configuration Files

### Primary Configuration

- **`.env`** - Single consolidated configuration file (required)
- **`.env.example`** - Template with all supported variables and documentation
- **`.env.local`** *(optional)* - Developer-specific overrides (gitignored)

### Related Documentation

- [`.env.example`](../.env.example) - Complete variable reference with examples
- [`docs/DATABASE_MIGRATION_COMPLETE.md`](DATABASE_MIGRATION_COMPLETE.md) - Migration from Supabase to PostgreSQL complete
- [`docs/setup/DEPRECATED_VARIABLES.md`](setup/DEPRECATED_VARIABLES.md) - Legacy variable mappings
- [`DEPLOYMENT.md`](../DEPLOYMENT.md) - Production deployment guide
- [`DOCKER_SETUP.md`](../DOCKER_SETUP.md) - Docker configuration guide

---

## Variable Reference

This section documents all currently supported variables using a consistent schema:
- **Name:** Variable identifier
- **Required:** Whether the variable must be set
- **Default:** Default value if not specified
- **Example:** Sample value
- **Description:** What the variable controls
- **Used by:** Which components consume this variable
- **Notes:** Additional context or warnings

Variables are organized by functional area matching the structure in `.env.example`.

---

"""

    sections = []
    for section_name, variables in VARIABLES.items():
        section = f"## {section_name}\n\n"
        for var in variables:
            section += format_variable(var)
        sections.append(section)

    footer = """---

## Deprecated Variables

**IMPORTANT:** The following variables are deprecated and should not be used in new deployments.

For complete deprecation information, migration instructions, and variable mappings, see:
- [`docs/setup/DEPRECATED_VARIABLES.md`](setup/DEPRECATED_VARIABLES.md) - Complete deprecation reference
- [`docs/DATABASE_MIGRATION_COMPLETE.md`](DATABASE_MIGRATION_COMPLETE.md) - Migration guide

### Deprecated Database Variables

| Variable | Status | Notes |
|----------|--------|-------|
| `SUPABASE_URL` | ✅ Removed | Use `DATABASE_URL` instead |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ Removed | Use `DATABASE_SERVICE_KEY` instead |
| `SUPABASE_ANON_KEY` | ✅ Removed | Not needed with PostgreSQL |
| `SUPABASE_STORAGE_URL` | ✅ Removed | Use `OBJECT_STORAGE_ENDPOINT` instead |
| `SUPABASE_DB_PASSWORD` | ✅ Removed | Use `DATABASE_PASSWORD` instead |
| `DATABASE_URL` | ✅ Active | PostgreSQL connection string |

### Deprecated Storage Variables

| Variable | Replaced By | Notes |
|----------|-------------|-------|
| `R2_ACCESS_KEY_ID` | `OBJECT_STORAGE_ACCESS_KEY` | MinIO access key |
| `R2_SECRET_ACCESS_KEY` | `OBJECT_STORAGE_SECRET_KEY` | MinIO secret key |
| `R2_ENDPOINT_URL` | `OBJECT_STORAGE_ENDPOINT` | MinIO S3-compatible endpoint |
| `R2_BUCKET_NAME_DOCUMENTS` | *(managed by MinIO)* | Buckets created automatically |
| `R2_REGION` | `OBJECT_STORAGE_REGION` | AWS region identifier |
| `R2_PUBLIC_URL_*` | `OBJECT_STORAGE_PUBLIC_URL` | Single public URL for all buckets |
| `MINIO_ENDPOINT` | `OBJECT_STORAGE_ENDPOINT` | Renamed for consistency |
| `MINIO_ACCESS_KEY` | `OBJECT_STORAGE_ACCESS_KEY` | Renamed for consistency |
| `MINIO_SECRET_KEY` | `OBJECT_STORAGE_SECRET_KEY` | Renamed for consistency |

### Deprecated AI Service Variables

| Variable | Replaced By | Notes |
|----------|-------------|-------|
| `OLLAMA_BASE_URL` | `OLLAMA_URL` | Simplified naming convention |
| `AI_SERVICE_URL` | `OLLAMA_URL` | Consolidated into single variable |

---

## Configuration Management

### Variable Precedence

1. Environment variables (highest priority)
2. `.env` file
3. Default values in code
4. Configuration templates (lowest priority)

### Loading Order

1. `.env` - Base configuration
2. `.env.local` - Developer overrides (gitignored)
3. System environment variables - Runtime overrides

### Validation

Run validation scripts to ensure configuration is correct:

```bash
# Validate all required variables are set
python scripts/validate_env.py --verbose

# Test database connectivity
python scripts/test_db_connection.py

# Test storage connectivity
python scripts/test_storage_connection.py
```

---

## Best Practices

### Security

1. **Never commit secrets**: Use `.env.example` templates only
2. **Use strong passwords**: Generate cryptographically secure passwords
3. **Rotate secrets regularly**: Update JWT keys and API keys periodically
4. **Use environment-specific configs**: Separate development and production settings
5. **Store production secrets securely**: Use a secrets manager (1Password, Vault, etc.)

### Performance

1. **Tune connection pools**: Adjust based on expected load
2. **Optimize batch sizes**: Balance memory usage and throughput
3. **Enable caching**: Use Redis for frequently accessed data
4. **Monitor resource usage**: Adjust settings based on metrics

### Maintenance

1. **Document changes**: Update this reference when adding variables
2. **Use semantic naming**: Choose descriptive variable names
3. **Group related settings**: Organize variables by service/feature
4. **Provide defaults**: Ensure reasonable default values

---

## Troubleshooting

### Common Issues

1. **Missing variables**: Check `.env.example` for required settings
2. **Invalid values**: Validate variable formats and ranges
3. **Permission issues**: Check file permissions for configuration files
4. **Service connectivity**: Verify network settings and endpoints

### Debug Commands

```bash
# Check loaded environment variables
docker-compose exec krai-engine env | grep -E "DATABASE|OBJECT_STORAGE|OLLAMA"

# Validate configuration files
docker-compose config

# Test service connectivity
docker-compose exec krai-postgres pg_isready
docker-compose exec krai-minio mc alias list
curl http://localhost:11434/api/tags
```

---

## Additional Resources

- [`.env.example`](../.env.example) - Complete template with all variables
- [`DEPLOYMENT.md`](../DEPLOYMENT.md) - Production deployment guide
- [`DOCKER_SETUP.md`](../DOCKER_SETUP.md) - Docker configuration guide
- [`docs/SUPABASE_TO_POSTGRESQL_MIGRATION.md`](SUPABASE_TO_POSTGRESQL_MIGRATION.md) - Migration guide
- [`docs/setup/DEPRECATED_VARIABLES.md`](setup/DEPRECATED_VARIABLES.md) - Deprecation reference
- [`DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) - Database schema documentation

---

**Last Updated:** 2024-11-19
**Configuration Approach:** Consolidated single `.env` file
**Deprecated:** Legacy modular `.env.*` files
"""

    return header + "\n".join(sections) + footer


if __name__ == "__main__":
    output_path = Path(__file__).parent.parent / "docs" / "ENVIRONMENT_VARIABLES_REFERENCE.md"
    content = generate_documentation()

    output_path.write_text(content, encoding="utf-8")
    print(f"✅ Generated: {output_path}")
    print(f"📄 Total length: {len(content)} characters")
