<?php

namespace App\Filament\Widgets;

use App\Services\MonitoringService;
use Filament\Widgets\Widget;

class PipelineStatusWidget extends Widget
{
    protected static ?int $sort = 3;
    protected int | string | array $columnSpan = 'full';
    protected string $view = 'filament.widgets.pipeline-status';

    protected function getPollingInterval(): ?string
    {
        return config('krai.monitoring.polling_intervals.pipeline', '15s');
    }

    public function getPipelineData(): array
    {
        $monitoringService = app(MonitoringService::class);

        try {
            $result = $monitoringService->getPipelineStatus();

            if (!$result['success']) {
                // Parse error to provide actionable feedback
                $error = $result['error'] ?? 'Unknown error';
                $errorType = $this->classifyError($error);

                return [
                    'success' => false,
                    'error' => $error,
                    'error_type' => $errorType,
                    'config_url' => config('krai.monitoring.base_url'),
                    'engine_url' => config('krai.engine_url'),
                    'pipeline_metrics' => [],
                    'stage_metrics' => [],
                    'hardware_status' => [],
                ];
            }

            // Success path unchanged
            $data = $result['data'];
            return [
                'success' => true,
                'error' => null,
                'pipeline_metrics' => $data['pipeline_metrics'] ?? [],
                'stage_metrics' => $data['stage_metrics'] ?? [],
                'hardware_status' => $data['hardware_status'] ?? [],
            ];
        } catch (\Exception $e) {
            \Log::error('Pipeline widget exception', [
                'message' => $e->getMessage(),
                'config_url' => config('krai.monitoring.base_url'),
                'engine_url' => config('krai.engine_url'),
            ]);

            return [
                'success' => false,
                'error' => $e->getMessage(),
                'error_type' => 'exception',
                'config_url' => config('krai.monitoring.base_url'),
                'engine_url' => config('krai.engine_url'),
                'pipeline_metrics' => [],
                'stage_metrics' => [],
                'hardware_status' => [],
            ];
        }
    }

    private function classifyError(string $error): string
    {
        if (str_contains($error, 'Could not resolve host')) {
            return 'dns_failure';
        }
        if (str_contains($error, 'Connection refused')) {
            return 'connection_refused';
        }
        if (str_contains($error, 'Connection timed out')) {
            return 'timeout';
        }
        if (str_contains($error, 'HTTP 404')) {
            return 'endpoint_not_found';
        }
        if (str_contains($error, 'HTTP 401') || str_contains($error, 'HTTP 403')) {
            return 'authentication_error';
        }
        if (str_contains($error, 'HTTP 500')) {
            return 'server_error';
        }
        return 'unknown';
    }

    protected function getViewData(): array
    {
        return [
            'pipelineData' => $this->getPipelineData(),
        ];
    }
}
