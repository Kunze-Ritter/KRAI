# TODO: KRAI Admin Dashboard & Configuration System

> **Note:** This document was created before Laravel/Filament dashboard implementation. All UI features should be implemented in the existing Laravel/Filament dashboard at `laravel-admin/`.

> **Note:** For consolidated project-wide TODOs, see `/MASTER-TODO.md`
> This file focuses on dashboard-specific implementation details.

## Current Status: Phase 1 & 2 Complete, Phase 3 Ready to Build! 🚀

**Last Updated:** 2025-10-22 (10:38)

---

## 🎯 Vision

Ein vollständiges Admin Dashboard zum:
1. **Verwalten** von Products, Documents, Videos, Links
2. **Konfigurieren** von Produkten mit Accessories/Options
3. **Validieren** von Konfigurationen (Konflikte erkennen)
4. **Visualisieren** von Kompatibilitäten und Abhängigkeiten
5. **Monitoring** von System Status und Processing Queue
6. **CRUD Operations** für alle Entities (Create, Read, Update, Delete)

---

## ✅ Was bereits existiert (Backend)

### Database Schema
- ✅ `product_accessories` table (M:N) - Links products to accessories
- ✅ `option_dependencies` table - Models requires/excludes/alternative relationships
- ✅ 12 neue product_types (finisher_accessory, controller_accessory, image_controller, etc.)

### Backend Logic
- ✅ `accessory_linker.py` (280 lines) - Auto-links accessories during processing
- ✅ `configuration_validator.py` (320 lines) - Validates configurations
- ✅ `accessory_detector.py` (456 lines) - Detects 30+ accessory types
- ✅ `product_type_mapper.py` - Maps 200+ series to product types

### Sample Data
- ✅ 4 Dependencies in DB (PK-524, PK-526 → FS-533, FS-534)
- ✅ Migration 108 ready for more dependencies

---

## 📋 Phase 3: Dashboard & UI

### 3.0 Dashboard Core & Navigation ⭐ HIGHEST PRIORITY

**Goal:** Base dashboard structure with navigation and overview

**Features:**
- [ ] **Main Layout**
  - Sidebar navigation
  - Header with user info
  - Main content area
  - Responsive design (Desktop-first, mobile-friendly)

- [ ] **Dashboard Overview (Home)**
  - Statistics cards (Products, Documents, Videos, Chunks count)
  - Recent activity feed
  - System status indicators
  - Quick actions

- [ ] **Navigation Menu**
  - 📊 Overview (Dashboard home)
  - 📦 Products Management
  - 📄 Documents Management
  - 🎬 Videos Management
  - 🔗 Links Management
  - 🔧 Configuration Builder
  - ⚙️ Dependencies Management
  - ⚙️ Settings

**API Endpoints needed:**
```python
# GET /api/dashboard/stats
# Returns: { products_count, documents_count, videos_count, chunks_count }

# GET /api/dashboard/activity
# Returns: Recent activity feed (last 10 actions)

# GET /api/dashboard/status
# Returns: System status (DB connection, queue length, last backup)
```

**UI Framework:** Laravel/Filament (existing dashboard at `laravel-admin/`)
**Priority:** 🔥 HIGHEST (Foundation for everything)
**Effort:** 6-8 hours
**Blockers:** None

---

### 3.1 Products Management ⭐ HIGH PRIORITY

**Goal:** CRUD interface for products with filtering and search

**Features:**
- [ ] **Product List View**
  - Table with model_number, type, manufacturer, actions
  - Search by model number or name
  - Filter by product_type, manufacturer
  - Pagination (50 per page)
  - Sort by columns

- [ ] **Product Details View**
  - Show all product information
  - Show linked accessories
  - Show linked documents
  - Show linked videos

- [ ] **Create/Edit Product**
  - Form with all fields
  - Validation
  - Save to database

- [ ] **Delete Product**
  - Confirmation dialog
  - Cascade delete or prevent if linked

**API Endpoints needed:**
```python
# GET /api/products
# Query params: search, type, manufacturer, page, per_page
# Returns: Paginated product list

# GET /api/products/{id}
# Returns: Product details with accessories, documents, videos

# POST /api/products
# Body: Product data
# Returns: Created product

# PUT /api/products/{id}
# Body: Updated product data
# Returns: Updated product

# DELETE /api/products/{id}
# Returns: Success message
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 🔥 HIGH
**Effort:** 8-10 hours
**Blockers:** 3.0 (Dashboard Core)

---

### 3.2 Documents Management ⭐ HIGH PRIORITY

**Goal:** View, upload, delete, and reprocess documents

**Features:**
- [ ] **Document List View**
  - Table with filename, type, status, upload_date, actions
  - Search by filename
  - Filter by document_type, status
  - Status indicators: ✅ Done, ⏳ Processing, ❌ Error
  - Pagination

- [ ] **Upload Document**
  - Drag & drop or file picker
  - Progress indicator
  - Auto-start processing

- [ ] **Document Details View**
  - Show metadata
  - Show linked products
  - Show chunks count
  - Preview (if possible)

- [ ] **Delete Document**
  - Confirmation dialog
  - Delete document + chunks + embeddings

- [ ] **Reprocess Document**
  - Re-run processing pipeline
  - Update status

**API Endpoints needed:**
```python
# GET /api/documents
# Query params: search, type, status, page, per_page
# Returns: Paginated document list

# POST /api/documents/upload
# Body: FormData with file
# Returns: Document ID + processing status

# GET /api/documents/{id}
# Returns: Document details

# DELETE /api/documents/{id}
# Returns: Success message

# POST /api/documents/{id}/reprocess
# Returns: Processing job ID
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 🔥 HIGH
**Effort:** 8-10 hours
**Blockers:** 3.0 (Dashboard Core)

---

### 3.3 Videos Management ⭐ HIGH PRIORITY

**Goal:** Add, view, link, and manage videos

**Features:**
- [ ] **Video List View**
  - Table with title, platform, product, status, actions
  - Search by title or video_id
  - Filter by platform (YouTube, Vimeo, etc.), status
  - Status indicators: ✅ Linked, ⚠️ Needs Review, ❌ Error
  - Pagination

- [ ] **Add Video**
  - Form: video_url, platform, title (optional)
  - Auto-extract metadata from URL
  - Auto-enrich with AI

- [ ] **Video Details View**
  - Show metadata (title, description, duration, etc.)
  - Show linked products
  - Embedded video player
  - Transcript (if available)

- [ ] **Link Video to Product**
  - Search and select product
  - Save link

- [ ] **Delete Video**
  - Confirmation dialog
  - Remove from database

- [ ] **Re-enrich Video**
  - Re-run AI enrichment
  - Update metadata

**API Endpoints needed:**
```python
# GET /api/videos
# Query params: search, platform, status, product_id, page, per_page
# Returns: Paginated video list

# POST /api/videos
# Body: { video_url, platform, title }
# Returns: Created video + enrichment job ID

# GET /api/videos/{id}
# Returns: Video details with linked products

# POST /api/videos/{id}/link-product
# Body: { product_id }
# Returns: Success message

# DELETE /api/videos/{id}
# Returns: Success message

# POST /api/videos/{id}/re-enrich
# Returns: Enrichment job ID
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 🔥 HIGH
**Effort:** 8-10 hours
**Blockers:** 3.0 (Dashboard Core)

---

### 3.4 Links Management ⭐ HIGH PRIORITY

**Goal:** Add, view, and manage external links (manuals, support pages, etc.)

**Features:**
- [ ] **Links List View**
  - Table with url, title, type, linked_product, actions
  - Search by url or title
  - Filter by link_type (manual, support, video, etc.)
  - Pagination

- [ ] **Add Link**
  - Form: url, title, link_type, product_id (optional)
  - Auto-fetch title from URL (if possible)
  - Validate URL

- [ ] **Link Details View**
  - Show metadata
  - Show linked product
  - Preview (iframe or screenshot)

- [ ] **Edit Link**
  - Update url, title, type, product

- [ ] **Delete Link**
  - Confirmation dialog

**API Endpoints needed:**
```python
# GET /api/links
# Query params: search, type, product_id, page, per_page
# Returns: Paginated links list

# POST /api/links
# Body: { url, title, link_type, product_id }
# Returns: Created link

# GET /api/links/{id}
# Returns: Link details

# PUT /api/links/{id}
# Body: Updated link data
# Returns: Updated link

# DELETE /api/links/{id}
# Returns: Success message
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 🔥 HIGH
**Effort:** 6-8 hours
**Blockers:** 3.0 (Dashboard Core)

---

### 3.5 Product Configuration Builder ⭐ HIGH PRIORITY

**Goal:** Interactive UI to configure a product with accessories

**Features:**
- [ ] **Product Selection**
  - Select base product (e.g., bizhub C558)
  - Show compatible accessories (from `product_accessories` table)

- [ ] **Accessory Selection**
  - Drag & drop accessories to configuration
  - Visual indicators: ✅ compatible, ⚠️ requires, ❌ conflicts
  - Real-time validation using `configuration_validator.py`

- [ ] **Validation Display**
  - Show errors: "❌ PK-524 requires FS-533 (missing)"
  - Show warnings: "ℹ️ FS-533 and FS-534 are alternatives"
  - Show recommendations: "💡 Consider adding RU-513 (required for FS-534)"

- [ ] **Configuration Summary**
  - List all selected accessories
  - Total price (if available)
  - Export as PDF/JSON

**API Endpoints needed:**
```python
# GET /api/products/{product_id}/compatible-accessories
# Returns: List of compatible accessories with dependency info

# POST /api/products/{product_id}/validate-configuration
# Body: { "accessory_ids": ["id1", "id2"] }
# Returns: ValidationResult (valid, errors, warnings, recommendations)

# POST /api/products/{product_id}/save-configuration
# Body: { "name": "My Config", "accessory_ids": [...] }
# Returns: Configuration ID
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 🔥 HIGH
**Effort:** 12-16 hours
**Blockers:** None (backend ready!)

---

### 3.2 Dependency Management Dashboard ⭐ MEDIUM PRIORITY

**Goal:** Admin UI to manage option dependencies

**Features:**
- [ ] **View Dependencies**
  - Table view: Option → Depends On → Type → Notes
  - Filter by dependency_type (requires, excludes, alternative)
  - Search by product model number

- [ ] **Add Dependencies**
  - Select Option (e.g., PK-524)
  - Select Depends On (e.g., FS-533)
  - Select Type (requires/excludes/alternative)
  - Add notes
  - Save to `option_dependencies` table

- [ ] **Edit/Delete Dependencies**
  - Edit existing dependencies
  - Delete invalid dependencies
  - Bulk operations

- [ ] **Dependency Graph Visualization**
  - Visual graph showing product → accessory relationships
  - Color-coded: green (requires), red (excludes), blue (alternative)
  - Interactive: click to see details

**API Endpoints needed:**
```python
# GET /api/dependencies
# Returns: List of all dependencies with product details

# POST /api/dependencies
# Body: { "option_id", "depends_on_option_id", "dependency_type", "notes" }
# Returns: Created dependency

# PUT /api/dependencies/{id}
# Body: { "notes": "Updated notes" }
# Returns: Updated dependency

# DELETE /api/dependencies/{id}
# Returns: Success message
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 🔍 MEDIUM
**Effort:** 8-12 hours
**Blockers:** None

---

### 3.3 Accessory Compatibility Matrix 📊 MEDIUM PRIORITY

**Goal:** Visual matrix showing which accessories work with which products

**Features:**
- [ ] **Matrix View**
  - Rows: Products (bizhub C558, C658, etc.)
  - Columns: Accessories (FS-533, PK-524, RU-513, etc.)
  - Cells: ✅ compatible, ⚠️ requires other, ❌ not compatible

- [ ] **Filtering**
  - Filter by manufacturer
  - Filter by product type
  - Filter by accessory type

- [ ] **Export**
  - Export as CSV
  - Export as PDF
  - Print-friendly view

**API Endpoints needed:**
```python
# GET /api/compatibility-matrix
# Query params: manufacturer, product_type, accessory_type
# Returns: Matrix data structure
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 📌 MEDIUM
**Effort:** 6-8 hours
**Blockers:** None

---

### 3.4 Product Accessories Overview 📦 LOW PRIORITY

**Goal:** Simple overview of all products and their accessories

**Features:**
- [ ] **Product List**
  - Show all products with accessories count
  - Click to expand and see accessories

- [ ] **Accessory Details**
  - Show accessory type
  - Show compatibility notes
  - Show if standard or optional

- [ ] **Quick Actions**
  - Add new accessory link
  - Edit compatibility notes
  - Mark as standard/optional

**API Endpoints needed:**
```python
# GET /api/products/{product_id}/accessories
# Returns: List of accessories with details

# POST /api/products/{product_id}/accessories
# Body: { "accessory_id", "is_standard", "compatibility_notes" }
# Returns: Created link
```

**UI Framework:** Laravel/Filament (existing dashboard)
**Priority:** 📌 LOW
**Effort:** 4-6 hours
**Blockers:** None

---

## 🛠️ Technical Stack

### Frontend
- **Framework:** Laravel 12 + Filament 4
- **Styling:** TailwindCSS (built into Filament)
- **State Management:** Livewire (built into Filament)
- **Routing:** Laravel routing
- **Graph Visualization:** Filament Charts plugin, Livewire + ApexCharts, or Filament Table widgets with tree views
- **Tables:** Filament Tables (built-in)
- **Forms:** Filament Forms (built-in)
- **Icons:** Heroicons (built into Filament)

### Backend (Already exists!)
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL
- **Validation:** `configuration_validator.py`
- **Auto-linking:** `accessory_linker.py`

### API Design
```python
# New routes to add to backend/api/routes/

# products.py
@router.get("/products/{product_id}/compatible-accessories")
@router.post("/products/{product_id}/validate-configuration")
@router.post("/products/{product_id}/save-configuration")
@router.get("/products/{product_id}/accessories")
@router.post("/products/{product_id}/accessories")

# dependencies.py (NEW FILE)
@router.get("/dependencies")
@router.post("/dependencies")
@router.put("/dependencies/{id}")
@router.delete("/dependencies/{id}")
@router.get("/dependencies/graph")

# compatibility.py (NEW FILE)
@router.get("/compatibility-matrix")
```

---

## 📊 Implementation Roadmap

### 🔥 Week 1: Dashboard Foundation (3.0)
**Goal:** Extend existing Laravel/Filament dashboard
1. ✅ Use existing Laravel/Filament setup at `laravel-admin/`
2. ✅ Add new Filament pages and resources as needed
3. ✅ Extend navigation in `KradminPanelProvider`
4. ✅ Create dashboard widgets for overview stats
5. ✅ Build Dashboard Overview (Stats, Activity, Status)
6. ✅ Create API endpoints for dashboard stats (if needed beyond existing)

**Deliverable:** Extended dashboard with product configuration features
**Effort:** 6-8 hours

---

### 🔥 Week 2: Core Management Pages (3.1, 3.2, 3.3, 3.4)
**Goal:** CRUD for Products, Documents, Videos, Links
1. ✅ Products Management (List, Create, Edit, Delete)
2. ✅ Documents Management (List, Upload, Delete, Reprocess)
3. ✅ Videos Management (List, Add, Link, Delete, Re-enrich)
4. ✅ Links Management (List, Add, Edit, Delete)
5. ✅ Create all API endpoints
6. ✅ Implement filtering, search, pagination

**Deliverable:** Full CRUD for all main entities
**Effort:** 30-36 hours (3-4 days)

---

### 🔥 Week 3: Configuration Builder (3.5)
**Goal:** Multi-step product configuration with validation
1. ✅ Step 1: Product Selection
2. ✅ Step 2: Accessory Selection (with auto-add dependencies)
3. ✅ Step 3: Review & Validation
4. ✅ Real-time validation display
5. ✅ Save & export configurations

**Deliverable:** Working configuration builder
**Effort:** 12-16 hours (2 days)

---

### 🔍 Week 4: Dependencies & Advanced Features (3.6, 3.7)
**Goal:** Dependency management and visualization
1. ✅ In Filament dashboard: Dependencies Management (CRUD)
2. ✅ In Filament dashboard: Dependency Graph Visualization (Filament Charts/Livewire + ApexCharts)
3. ✅ In Filament dashboard: Compatibility Matrix
4. ✅ In Filament dashboard: Bulk operations

**Deliverable:** Complete dependency management system
**Effort:** 12-16 hours (2 days)

---

### 📌 Week 5: Polish & Nice-to-Haves
**Goal:** Improve UX and add advanced features
1. ✅ Drag & Drop for configuration builder
2. ✅ Export as PDF
3. ✅ Share configurations via link
4. ✅ Configuration templates
5. ✅ Mobile optimization
6. ✅ Performance optimization

**Deliverable:** Production-ready dashboard
**Effort:** 8-12 hours (1-2 days)

---

## 🎯 Total Effort Estimate
- **Week 1 (Foundation):** 6-8 hours
- **Week 2 (CRUD):** 30-36 hours
- **Week 3 (Configuration):** 12-16 hours
- **Week 4 (Dependencies):** 12-16 hours
- **Week 5 (Polish):** 8-12 hours

**Total:** 68-88 hours (2-3 weeks full-time, 4-6 weeks part-time)

---

## 🎯 Success Criteria

### Must Have (MVP)
- ✅ User can select a product
- ✅ User can add accessories to configuration
- ✅ System validates configuration in real-time
- ✅ User sees errors/warnings/recommendations
- ✅ User can save configuration

### Should Have
- ✅ Admin can add/edit dependencies
- ✅ Visual dependency graph
- ✅ Compatibility matrix view

### Nice to Have
- ✅ Export configurations as PDF
- ✅ Price calculation
- ✅ Configuration templates
- ✅ Share configurations via link

---

## 📝 Example User Flow

### Scenario: Configure bizhub C558 with Finisher

1. **User selects base product:** bizhub C558
2. **System shows compatible accessories:**
   - FS-533 (Finisher) ✅
   - FS-534 (Finisher) ✅
   - PK-524 (Punch Kit) ⚠️ requires FS-533
   - RU-513 (Relay Unit) ⚠️ required for FS-534
3. **User adds FS-534 to configuration**
4. **System validates:**
   - ❌ Error: "FS-534 requires RU-513 (missing)"
5. **User adds RU-513**
6. **System validates:**
   - ✅ Valid configuration!
7. **User adds PK-524**
8. **System validates:**
   - ❌ Error: "PK-524 requires FS-533, but FS-534 is selected"
   - 💡 Recommendation: "Remove FS-534 and add FS-533, or remove PK-524"
9. **User removes PK-524**
10. **System validates:**
    - ✅ Valid configuration!
11. **User saves configuration:** "C558 with FS-534 Finisher"

---

## 🚀 Next Steps

1. **Create API endpoints** for configuration validation in `backend/api/routes/`
2. **Extend existing Filament dashboard** with new Pages/Resources at `laravel-admin/app/Filament/`
3. **Build Configuration Builder** UI in Filament (Phase 3.1) using `php artisan make:filament-page ConfigurationBuilder`
4. **Test with sample data** via Filament forms and tables
5. **Add more dependencies** to database via Filament resource or seeder
6. **Build Dependency Dashboard** in Filament (Phase 3.2) using Filament widgets and custom pages

---

## 📚 References

- **Backend Files:**
  - `backend/processors/accessory_linker.py`
  - `backend/utils/configuration_validator.py`
  - `backend/utils/accessory_detector.py`
  - `backend/utils/product_type_mapper.py`

- **Database:**
  - `krai_core.product_accessories` table
  - `krai_core.option_dependencies` table
  - Migration 106, 107, 108

- **Related TODOs:**
  - `TODO_PRODUCT_ACCESSORIES.md` - Phase 1 & 2 documentation
  - `TODO.md` - Main project TODO

---

**Status:** 🟢 Ready to start Phase 3!
**Next Action:** Create API endpoints for configuration validation
**Estimated Time:** 2-3 weeks for full dashboard
