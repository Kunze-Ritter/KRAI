<?php

namespace App\Services;

use App\Models\User;
use Illuminate\Http\Client\PendingRequest;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class KraiEngineService
{
    private string $baseUrl;

    private string $serviceToken;

    private int $defaultTimeout;

    private int $queryTimeout;

    private int $uploadTimeout;

    public function __construct(
        string $baseUrl,
        string $serviceToken,
        int $defaultTimeout = 120,
        int $queryTimeout = 60,
        int $uploadTimeout = 600
    ) {
        $this->baseUrl = rtrim($baseUrl, '/');
        $this->serviceToken = $serviceToken;
        $this->defaultTimeout = $defaultTimeout;
        $this->queryTimeout = $queryTimeout;
        $this->uploadTimeout = $uploadTimeout;
    }

    /**
     * Create HTTP client with default headers
     */
    private function createHttpClient(?int $timeout = null): PendingRequest
    {
        $client = Http::timeout($timeout ?? $this->defaultTimeout)
            ->withHeaders([
                'Accept' => 'application/json',
            ]);

        if ($this->serviceToken) {
            $client = $client->withHeaders([
                'Authorization' => 'Bearer '.$this->serviceToken,
            ]);
        }

        return $client;
    }

    /**
     * Add user context headers to HTTP client
     */
    private function addUserContext(PendingRequest $client, ?User $user = null): PendingRequest
    {
        if (! $user) {
            $user = auth()->user();
        }

        if ($user) {
            $client = $client->withHeaders([
                'X-Uploader-Username' => $user->name ?? null,
                'X-Uploader-UserId' => (string) ($user->id ?? ''),
                'X-Uploader-Source' => 'laravel-admin',
            ]);
        }

        return $client;
    }

    /**
     * Log API call with context
     */
    private function logApiCall(string $method, string $endpoint, string $documentId, int $status, ?string $error = null): void
    {
        $message = sprintf(
            'KRAI Engine API: %s %s - Document: %s - Status: %d',
            $method,
            $endpoint,
            $documentId,
            $status
        );

        if ($error) {
            $message .= ' - Error: '.$error;
        }

        if ($status >= 400) {
            Log::channel('krai-engine')->error($message);
        } else {
            Log::channel('krai-engine')->info($message);
        }
    }

    /**
     * Normalize API error payloads into safe loggable strings.
     */
    private function normalizeApiError(mixed $error, string $fallback = 'Unknown error'): string
    {
        if (is_string($error)) {
            return $error;
        }

        if (is_array($error)) {
            $json = json_encode($error, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

            return $json !== false ? $json : $fallback;
        }

        if (is_scalar($error)) {
            return (string) $error;
        }

        return $fallback;
    }

    /**
     * Process a single stage for a document
     */
    public function processStage(string $documentId, string $stageName, ?User $user = null): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/process/stage/{$stageName}";

        try {
            $client = $this->createHttpClient();
            $client = $this->addUserContext($client, $user);

            $response = $client->post($this->baseUrl.$endpoint);

            $this->logApiCall('POST', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'stage' => $data['data']['stage'] ?? $stageName,
                    'status' => $data['data']['status'] ?? 'queued',
                    'document_id' => $data['data']['document_id'] ?? $documentId,
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('POST', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('POST', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }

    /**
     * Process multiple stages for a document
     */
    public function processMultipleStages(string $documentId, array $stages, bool $stopOnError = true, ?User $user = null): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/process/stages";

        try {
            $client = $this->createHttpClient($this->uploadTimeout);
            $client = $this->addUserContext($client, $user);

            $payload = [
                'stages' => $stages,
                'stop_on_error' => $stopOnError,
            ];

            $response = $client->asJson()->post($this->baseUrl.$endpoint, $payload);

            $this->logApiCall('POST', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'total_stages' => $data['data']['total_stages'] ?? count($stages),
                    'successful' => $data['data']['successful'] ?? 0,
                    'failed' => $data['data']['failed'] ?? 0,
                    'stage_results' => $data['data']['stage_results'] ?? [],
                    'success_rate' => (float) ($data['data']['success_rate'] ?? 0),
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('POST', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                    'total_stages' => count($stages),
                    'successful' => 0,
                    'failed' => count($stages),
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('POST', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
                'total_stages' => count($stages),
                'successful' => 0,
                'failed' => count($stages),
            ];
        }
    }

    /**
     * Process video enrichment for a document
     */
    public function processVideo(string $documentId, string $videoUrl, ?string $manufacturerId = null, ?User $user = null): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/process/video";

        try {
            $client = $this->createHttpClient();
            $client = $this->addUserContext($client, $user);

            $payload = [
                'video_url' => $videoUrl,
            ];

            if ($manufacturerId) {
                $payload['manufacturer_id'] = $manufacturerId;
            }

            $response = $client->asJson()->post($this->baseUrl.$endpoint, $payload);

            $this->logApiCall('POST', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'video_id' => $data['data']['video_id'] ?? null,
                    'title' => $data['data']['title'] ?? null,
                    'platform' => $data['data']['platform'] ?? null,
                    'thumbnail_url' => $data['data']['thumbnail_url'] ?? null,
                    'duration' => $data['data']['duration'] ?? null,
                    'channel_title' => $data['data']['channel_title'] ?? null,
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('POST', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('POST', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }

    /**
     * Generate thumbnail for a document
     */
    public function generateThumbnail(string $documentId, array $size = [300, 400], int $page = 0, ?User $user = null): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/process/thumbnail";

        try {
            $client = $this->createHttpClient();
            $client = $this->addUserContext($client, $user);

            $payload = [
                'size' => $size,
                'page' => $page,
            ];

            $response = $client->asJson()->post($this->baseUrl.$endpoint, $payload);

            $this->logApiCall('POST', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'thumbnail_url' => $data['data']['thumbnail_url'] ?? null,
                    'size' => $data['data']['size'] ?? $size,
                    'file_size' => $data['data']['file_size'] ?? null,
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('POST', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('POST', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }

    /**
     * Normalize the per-stage payload from a backend stages response.
     *
     * Accepts three payload shapes:
     *   1. Structured (current backend): payload['stages'][stage] = {status,error,...}
     *   2. Flat (legacy v1):              payload['stage_status'][stage] = "completed"
     *   3. Mixed legacy:                  payload['stages'][stage] = "completed"
     *
     * Always returns:
     *   - stage_status:  [stage => status_string] for legacy callers / views
     *   - stage_details: full structured payload per stage (status, error,
     *                    duration_seconds, started_at, completed_at, progress, …)
     *
     * @param  array<string, mixed>  $payload
     * @return array{stage_status: array<string, string>, stage_details: array<string, array<string, mixed>>, found: bool}
     */
    private function normalizeStagePayload(array $payload): array
    {
        $stages = is_array($payload['stages'] ?? null) ? $payload['stages'] : null;
        $legacyFlat = is_array($payload['stage_status'] ?? null) ? $payload['stage_status'] : null;

        $stageStatus = [];
        $stageDetails = [];

        $source = $stages ?? $legacyFlat ?? [];

        foreach ($source as $stageName => $entry) {
            $stageName = (string) $stageName;
            if (is_array($entry)) {
                $status = (string) ($entry['status'] ?? 'pending');
                $stageStatus[$stageName] = $status;
                $stageDetails[$stageName] = $entry;
            } else {
                $status = (string) $entry;
                $stageStatus[$stageName] = $status;
                $stageDetails[$stageName] = ['status' => $status];
            }
        }

        $found = array_key_exists('found', $payload)
            ? (bool) $payload['found']
            : ($stages !== null || $legacyFlat !== null);

        return [
            'stage_status' => $stageStatus,
            'stage_details' => $stageDetails,
            'found' => $found,
        ];
    }

    /**
     * Get stage status for a document
     */
    public function getStageStatus(string $documentId): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/stages";

        try {
            $client = $this->createHttpClient($this->queryTimeout);

            $response = $client->get($this->baseUrl.$endpoint);

            $this->logApiCall('GET', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();
                $payload = is_array($data['data'] ?? null) ? $data['data'] : [];
                $normalized = $this->normalizeStagePayload($payload);

                return [
                    'success' => true,
                    'document_id' => (string) ($payload['document_id'] ?? $documentId),
                    'stage_status' => $normalized['stage_status'],
                    'stage_details' => $normalized['stage_details'],
                    'found' => $normalized['found'],
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('GET', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                    'found' => false,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('GET', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
                'found' => false,
            ];
        }
    }

    /**
     * Get available stages for processing
     */
    public function getAvailableStages(): array
    {
        $endpoint = '/api/v1/stages/names';
        $logContext = 'global';

        try {
            $client = $this->createHttpClient($this->queryTimeout);

            $response = $client->get($this->baseUrl.$endpoint);

            $this->logApiCall('GET', $endpoint, $logContext, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'stages' => $data['data']['stages'] ?? [],
                    'total' => $data['data']['total'] ?? 0,
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('GET', $endpoint, $logContext, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                    'stages' => [],
                    'total' => 0,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('GET', $endpoint, $logContext, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
                'stages' => [],
                'total' => 0,
            ];
        }
    }

    /**
     * Get document processing status
     */
    public function getDocumentStatus(string $documentId): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/status";

        try {
            $client = $this->createHttpClient($this->queryTimeout);

            $response = $client->get($this->baseUrl.$endpoint);

            $this->logApiCall('GET', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();
                $payload = is_array($data['data'] ?? null) ? $data['data'] : [];
                $stageSummary = is_array($payload['stage_summary'] ?? null) ? $payload['stage_summary'] : [];

                return [
                    'success' => true,
                    'status' => $payload['status'] ?? 'unknown',
                    'current_stage' => $payload['current_stage'] ?? null,
                    'progress' => (float) ($payload['progress'] ?? 0),
                    'queue_position' => $payload['queue_position'] ?? 0,
                    'total_queue_items' => $payload['total_queue_items'] ?? 0,
                    'stage_summary' => $stageSummary,
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('GET', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('GET', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }

    /**
     * Upload a document to the KRAI Engine
     */
    public function uploadDocument(\Illuminate\Http\UploadedFile $file, string $documentType, string $language = 'en', ?User $user = null, array $context = []): array
    {
        $endpoint = '/upload';

        try {
            $client = $this->createHttpClient();
            $client = $this->addUserContext($client, $user);
            $payload = array_filter([
                'document_type' => $documentType,
                'language' => $language,
                'manufacturer' => $context['manufacturer'] ?? null,
                'series' => $context['series'] ?? null,
                'model' => $context['model'] ?? null,
            ], static fn (mixed $value): bool => $value !== null && $value !== '');

            $realPath = $file->getRealPath();
            if ($realPath === false || ! is_readable($realPath)) {
                throw new \RuntimeException('Upload-Datei nicht lesbar: '.$file->getClientOriginalName());
            }

            $fileHandle = @fopen($realPath, 'rb');
            if ($fileHandle === false) {
                throw new \RuntimeException('Upload-Datei konnte nicht geöffnet werden: '.$file->getClientOriginalName());
            }

            try {
                $response = $client->attach(
                    'file',
                    $fileHandle,
                    $file->getClientOriginalName()
                )->post($this->baseUrl.$endpoint, $payload);
            } finally {
                if (is_resource($fileHandle)) {
                    fclose($fileHandle);
                }
            }

            $this->logApiCall('POST', $endpoint, 'upload', $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'document_id' => $data['document_id'] ?? null,
                    'filename' => $data['filename'] ?? $file->getClientOriginalName(),
                    'document_type' => $data['document_type'] ?? $documentType,
                    'language' => $data['language'] ?? $language,
                    'status' => $data['status'] ?? 'uploaded',
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('POST', $endpoint, 'upload', $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('POST', $endpoint, 'upload', 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }

    /**
     * Reprocess a document (full pipeline)
     */
    public function reprocessDocument(string $documentId, ?User $user = null): array
    {
        $endpoint = "/api/v1/documents/{$documentId}/reprocess";

        try {
            $client = $this->createHttpClient();
            $client = $this->addUserContext($client, $user);

            $response = $client->post($this->baseUrl.$endpoint);

            $this->logApiCall('POST', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'message' => $data['data']['message'] ?? 'Document reprocessing started',
                    'document_id' => $data['data']['document_id'] ?? $documentId,
                    'status' => $data['data']['status'] ?? 'started',
                ];
            } else {
                $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
                $this->logApiCall('POST', $endpoint, $documentId, $response->status(), $error);

                return [
                    'success' => false,
                    'error' => $error,
                ];
            }
        } catch (\Exception $e) {
            $this->logApiCall('POST', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }

    /**
     * Delete a document and related backend artifacts.
     */
    public function deleteDocument(string $documentId, ?User $user = null): array
    {
        $endpoint = "/api/v1/documents/{$documentId}";

        try {
            $client = $this->createHttpClient();
            $client = $this->addUserContext($client, $user);

            $response = $client->delete($this->baseUrl.$endpoint);

            $this->logApiCall('DELETE', $endpoint, $documentId, $response->status());

            if ($response->successful()) {
                $data = $response->json();

                return [
                    'success' => true,
                    'message' => $data['data']['message'] ?? 'Document deleted successfully',
                ];
            }

            $error = $this->normalizeApiError($response->json('detail', 'Unknown error'));
            $this->logApiCall('DELETE', $endpoint, $documentId, $response->status(), $error);

            return [
                'success' => false,
                'error' => $error,
            ];
        } catch (\Exception $e) {
            $this->logApiCall('DELETE', $endpoint, $documentId, 500, $e->getMessage());

            return [
                'success' => false,
                'error' => 'Connection error: '.$e->getMessage(),
            ];
        }
    }
}
