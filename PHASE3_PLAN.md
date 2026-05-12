# Phase 3 Implementation Plan: Dashboard & UI

**Status:** 🟢 Ready to start

## Übersicht

Implementiere die Laravel/Filament UI für das Zubehör- und Konfigurationssystem. Backend-Logik existiert bereits.

## Phase 3.1: Foundation (Accessories & Dependencies)

### 1. Database Migration 031
- [ ] Create `option_dependencies` table
  - `id` (UUID)
  - `option_id` (UUID, refs products)
  - `depends_on_option_id` (UUID, refs products)
  - `dependency_type` (enum: requires, excludes, alternative)
  - `notes` (text, nullable)
  - Unique constraint on (option_id, depends_on_option_id, dependency_type)

### 2. Laravel Models
- [ ] `Accessory` Model (wrapper around Product with product_type filter)
- [ ] `OptionDependency` Model (binds to option_dependencies table)
  - Relations: `option`, `dependsOn`

### 3. Filament Resources
- [ ] `AccessoriesResource` (CRUD)
  - List: all accessories filtered by product_type
  - Create: select product, mark as accessory
  - Edit: update compatibility notes
  - Delete: with confirmation

- [ ] `OptionDependenciesResource` (CRUD)
  - List: all dependencies with product names
  - Create: select option, depends_on, dependency_type, notes
  - Edit: update notes, dependency_type
  - Delete: with confirmation

### 4. Product Management Enhancement
- [ ] Add `AccessoriesRelationManager` to ProductResource
  - Show linked accessories (from product_accessories)
  - Quick add/remove accessories
  - Show dependency warnings

### 5. API Endpoints (Backend)
- [ ] GET `/api/products/{product_id}/compatible-accessories`
- [ ] POST `/api/products/{product_id}/validate-configuration`
- [ ] GET `/api/dependencies`
- [ ] POST `/api/dependencies`

## Phase 3.2: Configuration Builder UI

### 6. Configuration Builder Page
- [ ] Step 1: Select base product
- [ ] Step 2: Select accessories (with validation)
- [ ] Step 3: Review & save configuration
- [ ] Real-time validation display

### 7. Configuration Model & Database
- [ ] Create migrations for product_configurations table
- [ ] Create `ProductConfiguration` Model
- [ ] Create FilamentResource for saved configurations

## Phase 3.3: Dashboard & Monitoring

### 8. Dashboard Core
- [ ] Extend DashboardOverviewWidget with accessory stats
- [ ] Add recent configurations feed
- [ ] Add compatibility issues widget

## Next Steps

1. Create migration 031 for option_dependencies
2. Create models and resources
3. Test with sample data
4. Implement Configuration Builder UI

**Total Effort:** ~40-50 hours
**Timeline:** 1 week (full-time)
