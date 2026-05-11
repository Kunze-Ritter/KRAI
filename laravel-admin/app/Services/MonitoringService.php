<?php

namespace App\Services;

use Illuminate\Http\Client\Pool;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class MonitoringService
{
    private static array $pendingRequests = [];

    private TokenService $tokenService;

    public function __construct(
        private ?string $baseUrl = null,
        private ?string $serviceJwt = null,
    ) {
        $resolvedUrl = $baseUrl
            ?? config('krai.monitoring.base_url')
            ?? config('krai.engine_url', 'http://krai-engine:8000');

        $this->baseUrl = rtrim($resolvedUrl, '/');
        $this->serviceJwt = $serviceJwt ?? config('krai.service_jwt');
        $this->tokenService = new TokenService($this->baseUrl, $this->serviceJwt);
    }

    /**
     * Create HTTP client with timeout and authorization
     */
    private function createHttpClient()
    {
        return Http::timeout(config('krai.monitoring.timeout', 10))
            ->withHeaders($this->buildHeaders());
    }

    private function buildHeaders(): array
    {
        $headers = [
            'Accept' => 'application/json',
            'Content-Type' => 'application/json',
        ];

        $jwt = $this->tokenService->getToken();
        if ($jwt) {
            $headers['Authorization'] = 'Bearer '.$jwt;
        }

        return $headers;
    }

    /**
     * Get dashboard overview data
     */
    public function getDashboardOverview(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.dashboard', 120);
        $cacheKey = 'monitoring.dashboard.overview';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    Log::debug('Fetching dashboard overview', [
                        'url' => "{$this->baseUrl}/api/v1/dashboard/overview",
                        'base_url' => $this->baseUrl,
                    ]);

                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/dashboard/overview");

                    if ($response->successful()) {
                        $json = $response->json();

                        return [
                            'success' => true,
                            'data' => $json['data'] ?? [],
                            'error' => null,
                        ];
                    }

                    // Specific error messages based on HTTP status
                    $errorMessage = match ($response->status()) {
                        404 => 'Dashboard endpoint not registered in backend',
                        401, 403 => 'Authentication failed (check KRAI_SERVICE_JWT)',
                        500, 502, 503 => 'Backend service error (check container logs)',
                        default => "HTTP {$response->status()}: {$response->body()}",
                    };

                    Log::error('Failed to fetch dashboard overview', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                        'error_message' => $errorMessage,
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $errorMessage,
                    ];
                } catch (\Illuminate\Http\Client\ConnectionException $e) {
                    $errorMessage = 'Backend service unavailable (check Docker container status)';
                    Log::error('Connection error fetching dashboard overview', [
                        'message' => $e->getMessage(),
                        'error_message' => $errorMessage,
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $errorMessage,
                    ];
                } catch (\Illuminate\Http\Client\RequestException $e) {
                    $errorMessage = str_contains($e->getMessage(), 'timed out')
                        ? 'Dashboard query timeout (check database performance)'
                        : 'Request failed: '.$e->getMessage();

                    Log::error('Request error fetching dashboard overview', [
                        'message' => $e->getMessage(),
                        'error_message' => $errorMessage,
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $errorMessage,
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching dashboard overview', [
                        'message' => $e->getMessage(),
                        'trace' => $e->getTraceAsString(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get processor health for navigation badges with dedicated TTL
     */
    public function getProcessorHealthBadge(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.navigation_badges', 30);
        $cacheKey = 'monitoring.processors.badge';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/processors");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch processor health for badge', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching processor health for badge', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get monitoring metrics
     */
    public function getMonitoringMetrics(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.metrics', 30);
        $cacheKey = 'monitoring.metrics';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/metrics");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch monitoring metrics', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching monitoring metrics', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get pipeline status
     */
    /**
     * Fetch the single pipeline-activity endpoint that powers the Filament
     * Pipeline Status page. Returns a normalized envelope with
     * pipeline_metrics + active_documents + recent_activity + recent_failures.
     */
    public function getPipelineActivity(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.pipeline', 15);
        $cacheKey = 'monitoring.pipeline_activity';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                $url = "{$this->baseUrl}/api/v1/monitoring/pipeline-activity";

                try {
                    $response = $this->createHttpClient()->get($url);

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch pipeline activity', [
                        'url' => $url,
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching pipeline activity', [
                        'url' => $url,
                        'message' => $e->getMessage(),
                        'class' => get_class($e),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    public function getPipelineStatus(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.pipeline', 15);
        $cacheKey = 'monitoring.pipeline';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                $url = "{$this->baseUrl}/api/v1/monitoring/pipeline";

                // Log the request for debugging
                Log::debug('Fetching pipeline status', [
                    'url' => $url,
                    'base_url' => $this->baseUrl,
                    'config_monitoring_base_url' => config('krai.monitoring.base_url'),
                    'config_engine_url' => config('krai.engine_url'),
                ]);

                try {
                    $response = $this->createHttpClient()
                        ->get($url);

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch pipeline status', [
                        'url' => $url,
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching pipeline status', [
                        'url' => $url,
                        'message' => $e->getMessage(),
                        'class' => get_class($e),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get queue status
     */
    public function getQueueStatus(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.queue', 20);
        $cacheKey = 'monitoring.queue';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/queue");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch queue status', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching queue status', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get queue status for navigation badges with dedicated TTL
     */
    public function getQueueStatusBadge(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.navigation_badges', 30);
        $cacheKey = 'monitoring.queue.badge';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/queue");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch queue status for badge', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching queue status for badge', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get processor health
     */
    public function getProcessorHealth(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.metrics', 30);
        $cacheKey = 'monitoring.processors';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/processors");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch processor health', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching processor health', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    /**
     * Get data quality metrics
     */
    public function getDataQuality(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.data_quality', 120);
        $cacheKey = 'monitoring.data_quality';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/data-quality");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }
                } catch (\Exception $e) {
                    Log::error('Exception fetching data quality', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }

                Log::error('Failed to fetch data quality', [
                    'status' => $response->status(),
                    'body' => $response->body(),
                ]);

                return [
                    'success' => false,
                    'data' => [],
                    'error' => "HTTP {$response->status()}: {$response->body()}",
                ];
            });
        });
    }

    public function getPerformanceMetrics(): array
    {
        $ttl = config('krai.monitoring.cache_ttl.performance', 60);
        $cacheKey = 'monitoring.performance';

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($ttl, $cacheKey) {
            return Cache::remember($cacheKey, $ttl, function () {
                try {
                    $response = $this->createHttpClient()
                        ->get("{$this->baseUrl}/api/v1/monitoring/performance");

                    if ($response->successful()) {
                        return [
                            'success' => true,
                            'data' => $response->json(),
                            'error' => null,
                        ];
                    }

                    Log::error('Failed to fetch performance metrics', [
                        'status' => $response->status(),
                        'body' => $response->body(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => "HTTP {$response->status()}: {$response->body()}",
                    ];
                } catch (\Exception $e) {
                    Log::error('Exception fetching performance metrics', [
                        'message' => $e->getMessage(),
                    ]);

                    return [
                        'success' => false,
                        'data' => [],
                        'error' => $e->getMessage(),
                    ];
                }
            });
        });
    }

    public function getBatchMonitoringData(array $endpoints): array
    {
        $cacheKey = 'monitoring.batch.'.md5(json_encode($endpoints));
        $ttl = config('krai.monitoring.cache_ttl.dashboard', 120);

        return $this->deduplicatedRequest($cacheKey, $ttl, function () use ($endpoints, $cacheKey, $ttl) {
            $lock = Cache::lock('lock.'.$cacheKey, 30);

            $lockResult = $lock->get(function () use ($endpoints, $cacheKey, $ttl) {
                return Cache::remember($cacheKey, $ttl, function () use ($endpoints) {
                    try {
                        $responses = Http::pool(function (Pool $pool) use ($endpoints) {
                            $headers = $this->buildHeaders();
                            $requests = [];

                            foreach ($endpoints as $name => $path) {
                                $requests[] = $pool->as($name)->withHeaders($headers)->timeout(config('krai.monitoring.timeout', 10))->get("{$this->baseUrl}{$path}");
                            }

                            return $requests;
                        });

                        $result = [];

                        foreach ($responses as $name => $response) {
                            if ($response->successful()) {
                                $json = $response->json();
                                $result[$name] = [
                                    'success' => true,
                                    'data' => $json['data'] ?? $json,
                                    'error' => null,
                                ];
                            } else {
                                Log::error('Failed batch monitoring request', [
                                    'endpoint' => $name,
                                    'status' => $response->status(),
                                    'body' => $response->body(),
                                ]);

                                $result[$name] = [
                                    'success' => false,
                                    'data' => [],
                                    'error' => "HTTP {$response->status()}: {$response->body()}",
                                ];
                            }
                        }

                        return $result;
                    } catch (\Exception $e) {
                        Log::error('Exception during batch monitoring request', [
                            'message' => $e->getMessage(),
                            'trace' => $e->getTraceAsString(),
                        ]);

                        return $this->buildBatchErrorResult($endpoints, $e->getMessage());
                    }
                });
            });

            if (is_array($lockResult)) {
                return $lockResult;
            }

            Log::warning('Batch monitoring lock unavailable', [
                'cache_key' => $cacheKey,
                'endpoints' => array_keys($endpoints),
            ]);

            return $this->buildBatchErrorResult($endpoints, 'Cache lock timeout');
        });
    }

    public function getDashboardBatch(): array
    {
        return $this->getBatchMonitoringData([
            'dashboard' => '/api/v1/dashboard/overview',
            'metrics' => '/api/v1/monitoring/metrics',
            'data_quality' => '/api/v1/monitoring/data-quality',
            'queue' => '/api/v1/monitoring/queue',
            'pipeline' => '/api/v1/monitoring/pipeline',
        ]);
    }

    /**
     * Clear all monitoring caches
     */
    public function clearCache(): void
    {
        Cache::forget('monitoring.dashboard.overview');
        Cache::forget('monitoring.metrics');
        Cache::forget('monitoring.pipeline');
        Cache::forget('monitoring.queue');
        Cache::forget('monitoring.queue.badge');
        Cache::forget('monitoring.processors');
        Cache::forget('monitoring.processors.badge');
        Cache::forget('monitoring.data_quality');
        Cache::forget('monitoring.performance');

        // Also clear token cache to force re-authentication
        $this->tokenService->clearCache();
    }

    private function deduplicatedRequest(string $key, int $ttl, callable $callback): mixed
    {
        if (isset(self::$pendingRequests[$key])) {
            return self::$pendingRequests[$key];
        }

        try {
            self::$pendingRequests[$key] = $callback();

            return self::$pendingRequests[$key];
        } finally {
            unset(self::$pendingRequests[$key]);
        }
    }

    private function buildBatchErrorResult(array $endpoints, string $error): array
    {
        $result = [];

        foreach (array_keys($endpoints) as $name) {
            $result[$name] = [
                'success' => false,
                'data' => [],
                'error' => $error,
            ];
        }

        return $result;
    }

    /**
     * Get queue for a specific stage
     */
    public function getStageQueue(string $stageName, int $limit = 50): array
    {
        try {
            $response = $this->createHttpClient()
                ->get("{$this->baseUrl}/api/v1/monitoring/stages/{$stageName}/queue", [
                    'limit' => $limit,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data' => $response->json(),
                    'error' => null,
                ];
            }

            Log::error('Failed to fetch stage queue', [
                'stage' => $stageName,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            return [
                'success' => false,
                'data' => [],
                'error' => "HTTP {$response->status()}: {$response->body()}",
            ];
        } catch (\Exception $e) {
            Log::error('Exception fetching stage queue', [
                'stage' => $stageName,
                'message' => $e->getMessage(),
            ]);

            return [
                'success' => false,
                'data' => [],
                'error' => $e->getMessage(),
            ];
        }
    }

    /**
     * Get errors for a specific stage
     */
    public function getStageErrors(string $stageName, int $limit = 100): array
    {
        try {
            $response = $this->createHttpClient()
                ->get("{$this->baseUrl}/api/v1/monitoring/stages/{$stageName}/errors", [
                    'limit' => $limit,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data' => $response->json(),
                    'error' => null,
                ];
            }

            Log::error('Failed to fetch stage errors', [
                'stage' => $stageName,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            return [
                'success' => false,
                'data' => [],
                'error' => "HTTP {$response->status()}: {$response->body()}",
            ];
        } catch (\Exception $e) {
            Log::error('Exception fetching stage errors', [
                'stage' => $stageName,
                'message' => $e->getMessage(),
            ]);

            return [
                'success' => false,
                'data' => [],
                'error' => $e->getMessage(),
            ];
        }
    }

    /**
     * Retry a specific stage for a document
     */
    public function retryStage(string $documentId, string $stageName): array
    {
        try {
            $response = $this->createHttpClient()
                ->post("{$this->baseUrl}/api/v1/monitoring/stages/{$stageName}/retry", [
                    'document_id' => $documentId,
                ]);

            if ($response->successful()) {
                return [
                    'success' => true,
                    'data' => $response->json(),
                    'error' => null,
                ];
            }

            Log::error('Failed to retry stage', [
                'document_id' => $documentId,
                'stage' => $stageName,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            return [
                'success' => false,
                'data' => [],
                'error' => "HTTP {$response->status()}: {$response->body()}",
            ];
        } catch (\Exception $e) {
            Log::error('Exception retrying stage', [
                'document_id' => $documentId,
                'stage' => $stageName,
                'message' => $e->getMessage(),
            ]);

            return [
                'success' => false,
                'data' => [],
                'error' => $e->getMessage(),
            ];
        }
    }
}
