# Phase 6 API Reference

## Overview

This document provides comprehensive API reference for KRAI Phase 6, including all new multimodal AI features, hierarchical document processing, SVG vector graphics handling, and advanced search capabilities.

## Table of Contents

- [Authentication](#authentication)
- [Base URLs](#base-urls)
- [Common Headers](#common-headers)
- [Response Format](#response-format)
- [Document Processing APIs](#document-processing-apis)
- [Multimodal Search APIs](#multimodal-search-apis)
- [Context Extraction APIs](#context-extraction-apis)
- [SVG Processing APIs](#svg-processing-apis)
- [Hierarchical Chunking APIs](#hierarchical-chunking-apis)
- [Analytics APIs](#analytics-apis)
- [Configuration APIs](#configuration-apis)
- [Error Codes](#error-codes)

## Authentication

### JWT Authentication

```http
Authorization: Bearer <jwt_token>
```

### API Key Authentication

```http
X-API-Key: <api_key>
```

### OAuth2 Authentication

```http
Authorization: Bearer <oauth2_token>
```

## Base URLs

| Environment | Base URL |
|-------------|----------|
| Development | `http://localhost:8000/api/v1` |
| Staging | `https://staging.krai.ai/api/v1` |
| Production | `https://api.krai.ai/api/v1` |

## Common Headers

```http
Content-Type: application/json
Accept: application/json
X-Request-ID: <unique_request_id>
X-Client-Version: <client_version>
```

## Response Format

### Success Response

```json
{
  "success": true,
  "data": {
    // Response data
  },
  "metadata": {
    "request_id": "req_123456789",
    "timestamp": "2025-12-08T10:30:00Z",
    "duration_ms": 250
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": {
      "field": "query",
      "reason": "Query too short"
    }
  },
  "metadata": {
    "request_id": "req_123456789",
    "timestamp": "2025-12-08T10:30:00Z"
  }
}
```

## Document Processing APIs

### Upload Document with Phase 6 Features

Upload and process a document with all Phase 6 features enabled.

```http
POST /api/v1/documents/upload
```

**Request Body (multipart/form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| file | File | Yes | Document file (PDF, DOCX, etc.) |
| enable_hierarchical_chunking | boolean | No | Enable hierarchical structure detection (default: true) |
| enable_svg_extraction | boolean | No | Enable SVG vector graphics processing (default: true) |
| enable_context_extraction | boolean | No | Enable AI context extraction (default: true) |
| chunk_size | integer | No | Chunk size for text processing (default: 1000) |
| chunk_overlap | integer | No | Chunk overlap (default: 100) |
| detect_error_codes | boolean | No | Detect error code boundaries (default: true) |
| link_chunks | boolean | No | Create cross-chunk links (default: true) |

**Example Request:**

```bash
curl -X POST "https://api.krai.ai/api/v1/documents/upload" \
  -H "Authorization: Bearer <jwt_token>" \
  -F "file=@document.pdf" \
  -F "enable_hierarchical_chunking=true" \
  -F "enable_svg_extraction=true" \
  -F "enable_context_extraction=true" \
  -F "chunk_size=1000"
```

**Response:**

```json
{
  "success": true,
  "data": {
    "document_id": "doc_123456789",
    "status": "processing",
    "processing_stages": [
      {
        "stage": "upload",
        "status": "completed",
        "duration_ms": 500
      },
      {
        "stage": "text_extraction",
        "status": "in_progress"
      },
      {
        "stage": "hierarchical_chunking",
        "status": "pending"
      },
      {
        "stage": "svg_extraction",
        "status": "pending"
      },
      {
        "stage": "context_extraction",
        "status": "pending"
      }
    ],
    "estimated_completion_time": "2025-12-08T10:35:00Z"
  },
  "metadata": {
    "request_id": "req_123456789",
    "timestamp": "2025-12-08T10:30:00Z"
  }
}
```

### Get Document Processing Status

Check the status of document processing with Phase 6 features.

```http
GET /api/v1/documents/{document_id}/status
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| document_id | string | Document ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "document_id": "doc_123456789",
    "status": "completed",
    "progress": 100,
    "processing_stages": [
      {
        "stage": "upload",
        "status": "completed",
        "duration_ms": 500,
        "details": {
          "file_size": 5242880,
          "pages": 25
        }
      },
      {
        "stage": "text_extraction",
        "status": "completed",
        "duration_ms": 2000,
        "details": {
          "characters_extracted": 15000,
          "pages_processed": 25
        }
      },
      {
        "stage": "hierarchical_chunking",
        "status": "completed",
        "duration_ms": 1500,
        "details": {
          "chunks_created": 45,
          "hierarchical_sections": 12,
          "error_code_boundaries": 8,
          "cross_chunk_links": 37
        }
      },
      {
        "stage": "svg_extraction",
        "status": "completed",
        "duration_ms": 3000,
        "details": {
          "svg_elements_found": 15,
          "svg_converted": 15,
          "vision_analysis_completed": 15
        }
      },
      {
        "stage": "context_extraction",
        "status": "completed",
        "duration_ms": 4000,
        "details": {
          "images_processed": 20,
          "videos_processed": 3,
          "tables_processed": 5,
          "links_processed": 8,
          "contexts_generated": 36
        }
      }
    ],
    "completion_time": "2025-12-08T10:34:30Z",
    "total_duration_ms": 11000
  }
}
```

### Get Document with Phase 6 Data

Retrieve document data including all Phase 6 processed information.

```http
GET /api/v1/documents/{document_id}
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| include_chunks | boolean | No | Include hierarchical chunks (default: true) |
| include_images | boolean | No | Include processed images (default: true) |
| include_contexts | boolean | No | Include extracted contexts (default: true) |
| include_svg_data | boolean | No | Include SVG processing data (default: true) |
| chunk_limit | integer | No | Limit number of chunks returned (default: 100) |

**Response:**

```json
{
  "success": true,
  "data": {
    "document_id": "doc_123456789",
    "title": "Technical Manual",
    "metadata": {
      "pages": 25,
      "file_size": 5242880,
      "processing_completed": "2025-12-08T10:34:30Z"
    },
    "chunks": [
      {
        "id": "chunk_001",
        "content": "Chapter 1: Introduction...",
        "section_hierarchy": ["Chapter 1", "Introduction"],
        "section_level": 2,
        "previous_chunk_id": null,
        "next_chunk_id": "chunk_002",
        "error_code": null,
        "chunk_type": "text",
        "chunk_id": "chunk_001"
      },
      {
        "id": "chunk_002",
        "content": "Error Code 001: Paper jam...",
        "section_hierarchy": ["Chapter 2", "Error Codes", "Error Code 001"],
        "section_level": 3,
        "previous_chunk_id": "chunk_001",
        "next_chunk_id": "chunk_003",
        "error_code": "001",
        "chunk_type": "error_code",
        "chunk_id": "chunk_002"
      }
    ],
    "images": [
      {
        "id": "img_001",
        "url": "https://storage.krai.ai/images/doc_123456789_img_001.png",
        "image_type": "vector",
        "vector_graphic": true,
        "svg_content": "<svg>...</svg>",
        "vision_analysis": {
          "description": "Technical diagram showing printer components",
          "objects": ["toner_cartridge", "fuser_unit", "paper_path"],
          "confidence": 0.92
        },
        "context": "Diagram showing the internal components of the laser printer including the toner cartridge position and paper feeding mechanism.",
        "chunk_id": "img_001"
      }
    ],
    "contexts": [
      {
        "id": "ctx_001",
        "media_type": "image",
        "media_id": "img_001",
        "context": "Technical diagram showing printer components with labels for toner cartridge, fuser unit, and paper path.",
        "chunk_id": "ctx_001"
      }
    ]
  }
}
```
**Note:** Embedding IDs map to chunk IDs because embeddings are stored in `krai_intelligence.chunks.embedding`.

## Multimodal Search APIs

### Multimodal Search

Search across all content types including text, images, videos, tables, and links.

```http
POST /api/v1/search/multimodal
```

**Request Body:**

```json
{
  "query": "HP LaserJet paper jam error",
  "modalities": ["text", "image", "video", "table", "link"],
  "threshold": 0.5,
  "limit": 20,
  "filters": {
    "document_types": ["technical_manual", "user_guide"],
    "manufacturers": ["HP", "Canon"],
    "date_range": {
      "start": "2025-01-01",
      "end": "2025-12-31"
    }
  },
  "boosting": {
    "recent_documents": 1.2,
    "error_codes": 1.5,
    "technical_diagrams": 1.3
  },
  "enable_two_stage_retrieval": true
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "query": "HP LaserJet paper jam error",
    "total_results": 15,
    "search_time_ms": 450,
    "results": [
      {
        "id": "chunk_002",
        "type": "text",
        "content": "Error Code 13.XX: Paper jam early in the paper path. This error occurs when paper fails to reach the first sensor...",
        "similarity": 0.89,
        "document_id": "doc_123456789",
        "document_title": "HP LaserJet Pro Manual",
        "section_hierarchy": ["Chapter 2", "Error Codes"],
        "error_code": "13.XX",
        "highlights": [
          "Error Code <mark>13.XX</mark>: <mark>paper jam</mark> early in the paper path"
        ]
      },
      {
        "id": "img_001",
        "type": "image",
        "content": "Technical diagram showing paper path and jam locations",
        "similarity": 0.82,
        "document_id": "doc_123456789",
        "document_title": "HP LaserJet Pro Manual",
        "image_url": "https://storage.krai.ai/images/doc_123456789_img_001.png",
        "vision_analysis": {
          "description": "Diagram showing paper jam locations and clearing procedures",
          "objects": ["paper_path", "sensors", "jam_points"]
        },
        "context": "This diagram illustrates the common paper jam locations in HP LaserJet printers and shows the proper procedure for clearing jams."
      },
      {
        "id": "video_001",
        "type": "video",
        "content": "Step-by-step video tutorial for clearing paper jams",
        "similarity": 0.78,
        "document_id": "doc_123456789",
        "document_title": "HP LaserJet Pro Manual",
        "video_url": "https://storage.krai.ai/videos/paper_jam_tutorial.mp4",
        "duration": 180,
        "context": "This video demonstrates the complete process of identifying and clearing paper jams in HP LaserJet printers."
      }
    ],
    "aggregations": {
      "by_type": {
        "text": 8,
        "image": 4,
        "video": 2,
        "table": 1
      },
      "by_document": {
        "doc_123456789": 12,
        "doc_987654321": 3
      },
      "by_error_code": {
        "13.XX": 5,
        "50.XX": 2
      }
    }
  }
}
```

### Context-Aware Image Search

Search images using their extracted context and Vision AI analysis.

```http
POST /api/v1/search/images/context
```

**Request Body:**

```json
{
  "query": "diagram showing toner cartridge replacement",
  "threshold": 0.4,
  "limit": 10,
  "include_svg": true,
  "filters": {
    "image_types": ["vector", "raster"],
    "document_types": ["technical_manual"]
  }
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "total_results": 7,
    "search_time_ms": 320,
    "results": [
      {
        "id": "img_001",
        "image_url": "https://storage.krai.ai/images/doc_123456789_img_001.png",
        "image_type": "vector",
        "similarity": 0.91,
        "context": "Diagram showing the proper procedure for replacing the toner cartridge in HP LaserJet printers",
        "vision_analysis": {
          "description": "Technical diagram with numbered steps for toner cartridge replacement",
          "objects": ["toner_cartridge", "printer_body", "release_lever"],
          "confidence": 0.89
        },
        "document_id": "doc_123456789",
        "page_number": 15
      }
    ]
  }
}
```

### Hierarchical Navigation

Navigate through document structure using hierarchical chunking.

```http
GET /api/v1/documents/{document_id}/navigation
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| section_path | string | No | Navigate to specific section (e.g., "Chapter 2/Section 2.1") |
| level | integer | No | Section level to return (default: all) |
| include_error_codes | boolean | No | Include error code boundaries (default: true) |

**Response:**

```json
{
  "success": true,
  "data": {
    "document_id": "doc_123456789",
    "hierarchy": [
      {
        "section_id": "chapter_1",
        "title": "Chapter 1: Introduction",
        "level": 1,
        "path": ["Chapter 1"],
        "chunk_ids": ["chunk_001", "chunk_002"],
        "child_sections": [
          {
            "section_id": "section_1_1",
            "title": "Section 1.1: Overview",
            "level": 2,
            "path": ["Chapter 1", "Section 1.1"],
            "chunk_ids": ["chunk_003", "chunk_004"]
          }
        ]
      },
      {
        "section_id": "chapter_2",
        "title": "Chapter 2: Error Codes",
        "level": 1,
        "path": ["Chapter 2"],
        "chunk_ids": ["chunk_005", "chunk_006"],
        "error_codes": ["13.XX", "50.XX", "49.XXXX"],
        "child_sections": [
          {
            "section_id": "section_2_1",
            "title": "Section 2.1: Common Errors",
            "level": 2,
            "path": ["Chapter 2", "Section 2.1"],
            "error_codes": ["13.XX", "50.XX"]
          }
        ]
      }
    ]
  }
}
```

## Context Extraction APIs

### Extract Context from Media

Extract AI-generated context from various media types.

```http
POST /api/v1/context/extract
```

**Request Body:**

```json
{
  "media_type": "image",
  "media_data": {
    "url": "https://example.com/image.jpg",
    "type": "technical_diagram",
    "description": "Printer components diagram"
  },
  "max_length": 1000,
  "include_embedding": true,
  "model": "llava-phi3"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "context_id": "ctx_123456789",
    "context": "This technical diagram illustrates the internal components of a laser printer, showing the toner cartridge position, fuser unit location, and paper feeding mechanism. The diagram includes numbered callouts indicating the proper sequence for maintenance procedures.",
    "embedding_id": "emb_123456789",
    "extraction_time_ms": 1200,
    "confidence": 0.89,
    "model_used": "llava-phi3",
    "media_analysis": {
      "objects_detected": ["toner_cartridge", "fuser_unit", "paper_path"],
      "text_detected": ["Toner", "Fuser", "Paper Path"],
      "layout_analysis": "technical_diagram"
    }
  }
}
```

### Batch Context Extraction

Extract context from multiple media items in parallel.

```http
POST /api/v1/context/extract/batch
```

**Request Body:**

```json
{
  "media_items": [
    {
      "media_type": "image",
      "media_data": {
        "url": "https://example.com/image1.jpg",
        "type": "diagram"
      }
    },
    {
      "media_type": "video",
      "media_data": {
        "url": "https://example.com/video1.mp4",
        "title": "Tutorial video",
        "duration": 300
      }
    },
    {
      "media_type": "table",
      "media_data": {
        "content": "Error Code | Description | Solution\n001 | Paper Jam | Open cover",
        "headers": ["Error Code", "Description", "Solution"]
      }
    }
  ],
  "batch_size": 5,
  "max_length": 500,
  "include_embeddings": true
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "batch_id": "batch_123456789",
    "total_items": 3,
    "processed_items": 3,
    "failed_items": 0,
    "processing_time_ms": 3500,
    "results": [
      {
        "item_index": 0,
        "context_id": "ctx_001",
        "context": "Technical diagram showing printer components...",
        "embedding_id": "emb_001",
        "success": true
      },
      {
        "item_index": 1,
        "context_id": "ctx_002",
        "context": "Tutorial video demonstrating maintenance procedures...",
        "embedding_id": "emb_002",
        "success": true
      },
      {
        "item_index": 2,
        "context_id": "ctx_003",
        "context": "Troubleshooting table with error codes and solutions...",
        "embedding_id": "emb_003",
        "success": true
      }
    ]
  }
}
```

## SVG Processing APIs

### Process SVG Content

Extract and process SVG vector graphics from documents.

```http
POST /api/v1/svg/process
```

**Request Body:**

```json
{
  "svg_content": "<svg width='200' height='100' xmlns='http://www.w3.org/2000/svg'>...</svg>",
  "document_id": "doc_123456789",
  "page_number": 1,
  "conversion_settings": {
    "dpi": 300,
    "max_dimension": 2048,
    "background_color": "white",
    "quality": 95
  },
  "enable_vision_analysis": true,
  "vision_model": "llava-phi3"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "svg_id": "svg_123456789",
    "png_converted": true,
    "png_url": "https://storage.krai.ai/images/doc_123456789_svg_001.png",
    "png_size": {
      "width": 2048,
      "height": 1024,
      "file_size": 245760
    },
    "vision_analysis": {
      "description": "Technical diagram showing printer components with labeled parts",
      "objects": [
        {
          "name": "toner_cartridge",
          "confidence": 0.95,
          "bbox": [100, 200, 300, 400]
        },
        {
          "name": "fuser_unit",
          "confidence": 0.88,
          "bbox": [400, 200, 600, 400]
        }
      ],
      "text_detected": ["Toner", "Fuser", "Paper Path"],
      "confidence": 0.91
    },
    "processing_time_ms": 2100,
    "svg_metadata": {
      "elements_count": 15,
      "text_elements": 3,
      "graphic_elements": 12,
      "complexity_score": 0.7
    }
  }
}
```

### Extract SVG from Document

Extract all SVG elements from a processed document.

```http
GET /api/v1/documents/{document_id}/svg
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| include_analysis | boolean | No | Include Vision AI analysis (default: true) |
| page_limit | integer | No | Limit pages to process (default: all) |

**Response:**

```json
{
  "success": true,
  "data": {
    "document_id": "doc_123456789",
    "total_svg_elements": 25,
    "svg_elements": [
      {
        "svg_id": "svg_001",
        "page_number": 1,
        "png_url": "https://storage.krai.ai/images/doc_123456789_svg_001.png",
        "svg_content": "<svg>...</svg>",
        "vision_analysis": {
          "description": "Company logo",
          "objects": ["logo"],
          "confidence": 0.95
        }
      },
      {
        "svg_id": "svg_002",
        "page_number": 5,
        "png_url": "https://storage.krai.ai/images/doc_123456789_svg_002.png",
        "svg_content": "<svg>...</svg>",
        "vision_analysis": {
          "description": "Technical diagram of printer mechanism",
          "objects": ["gears", "rollers", "sensors"],
          "confidence": 0.89
        }
      }
    ]
  }
}
```

## Hierarchical Chunking APIs

### Create Hierarchical Chunks

Create hierarchical chunks from document content.

```http
POST /api/v1/chunks/hierarchical
```

**Request Body:**

```json
{
  "content": "# Document Title\n\n## Chapter 1\n\nContent here...\n\n### Section 1.1\n\nMore content...",
  "document_id": "doc_123456789",
  "chunking_options": {
    "chunk_size": 1000,
    "chunk_overlap": 100,
    "min_chunk_size": 30,
    "detect_error_codes": true,
    "link_chunks": true,
    "preserve_structure": true
  },
  "embedding_options": {
    "generate_embeddings": true,
    "model": "nomic-embed-text"
  }
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "chunking_id": "chunk_123456789",
    "total_chunks": 15,
    "hierarchical_sections": 8,
    "error_code_boundaries": 3,
    "cross_chunk_links": 12,
    "chunks": [
      {
        "chunk_id": "chunk_001",
        "content": "Document Title and introduction...",
        "section_hierarchy": ["Document Title"],
        "section_level": 1,
        "previous_chunk_id": null,
        "next_chunk_id": "chunk_002",
        "error_code": null,
        "chunk_type": "title",
        "embedding_id": "emb_001"
      },
      {
        "chunk_id": "chunk_005",
        "content": "Error Code 001: Paper jam...",
        "section_hierarchy": ["Chapter 1", "Error Codes", "Error Code 001"],
        "section_level": 3,
        "previous_chunk_id": "chunk_004",
        "next_chunk_id": "chunk_006",
        "error_code": "001",
        "chunk_type": "error_code",
        "embedding_id": "emb_005"
      }
    ],
    "processing_time_ms": 1800
  }
}
```

### Navigate Chunk Hierarchy

Navigate through chunk hierarchy using cross-chunk links.

```http
GET /api/v1/chunks/{chunk_id}/navigate
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| direction | string | No | Navigation direction: "next", "previous", "parent", "children" |
| levels | integer | No | Number of levels to navigate (default: 1) |

**Response:**

```json
{
  "success": true,
  "data": {
    "current_chunk": {
      "chunk_id": "chunk_005",
      "content": "Error Code 001: Paper jam...",
      "section_hierarchy": ["Chapter 1", "Error Codes", "Error Code 001"],
      "section_level": 3
    },
    "navigation": {
      "previous_chunk": {
        "chunk_id": "chunk_004",
        "content": "Introduction to error codes...",
        "section_hierarchy": ["Chapter 1", "Error Codes"],
        "section_level": 2
      },
      "next_chunk": {
        "chunk_id": "chunk_006",
        "content": "Error Code 002: Toner low...",
        "section_hierarchy": ["Chapter 1", "Error Codes", "Error Code 002"],
        "section_level": 3
      },
      "parent_section": {
        "chunk_id": "chunk_003",
        "content": "Chapter 1: Error Codes overview...",
        "section_hierarchy": ["Chapter 1", "Error Codes"],
        "section_level": 2
      }
    }
  }
}
```

## Analytics APIs

### Get Phase 6 Analytics

Retrieve analytics for Phase 6 features usage and performance.

```http
GET /api/v1/analytics/phase6
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| start_date | string | No | Start date (ISO 8601) |
| end_date | string | No | End date (ISO 8601) |
| metrics | string | No | Comma-separated metrics list |
| granularity | string | No | Time granularity: hour, day, week, month |

**Response:**

```json
{
  "success": true,
  "data": {
    "period": {
      "start": "2025-12-01T00:00:00Z",
      "end": "2025-12-08T00:00:00Z",
      "granularity": "day"
    },
    "metrics": {
      "hierarchical_chunking": {
        "documents_processed": 1250,
        "chunks_created": 15600,
        "error_codes_detected": 3400,
        "cross_chunk_links": 12200,
        "average_processing_time_ms": 1500
      },
      "svg_processing": {
        "svg_elements_processed": 8900,
        "png_conversions": 8900,
        "vision_analysis_completed": 8900,
        "average_processing_time_ms": 2200
      },
      "multimodal_search": {
        "total_searches": 15400,
        "text_searches": 8900,
        "image_searches": 3200,
        "video_searches": 1800,
        "table_searches": 1500,
        "average_search_time_ms": 450,
        "average_similarity_score": 0.72
      },
      "context_extraction": {
        "images_processed": 12300,
        "videos_processed": 2100,
        "tables_processed": 3400,
        "links_processed": 5600,
        "contexts_generated": 23400,
        "average_processing_time_ms": 1200
      }
    },
    "performance": {
      "api_response_times": {
        "p50": 250,
        "p95": 800,
        "p99": 1500
      },
      "error_rates": {
        "hierarchical_chunking": 0.02,
        "svg_processing": 0.01,
        "multimodal_search": 0.005,
        "context_extraction": 0.015
      }
    }
  }
}
```

### Get Feature Usage Statistics

Get detailed usage statistics for specific Phase 6 features.

```http
GET /api/v1/analytics/usage/{feature}
```

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| feature | string | Feature name: hierarchical-chunking, svg-processing, multimodal-search, context-extraction |

**Response:**

```json
{
  "success": true,
  "data": {
    "feature": "multimodal-search",
    "usage_breakdown": {
      "by_modality": {
        "text": 58.5,
        "image": 20.8,
        "video": 11.7,
        "table": 9.0
      },
      "by_query_type": {
        "error_code_search": 35.2,
        "technical_specification": 28.5,
        "troubleshooting": 22.1,
        "general_search": 14.2
      },
      "by_user_type": {
        "technician": 45.0,
        "support_agent": 30.0,
        "end_user": 25.0
      }
    },
    "performance_metrics": {
      "average_query_length": 4.2,
      "average_results_returned": 12.5,
      "click_through_rate": 0.68,
      "success_rate": 0.94
    }
  }
}
```

## Configuration APIs

### Get Phase 6 Configuration

Retrieve current Phase 6 feature configuration.

```http
GET /api/v1/config/phase6
```

**Response:**

```json
{
  "success": true,
  "data": {
    "hierarchical_chunking": {
      "enabled": true,
      "chunk_size": 1000,
      "chunk_overlap": 100,
      "min_chunk_size": 30,
      "detect_error_codes": true,
      "link_chunks": true
    },
    "svg_processing": {
      "enabled": true,
      "conversion_dpi": 300,
      "max_dimension": 2048,
      "quality": 95,
      "background_color": "white",
      "vision_model": "llava-phi3"
    },
    "multimodal_search": {
      "enabled": true,
      "threshold": 0.5,
      "limit": 20,
      "enable_two_stage_retrieval": true,
      "modalities": ["text", "image", "video", "table", "link"]
    },
    "context_extraction": {
      "enabled": true,
      "max_length": 1000,
      "batch_size": 10,
      "vision_model": "llava-phi3",
      "text_model": "llama3.1:8b"
    }
  }
}
```

### Update Phase 6 Configuration

Update Phase 6 feature configuration.

```http
PUT /api/v1/config/phase6
```

**Request Body:**

```json
{
  "hierarchical_chunking": {
    "chunk_size": 1200,
    "chunk_overlap": 150
  },
  "multimodal_search": {
    "threshold": 0.4,
    "limit": 25
  },
  "context_extraction": {
    "max_length": 1200,
    "batch_size": 15
  }
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "configuration_updated": true,
    "updated_fields": [
      "hierarchical_chunking.chunk_size",
      "hierarchical_chunking.chunk_overlap",
      "multimodal_search.threshold",
      "multimodal_search.limit",
      "context_extraction.max_length",
      "context_extraction.batch_size"
    ],
    "restart_required": false
  }
}
```

## Error Codes

### Phase 6 Specific Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| PHASE6_FEATURE_DISABLED | 400 | Requested Phase 6 feature is disabled |
| HIERARCHICAL_CHUNKING_FAILED | 422 | Hierarchical chunking processing failed |
| SVG_PROCESSING_FAILED | 422 | SVG processing or conversion failed |
| VISION_AI_UNAVAILABLE | 503 | Vision AI service is unavailable |
| MULTIMODAL_SEARCH_FAILED | 422 | Multimodal search processing failed |
| CONTEXT_EXTRACTION_FAILED | 422 | Context extraction failed |
| EMBEDDING_GENERATION_FAILED | 422 | Embedding generation failed |
| CROSS_CHUNK_LINKING_FAILED | 422 | Cross-chunk linking failed |
| SVG_CONVERSION_TIMEOUT | 408 | SVG to PNG conversion timed out |
| AI_MODEL_OVERLOADED | 503 | AI model is overloaded, try again later |

### Example Error Response

```json
{
  "success": false,
  "error": {
    "code": "SVG_PROCESSING_FAILED",
    "message": "Failed to process SVG content",
    "details": {
      "svg_id": "svg_123456789",
      "reason": "Invalid SVG format: missing namespace declaration",
      "suggestion": "Ensure SVG content includes xmlns='http://www.w3.org/2000/svg'"
    }
  },
  "metadata": {
    "request_id": "req_123456789",
    "timestamp": "2025-12-08T10:30:00Z"
  }
}
```

## Rate Limiting

### Phase 6 API Rate Limits

| Endpoint | Rate Limit | Burst Limit |
|----------|------------|-------------|
| `/api/v1/documents/upload` | 10 requests/minute | 20 requests |
| `/api/v1/search/multimodal` | 100 requests/minute | 200 requests |
| `/api/v1/context/extract` | 50 requests/minute | 100 requests |
| `/api/v1/svg/process` | 30 requests/minute | 60 requests |
| `/api/v1/chunks/hierarchical` | 40 requests/minute | 80 requests |

### Rate Limit Headers

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1702035600
```

## SDK Examples

### Python SDK

```python
from krai_sdk import KRAIClient

# Initialize client
client = KRAIClient(
    base_url="https://api.krai.ai",
    api_key="your_api_key"
)

# Upload document with Phase 6 features
document = client.documents.upload(
    file="document.pdf",
    enable_hierarchical_chunking=True,
    enable_svg_extraction=True,
    enable_context_extraction=True
)

# Perform multimodal search
results = client.search.multimodal(
    query="HP LaserJet paper jam",
    modalities=["text", "image", "video"],
    threshold=0.5
)

# Extract context from image
context = client.context.extract(
    media_type="image",
    media_data={"url": "https://example.com/diagram.png"},
    max_length=1000
)
```

### JavaScript SDK

```javascript
import { KRAIClient } from '@krai/sdk';

// Initialize client
const client = new KRAIClient({
  baseURL: 'https://api.krai.ai',
  apiKey: 'your_api_key'
});

// Upload document with Phase 6 features
const document = await client.documents.upload({
  file: documentFile,
  enableHierarchicalChunking: true,
  enableSvgExtraction: true,
  enableContextExtraction: true
});

// Perform multimodal search
const results = await client.search.multimodal({
  query: 'HP LaserJet paper jam',
  modalities: ['text', 'image', 'video'],
  threshold: 0.5
});
```

---

**Last Updated**: 2025-12-08
**Version**: 1.0
**API Version**: v1
**Compatible with**: KRAI Phase 6 (v3.0+)
