<?php

namespace App\Filament\Widgets;

use App\Services\MonitoringService;
use Filament\Widgets\StatsOverviewWidget as BaseWidget;
use Filament\Widgets\StatsOverviewWidget\Stat;

class QueueStatusWidget extends BaseWidget
{
    protected static ?int $sort = 4;

    protected function getPollingInterval(): ?string
    {
        return config('krai.monitoring.polling_intervals.queue', '20s');
    }

    protected function getStats(): array
    {
        $monitoringService = app(MonitoringService::class);
        $result = $monitoringService->getQueueStatus();

        if (!$result['success']) {
            return $this->getFallbackStats($result['error']);
        }

        $data = $result['data'];
        $queueMetrics = $data['queue_metrics'] ?? [];

        $byStatus = [
            'pending' => $queueMetrics['pending_count'] ?? 0,
            'processing' => $queueMetrics['processing_count'] ?? 0,
            'completed' => $queueMetrics['completed_count'] ?? 0,
            'failed' => $queueMetrics['failed_count'] ?? 0,
        ];
        $avgWaitTime = $queueMetrics['avg_wait_time_seconds'] ?? 0;
        $byTaskType = $queueMetrics['by_task_type'] ?? [];

        return [
            $this->getPendingStat($byStatus, $avgWaitTime),
            $this->getProcessingStat($byStatus),
            $this->getCompletedStat($byStatus),
            $this->getFailedStat($byStatus, $byTaskType),
        ];
    }

    private function getPendingStat(array $byStatus, float $avgWaitTime): Stat
    {
        $pending = $byStatus['pending'] ?? 0;

        $description = sprintf('Avg wait time: %ds', round($avgWaitTime));

        $color = 'success';
        if ($pending > 100) {
            $color = 'warning';
        }
        if ($pending > 500) {
            $color = 'danger';
        }

        return Stat::make('Pending', number_format($pending))
            ->description($description)
            ->descriptionIcon('heroicon-o-clock')
            ->color($color);
    }

    private function getProcessingStat(array $byStatus): Stat
    {
        $processing = $byStatus['processing'] ?? 0;

        return Stat::make('Processing', number_format($processing))
            ->description('Currently active')
            ->descriptionIcon('heroicon-o-arrow-path')
            ->color('info');
    }

    private function getCompletedStat(array $byStatus): Stat
    {
        $completed = $byStatus['completed'] ?? 0;

        return Stat::make('Completed', number_format($completed))
            ->description('Successfully processed')
            ->descriptionIcon('heroicon-o-check-circle')
            ->color('success');
    }

    private function getFailedStat(array $byStatus, array $byTaskType): Stat
    {
        $failed = $byStatus['failed'] ?? 0;

        $taskTypeBreakdown = '';
        if (!empty($byTaskType)) {
            $topFailures = array_slice($byTaskType, 0, 2);
            $taskTypeBreakdown = implode(', ', array_map(
                fn($type, $count) => "$type: $count",
                array_keys($topFailures),
                array_values($topFailures)
            ));
        }

        $description = $taskTypeBreakdown ?: 'No failures';

        $color = 'success';
        if ($failed > 0) {
            $color = 'warning';
        }
        if ($failed > 50) {
            $color = 'danger';
        }

        return Stat::make('Failed', number_format($failed))
            ->description($description)
            ->descriptionIcon('heroicon-o-x-circle')
            ->color($color);
    }

    private function getFallbackStats(?string $error): array
    {
        return [
            Stat::make('Pending', 'N/A')
                ->description($error ?? 'Unable to fetch data')
                ->descriptionIcon('heroicon-o-exclamation-triangle')
                ->color('danger'),
            Stat::make('Processing', 'N/A')
                ->description('Offline')
                ->descriptionIcon('heroicon-o-exclamation-triangle')
                ->color('danger'),
            Stat::make('Completed', 'N/A')
                ->description('Offline')
                ->descriptionIcon('heroicon-o-exclamation-triangle')
                ->color('danger'),
            Stat::make('Failed', 'N/A')
                ->description('Offline')
                ->descriptionIcon('heroicon-o-exclamation-triangle')
                ->color('danger'),
        ];
    }
}
