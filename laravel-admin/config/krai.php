<?php

return [
    /*
    |--------------------------------------------------------------------------
    | KRAI Engine Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration for the KRAI Engine FastAPI backend integration.
    | This includes the base URL, authentication token, and timeouts.
    |
    */

    'engine_url' => env('KRAI_ENGINE_URL', 'http://krai-engine:8000'),
    'ollama_url' => env('OLLAMA_URL', 'http://krai-ollama-prod:11434'),
    'service_jwt' => env('KRAI_SERVICE_JWT', env('KRAI_ENGINE_SERVICE_JWT', '')),
    'default_timeout' => 120, // Default HTTP timeout in seconds
    'query_timeout' => 60, // Timeout for read-only queries
    'upload_timeout' => 600, // Timeout for multi-stage sync calls (seconds)

    /*
    |--------------------------------------------------------------------------
    | Stage Definitions
    |--------------------------------------------------------------------------
    |
    | Definition of all processing stages available in the KRAI pipeline.
    | Each stage includes a German label, description, icon, and grouping.
    |
    */

    'stages' => [
        'upload' => [
            'label' => 'Upload',
            'description' => 'Dokument hochladen und validieren',
            'icon' => 'heroicon-o-arrow-up-tray',
            'group' => 'initialization',
            'order' => 1,
        ],
        'text_extraction' => [
            'label' => 'Text-Extraktion',
            'description' => 'Text aus PDF extrahieren',
            'icon' => 'heroicon-o-document-text',
            'group' => 'extraction',
            'order' => 2,
        ],
        'table_extraction' => [
            'label' => 'Tabellen-Extraktion',
            'description' => 'Tabellen strukturiert extrahieren',
            'icon' => 'heroicon-o-table-cells',
            'group' => 'extraction',
            'order' => 3,
        ],
        'svg_processing' => [
            'label' => 'SVG-Verarbeitung',
            'description' => 'Vektorgrafiken zu PNG konvertieren',
            'icon' => 'heroicon-o-photo',
            'group' => 'extraction',
            'order' => 4,
        ],
        'image_processing' => [
            'label' => 'Bild-Verarbeitung',
            'description' => 'Bilder extrahieren und verarbeiten',
            'icon' => 'heroicon-o-photo',
            'group' => 'extraction',
            'order' => 5,
        ],
        'visual_embedding' => [
            'label' => 'Visuelle Embeddings',
            'description' => 'Bild-Embeddings generieren',
            'icon' => 'heroicon-o-cube',
            'group' => 'enrichment',
            'order' => 6,
        ],
        'link_extraction' => [
            'label' => 'Link-Extraktion',
            'description' => 'URLs und Referenzen extrahieren',
            'icon' => 'heroicon-o-link',
            'group' => 'extraction',
            'order' => 7,
        ],
        'video_enrichment' => [
            'label' => 'Video-Anreicherung',
            'description' => 'Brightcove/YouTube-Videos verknüpfen',
            'icon' => 'heroicon-o-video-camera',
            'group' => 'enrichment',
            'order' => 8,
        ],
        'chunk_prep' => [
            'label' => 'Chunk-Vorbereitung',
            'description' => 'Text in Chunks aufteilen',
            'icon' => 'heroicon-o-squares-2x2',
            'group' => 'processing',
            'order' => 9,
        ],
        'classification' => [
            'label' => 'Klassifizierung',
            'description' => 'Dokumenttyp und Hersteller erkennen',
            'icon' => 'heroicon-o-tag',
            'group' => 'processing',
            'order' => 10,
        ],
        'metadata_extraction' => [
            'label' => 'Metadaten-Extraktion',
            'description' => 'Fehlercodes und Metadaten extrahieren',
            'icon' => 'heroicon-o-information-circle',
            'group' => 'processing',
            'order' => 11,
        ],
        'parts_extraction' => [
            'label' => 'Ersatzteil-Extraktion',
            'description' => 'Ersatzteile und Artikelnummern extrahieren',
            'icon' => 'heroicon-o-wrench-screwdriver',
            'group' => 'processing',
            'order' => 12,
        ],
        'series_detection' => [
            'label' => 'Serien-Erkennung',
            'description' => 'Produktserien erkennen',
            'icon' => 'heroicon-o-rectangle-stack',
            'group' => 'processing',
            'order' => 13,
        ],
        'storage' => [
            'label' => 'Speicherung',
            'description' => 'Daten in Object Storage speichern',
            'icon' => 'heroicon-o-cloud-arrow-up',
            'group' => 'finalization',
            'order' => 14,
        ],
        'embedding' => [
            'label' => 'Text-Embeddings',
            'description' => 'Text-Embeddings generieren',
            'icon' => 'heroicon-o-cube-transparent',
            'group' => 'enrichment',
            'order' => 15,
        ],
        'search_indexing' => [
            'label' => 'Such-Indexierung',
            'description' => 'Suchindex aktualisieren',
            'icon' => 'heroicon-o-magnifying-glass',
            'group' => 'finalization',
            'order' => 16,
        ],
    ],

    /*
    |--------------------------------------------------------------------------
    | Stage Groups
    |--------------------------------------------------------------------------
    |
    | Groups for organizing stages in the UI. Stages are grouped by their
    | processing phase to improve user experience and navigation.
    |
    */

    'stage_groups' => [
        'initialization',
        'extraction',
        'processing',
        'enrichment',
        'finalization',
    ],

    /*
    |--------------------------------------------------------------------------
    | Default Stage Selection
    |--------------------------------------------------------------------------
    |
    | Default stages to process when no custom selection is made.
    | This excludes the UPLOAD stage which is handled separately.
    |
    */

    'default_stages' => [
        'text_extraction',
        'table_extraction',
        'svg_processing',
        'image_processing',
        'visual_embedding',
        'link_extraction',
        'video_enrichment',
        'chunk_prep',
        'classification',
        'metadata_extraction',
        'parts_extraction',
        'series_detection',
        'storage',
        'embedding',
        'search_indexing',
    ],

    /*
    |--------------------------------------------------------------------------
    | Monitoring Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration for the monitoring widgets and dashboard.
    | Includes cache TTL and polling intervals for real-time updates.
    |
    */

    'monitoring' => [
        'base_url' => env('MONITORING_BASE_URL', 'http://krai-engine:8000'),
        'cache_ttl' => [
            'metrics' => env('MONITORING_CACHE_TTL_METRICS', 30),
            'queue' => env('MONITORING_CACHE_TTL_QUEUE', 15),
            'dashboard' => env('MONITORING_CACHE_TTL_DASHBOARD', 180),
            'data_quality' => env('MONITORING_CACHE_TTL_DATA_QUALITY', 300),
            'navigation_badges' => env('MONITORING_CACHE_TTL_NAV_BADGES', 20),
            'pipeline' => env('MONITORING_CACHE_TTL_PIPELINE', 15),
            'performance' => env('MONITORING_CACHE_TTL_PERFORMANCE', 60),
        ],
        'timeout' => env('MONITORING_REQUEST_TIMEOUT', 10),
        'polling_intervals' => [
            'dashboard' => env('MONITORING_DASHBOARD_POLLING_INTERVAL', 60),
            'queue' => env('MONITORING_QUEUE_POLLING_INTERVAL', 30),
            'processor' => env('MONITORING_PROCESSOR_POLLING_INTERVAL', 30),
            'metrics' => env('MONITORING_METRICS_POLLING_INTERVAL', 60),
            'performance' => env('MONITORING_PERFORMANCE_POLLING_INTERVAL', 60),
            'pipeline' => env('MONITORING_PIPELINE_POLLING_INTERVAL', 15),
        ],
    ],

    'images' => [
        'cache_ttl' => 60,
        'default_page_size' => 24,
        'max_page_size' => 96,
        'thumbnail_size' => [
            'width' => 300,
            'height' => 300,
        ],
        'bulk_download_limit' => 100,
        'bulk_download_max_bytes' => env('KRAI_IMAGES_BULK_DOWNLOAD_MAX_BYTES', 524288000), // 500 MB
    ],

    /*
    |--------------------------------------------------------------------------
    | Error Monitoring Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration for error monitoring widgets on the dashboard.
    | Includes polling intervals and display limits for error tracking.
    |
    */

    'error_monitoring' => [
        'summary_polling_interval' => env('KRAI_ERROR_SUMMARY_POLLING', '15s'),
        'recent_failures_polling_interval' => env('KRAI_RECENT_FAILURES_POLLING', '30s'),
        'recent_failures_limit' => env('KRAI_RECENT_FAILURES_LIMIT', 10),
    ],

    /*
    |--------------------------------------------------------------------------
    | Firecrawl Configuration
    |--------------------------------------------------------------------------
    |
    | Configuration for Firecrawl web scraping service integration.
    | Includes API URL, timeouts, caching, and feature flags.
    |
    */

    'firecrawl' => [
        'api_url' => env('FIRECRAWL_API_URL', 'http://krai-firecrawl-api-prod:3002'),
        'llm_provider' => env('FIRECRAWL_LLM_PROVIDER', 'ollama'),
        'model_name' => env('FIRECRAWL_MODEL_NAME', 'qwen2.5:3b'),
        'embedding_model' => env('FIRECRAWL_EMBEDDING_MODEL', 'nomic-embed-text:latest'),
        'max_concurrency' => (int) env('FIRECRAWL_MAX_CONCURRENCY', 3),
        'block_media' => env('FIRECRAWL_BLOCK_MEDIA', 'true') === 'true',
        'cache_ttl' => 60,
        'timeout' => [
            'health' => 10,
            'scrape' => 30,
            'crawl' => 300,
            'extract' => 60,
        ],
        'test_urls' => [
            'example' => 'https://example.com',
            'manufacturer' => 'https://kmbs.konicaminolta.us',
        ],
    ],
];

/*
|--------------------------------------------------------------------------
| Helper Functions
|--------------------------------------------------------------------------
|
| These functions provide convenient access to stage configuration
| throughout the application.
|
*/

if (! function_exists('krai_stages')) {
    /**
     * Get all KRAI stages
     */
    function krai_stages(): array
    {
        return config('krai.stages', []);
    }
}

if (! function_exists('krai_stage_label')) {
    /**
     * Get the German label for a stage
     */
    function krai_stage_label(string $stage): string
    {
        return config("krai.stages.{$stage}.label", $stage);
    }
}

if (! function_exists('krai_stage_icon')) {
    /**
     * Get the icon for a stage
     */
    function krai_stage_icon(string $stage): string
    {
        return config("krai.stages.{$stage}.icon", 'heroicon-o-cog');
    }
}

if (! function_exists('krai_stage_group')) {
    /**
     * Get the group for a stage
     */
    function krai_stage_group(string $stage): string
    {
        return config("krai.stages.{$stage}.group", 'processing');
    }
}

if (! function_exists('krai_stages_by_group')) {
    /**
     * Get stages grouped by their group
     */
    function krai_stages_by_group(): array
    {
        $stages = krai_stages();
        $groups = [];

        foreach ($stages as $key => $stage) {
            $group = $stage['group'];
            $groups[$group][$key] = $stage;
        }

        return $groups;
    }
}

if (! function_exists('krai_stage_options')) {
    /**
     * Get stages formatted for form select options
     */
    function krai_stage_options(): array
    {
        $stages = krai_stages();
        $options = [];

        foreach ($stages as $key => $stage) {
            $options[$key] = $stage['label'];
        }

        return $options;
    }
}
