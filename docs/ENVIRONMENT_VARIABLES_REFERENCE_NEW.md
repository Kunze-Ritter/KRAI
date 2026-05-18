# Environment Variables Reference

## Overview

This document provides a comprehensive reference for all environment variables used in the KRAI system. Environment variables are used to configure services, enable/disable features, and manage deployment settings across different environments.

**Current Configuration Approach:** All environment variables are consolidated in a single root .env file. Legacy modular files (.env.database, .env.storage, etc.) are deprecated.

## Configuration Files

### Primary Configuration

- **.env** - Single consolidated configuration file (required)
- **.env.example** - Template with all supported variables and documentation
- **.env.local** *(optional)* - Developer-specific overrides (gitignored)

### Related Documentation

- [.env.example](../.env.example) - Complete variable reference with examples
- [docs/SUPABASE_TO_POSTGRESQL_MIGRATION.md](SUPABASE_TO_POSTGRESQL_MIGRATION.md) - Migration from cloud to local-first
- [docs/setup/DEPRECATED_VARIABLES.md](setup/DEPRECATED_VARIABLES.md) - Legacy variable mappings
- [DEPLOYMENT.md](../DEPLOYMENT.md) - Production deployment guide
- [DOCKER_SETUP.md](../DOCKER_SETUP.md) - Docker configuration guide

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

Variables are organized by functional area matching the structure in .env.example.
