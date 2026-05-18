<?php

namespace App\Filament\Widgets;

use App\Filament\Resources\Monitoring\PipelineErrorResource;
use App\Models\PipelineError;
use Filament\Notifications\Notification;
use Filament\Widgets\Widget;
use Illuminate\Support\Collection;

class RecentFailuresWidget extends Widget
{
    protected static ?int $sort = 6;

    protected int | string | array $columnSpan = 'full';

    protected string $view = 'filament.widgets.recent-failures';

    protected function getPollingInterval(): ?string
    {
        return config('krai.error_monitoring.recent_failures_polling_interval', '30s');
    }

    public function getRecentErrors(): Collection
    {
        try {
            $limit = config('krai.error_monitoring.recent_failures_limit', 10);

            return PipelineError::with([
                'document:id,filename',
                'resolvedBy:id,name'
            ])
            ->latest('created_at')
            ->limit($limit)
            ->get();
        } catch (\Exception $e) {
            \Log::error('RecentFailuresWidget: Failed to fetch recent errors', [
                'error' => $e->getMessage(),
            ]);
            return collect([]);
        }
    }

    protected function getViewData(): array
    {
        return [
            'recentErrors' => $this->getRecentErrors(),
        ];
    }

    public function getErrorUrl(PipelineError $error): string
    {
        return PipelineErrorResource::getUrl('view', ['record' => $error->error_id]);
    }

    public function retryError(string $errorId): void
    {
        try {
            Notification::make()
                ->title('Retry-Funktion')
                ->body('Backend-API-Integration wird in einer späteren Phase implementiert.')
                ->warning()
                ->send();
        } catch (\Exception $e) {
            Notification::make()
                ->title('Fehler beim Retry')
                ->body('Ein Fehler ist aufgetreten: ' . $e->getMessage())
                ->danger()
                ->send();
        }
    }
}
