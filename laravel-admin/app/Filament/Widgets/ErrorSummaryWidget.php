<?php

namespace App\Filament\Widgets;

use App\Models\PipelineError;
use Filament\Widgets\StatsOverviewWidget as BaseWidget;
use Filament\Widgets\StatsOverviewWidget\Stat;
use Illuminate\Support\Facades\Log;

class ErrorSummaryWidget extends BaseWidget
{
    protected static ?int $sort = 5;

    protected function getPollingInterval(): ?string
    {
        return config('krai.error_monitoring.summary_polling_interval', '15s');
    }

    protected function getStats(): array
    {
        try {
            $activeCount = PipelineError::active()->count();
            $retryingCount = PipelineError::retrying()->count();
            $resolvedCount = PipelineError::resolved()
                ->where('resolved_at', '>=', now()->subDay())
                ->count();

            // Get hourly counts for last 6 hours for chart data
            $activeChart = $this->getHourlyErrorCounts('active');
            $retryingChart = $this->getHourlyErrorCounts('retrying');
            $resolvedChart = $this->getHourlyResolvedCounts();

            return [
                Stat::make('Active Errors', $activeCount)
                    ->description('Errors requiring attention')
                    ->descriptionIcon('heroicon-o-exclamation-circle')
                    ->color($activeCount > 0 ? 'danger' : 'success')
                    ->chart($activeChart),

                Stat::make('Retrying', $retryingCount)
                    ->description('Automatic retry in progress')
                    ->descriptionIcon('heroicon-o-arrow-path')
                    ->color('warning')
                    ->chart($retryingChart),

                Stat::make('Resolved (24h)', $resolvedCount)
                    ->description('Last 24 hours')
                    ->descriptionIcon('heroicon-o-check-circle')
                    ->color('success')
                    ->chart($resolvedChart),
            ];
        } catch (\Exception $e) {
            Log::error('ErrorSummaryWidget: Failed to fetch error statistics', [
                'error' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);

            return [
                Stat::make('Active Errors', '—')
                    ->description('Unable to load data')
                    ->color('gray'),
                Stat::make('Retrying', '—')
                    ->description('Unable to load data')
                    ->color('gray'),
                Stat::make('Resolved (24h)', '—')
                    ->description('Unable to load data')
                    ->color('gray'),
            ];
        }
    }

    protected function getHourlyErrorCounts(string $scope): array
    {
        try {
            $counts = [];
            for ($i = 5; $i >= 0; $i--) {
                $start = now()->subHours($i + 1);
                $end = now()->subHours($i);

                $query = match($scope) {
                    'active' => PipelineError::active(),
                    'retrying' => PipelineError::retrying(),
                    default => PipelineError::query(),
                };

                $count = $query->whereBetween('created_at', [$start, $end])
                    ->count();

                $counts[] = $count;
            }
            return $counts;
        } catch (\Exception $e) {
            return [0, 0, 0, 0, 0, 0];
        }
    }

    protected function getHourlyResolvedCounts(): array
    {
        try {
            $counts = [];
            for ($i = 5; $i >= 0; $i--) {
                $start = now()->subHours($i + 1);
                $end = now()->subHours($i);

                $count = PipelineError::resolved()
                    ->whereBetween('resolved_at', [$start, $end])
                    ->count();

                $counts[] = $count;
            }
            return $counts;
        } catch (\Exception $e) {
            return [0, 0, 0, 0, 0, 0];
        }
    }
}
