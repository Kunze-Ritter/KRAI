<?php

namespace App\Filament\Pages;

use App\Services\MonitoringService;
use Filament\Pages\Page;

class PipelineStatusPage extends Page
{
    protected string $view = 'filament.pages.pipeline-status';

    protected static ?string $navigationLabel = 'Pipeline-Status';

    protected static \UnitEnum|string|null $navigationGroup = 'Monitoring';

    protected static \BackedEnum|string|null $navigationIcon = 'heroicon-o-arrow-path';

    protected static ?int $navigationSort = 2;

    protected static ?string $pollingInterval = null;

    public function getPipelineData(): array
    {
        try {
            $response = app(MonitoringService::class)->getPipelineStatus();

            if (! ($response['success'] ?? false)) {
                return [
                    'success' => false,
                    'error' => $response['error'] ?? 'Unbekannter Fehler',
                    'pipeline_metrics' => [],
                    'stage_metrics' => [],
                    'hardware_status' => [],
                ];
            }

            $data = is_array($response['data'] ?? null) ? $response['data'] : [];
            $pipelineMetrics = is_array($data['pipeline_metrics'] ?? null) ? $data['pipeline_metrics'] : [];
            $stageMetrics = is_array($data['stage_metrics'] ?? null) ? $data['stage_metrics'] : [];
            $hardwareStatus = is_array($data['hardware_status'] ?? null) ? $data['hardware_status'] : [];

            return [
                'success' => true,
                'error' => null,
                'pipeline_metrics' => $pipelineMetrics ?: $data,
                'stage_metrics' => $stageMetrics,
                'hardware_status' => $hardwareStatus,
            ];
        } catch (\Throwable $e) {
            return [
                'success' => false,
                'error' => $e->getMessage(),
                'pipeline_metrics' => [],
                'stage_metrics' => [],
                'hardware_status' => [],
            ];
        }
    }

    public function getDataQualityData(): array
    {
        try {
            $response = app(MonitoringService::class)->getDataQuality();

            if (! ($response['success'] ?? false)) {
                return [
                    'success' => false,
                    'error' => $response['error'] ?? 'Unbekannter Fehler',
                    'data' => [],
                ];
            }

            $data = is_array($response['data'] ?? null) ? $response['data'] : [];

            return [
                'success' => true,
                'error' => null,
                'data' => $data,
            ];
        } catch (\Throwable $e) {
            return [
                'success' => false,
                'error' => $e->getMessage(),
                'data' => [],
            ];
        }
    }

    public function getPipelineActivityData(): array
    {
        try {
            $response = app(MonitoringService::class)->getPipelineActivity();

            if (! ($response['success'] ?? false)) {
                return [
                    'success' => false,
                    'error' => $response['error'] ?? 'Unbekannter Fehler',
                    'active_documents' => [],
                    'activity' => [],
                    'recent_failures' => [],
                    'terminal_lines' => [],
                ];
            }

            $data = is_array($response['data'] ?? null) ? $response['data'] : [];
            $activeDocuments = is_array($data['active_documents'] ?? null) ? $data['active_documents'] : [];
            $recentActivity = is_array($data['recent_activity'] ?? null) ? $data['recent_activity'] : [];
            $recentFailures = is_array($data['recent_failures'] ?? null) ? $data['recent_failures'] : [];

            // Normalize recent_activity + recent_failures into one chronological list
            // that matches the existing blade view's expected shape.
            $activity = [];

            foreach ($recentActivity as $entry) {
                if (! is_array($entry)) {
                    continue;
                }
                $activity[] = [
                    'type' => 'stage',
                    'timestamp' => $entry['timestamp'] ?? null,
                    'document_id' => $entry['document_id'] ?? null,
                    'stage_name' => $entry['stage_name'] ?? null,
                    'status' => $entry['status'] ?? 'unknown',
                    'message' => $entry['message'] ?? sprintf(
                        'Stage %s: %s',
                        $entry['stage_name'] ?? 'unknown',
                        $entry['status'] ?? 'unknown'
                    ),
                    'priority' => null,
                ];
            }

            foreach ($recentFailures as $failure) {
                if (! is_array($failure)) {
                    continue;
                }
                $activity[] = [
                    'type' => 'error',
                    'timestamp' => $failure['created_at'] ?? null,
                    'document_id' => $failure['document_id'] ?? null,
                    'stage_name' => $failure['stage_name'] ?? null,
                    'status' => 'error',
                    'message' => $failure['error_message'] ?? 'Pipeline-Fehler',
                    'priority' => null,
                ];
            }

            usort($activity, fn (array $a, array $b): int => strcmp(
                (string) ($b['timestamp'] ?? ''),
                (string) ($a['timestamp'] ?? '')
            ));

            $activity = array_slice($activity, 0, 20);

            return [
                'success' => true,
                'error' => null,
                'active_documents' => $activeDocuments,
                'activity' => $activity,
                'recent_failures' => $recentFailures,
                'terminal_lines' => $this->formatTerminalLines($activity),
            ];
        } catch (\Throwable $e) {
            return [
                'success' => false,
                'error' => $e->getMessage(),
                'active_documents' => [],
                'activity' => [],
                'recent_failures' => [],
                'terminal_lines' => [],
            ];
        }
    }

    public function formatTerminalLines(array $activity): array
    {
        return array_map(function (array $entry): string {
            $timestamp = $entry['timestamp'] ?? 'unknown-time';
            $type = strtoupper((string) ($entry['type'] ?? 'activity'));
            $status = strtoupper((string) ($entry['status'] ?? 'unknown'));
            $stage = (string) ($entry['stage_name'] ?? 'unknown');
            $documentId = (string) ($entry['document_id'] ?? 'n/a');
            $message = (string) ($entry['message'] ?? 'No message');

            return sprintf('[%s] %-5s %-12s doc=%s stage=%s %s', $timestamp, $type, $status, $documentId, $stage, $message);
        }, $activity);
    }

    public function calculateProgress(array $metrics): float
    {
        $total = (float) ($metrics['total_documents'] ?? 0);
        $completed = (float) ($metrics['documents_completed'] ?? 0);

        if ($total <= 0) {
            return 0;
        }

        return min(100, max(0, ($completed / $total) * 100));
    }

    public function getStageStatusBadge(array $stage): array
    {
        if (! empty($stage['active'])) {
            return ['label' => 'Running', 'color' => 'warning'];
        }

        if (($stage['failed_count'] ?? 0) > 0) {
            return ['label' => 'Attention', 'color' => 'danger'];
        }

        if (! empty($stage['completed'])) {
            return ['label' => 'Completed', 'color' => 'success'];
        }

        return ['label' => 'Idle', 'color' => 'gray'];
    }

    protected function getViewData(): array
    {
        self::$pollingInterval = (string) config('krai.monitoring.polling_intervals.pipeline', '15s');

        return [
            'pipelineData' => $this->getPipelineData(),
            'qualityData' => $this->getDataQualityData(),
            'activityData' => $this->getPipelineActivityData(),
        ];
    }
}
