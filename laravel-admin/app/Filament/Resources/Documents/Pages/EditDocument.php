<?php

namespace App\Filament\Resources\Documents\Pages;

use App\Filament\Resources\Documents\DocumentResource;
use App\Models\Manufacturer;
use App\Services\KraiEngineService;
use Filament\Actions\Action;
use Filament\Forms\Components\CheckboxList;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Notifications\Notification;
use Filament\Resources\Pages\EditRecord;

class EditDocument extends EditRecord
{
    protected static string $resource = DocumentResource::class;

    public function getPollingInterval(): ?string
    {
        $record = $this->getRecord();
        $status = $record?->processing_status?->value ?? '';

        return in_array($status, ['processing', 'pending', 'queued'])
            ? '5s'
            : null;
    }

    /**
     * Render the body text shown in the "Status prüfen" notification, given the
     * normalized response from KraiEngineService::getDocumentStatus().
     *
     * Extracted from the action closure so it can be unit-tested without
     * spinning up Filament's full action lifecycle.
     *
     * @param  array<string, mixed>  $result
     */
    public static function buildStatusNotificationBody(array $result): string
    {
        $lines = ['Dokumentenstatus: '.($result['status'] ?? 'unknown')];

        $currentStage = $result['current_stage'] ?? null;
        $lines[] = 'Aktuelle Stage: '.($currentStage ?: 'keine');

        $progress = (float) ($result['progress'] ?? 0);
        $lines[] = 'Fortschritt: '.number_format($progress * 100, 1).'%';

        $summary = $result['stage_summary'] ?? [];
        if (is_array($summary) && ! empty($summary)) {
            $lines[] = sprintf(
                '✓ %d  ⏳ %d  ✗ %d  · pending %d',
                $summary['completed'] ?? 0,
                $summary['processing'] ?? 0,
                $summary['failed'] ?? 0,
                $summary['pending'] ?? 0,
            );
        }

        $queuePos = (int) ($result['queue_position'] ?? 0);
        $queueTotal = (int) ($result['total_queue_items'] ?? 0);
        if ($queuePos > 0 && $queueTotal > 0) {
            $lines[] = "Queue-Position: {$queuePos} von {$queueTotal}";
        }

        return implode("\n", $lines);
    }

    protected function getHeaderActions(): array
    {
        return [
            Action::make('viewStageStatus')
                ->label('Stage Status anzeigen')
                ->icon('heroicon-o-chart-bar')
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->modalHeading('Stage Verarbeitungsstatus')
                ->modalContent(function () {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);
                    $statusData = $service->getStageStatus($record->id);

                    // Handle backend errors
                    if (! $statusData['success'] && isset($statusData['error'])) {
                        // Trigger danger notification for backend error
                        Notification::make()
                            ->title('Fehler beim Abrufen des Stage-Status')
                            ->body($statusData['error'])
                            ->danger()
                            ->send();

                        // Return error view
                        return view('filament.components.stage-status-error', [
                            'error' => $statusData['error'],
                        ]);
                    }

                    // Handle case where request succeeded but data not found
                    if (! $statusData['found']) {
                        return view('filament.components.stage-status-empty');
                    }

                    return view('filament.components.stage-status-grid', [
                        'stageStatus' => $statusData['stage_status'],
                        'stageDetails' => $statusData['stage_details'] ?? [],
                        'stages' => config('krai.stages'),
                    ]);
                })
                ->modalWidth('5xl')
                ->slideOver(),

            Action::make('checkStatus')
                ->label('Status prüfen')
                ->icon('heroicon-o-information-circle')
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->action(function (): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $result = $service->getDocumentStatus($record->id);

                    if ($result['success']) {
                        Notification::make()
                            ->title('Dokumentenstatus')
                            ->body(self::buildStatusNotificationBody($result))
                            ->success()
                            ->send();
                    } else {
                        Notification::make()
                            ->title('Statusabfrage fehlgeschlagen')
                            ->body($result['error'] ?? 'Der Dokumentenstatus konnte nicht geladen werden.')
                            ->danger()
                            ->send();
                    }
                }),

            Action::make('processSingleStage')
                ->label('Stage verarbeiten')
                ->icon('heroicon-o-play')
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->form([
                    Select::make('stage')
                        ->label('Stage auswählen')
                        ->options(collect(config('krai.stages'))->except(['upload'])->mapWithKeys(fn ($stage, $key) => [$key => $stage['label']]))
                        ->required()
                        ->helperText('Wählen Sie eine einzelne Stage zur Verarbeitung'),
                ])
                ->action(function (array $data): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $result = $service->processStage($record->id, $data['stage']);

                    if ($result['success']) {
                        Notification::make()
                            ->title('Stage erfolgreich verarbeitet')
                            ->body(sprintf('Stage "%s" wurde zur Verarbeitung eingereiht', config('krai.stages.'.$data['stage'].'.label')))
                            ->success()
                            ->send();
                    } else {
                        Notification::make()
                            ->title('Stage-Verarbeitung fehlgeschlagen')
                            ->body($result['error'] ?? 'Unbekannter Fehler')
                            ->danger()
                            ->send();
                    }
                }),

            Action::make('processMultipleStages')
                ->label('Mehrere Stages verarbeiten')
                ->icon('heroicon-o-play-circle')
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->form([
                    CheckboxList::make('stages')
                        ->label('Stages auswählen')
                        ->options(collect(config('krai.stages'))->except(['upload'])->mapWithKeys(fn ($stage, $key) => [$key => $stage['label']]))
                        ->columns(3)
                        ->required()
                        ->helperText('Wählen Sie mehrere Stages zur sequenziellen Verarbeitung'),

                    \Filament\Forms\Components\Toggle::make('stop_on_error')
                        ->label('Bei Fehler stoppen')
                        ->default(true)
                        ->helperText('Verarbeitung bei erstem Fehler abbrechen'),
                ])
                ->action(function (array $data): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $result = $service->processMultipleStages(
                        $record->id,
                        $data['stages'],
                        $data['stop_on_error'] ?? true
                    );

                    if ($result['success']) {
                        Notification::make()
                            ->title('Stages erfolgreich verarbeitet')
                            ->body(sprintf('%d von %d Stages erfolgreich (%.1f%%)', $result['successful'], $result['total_stages'], $result['success_rate'] * 100))
                            ->success()
                            ->send();
                    } else {
                        Notification::make()
                            ->title('Stage-Verarbeitung teilweise fehlgeschlagen')
                            ->body(sprintf('%d erfolgreich, %d fehlgeschlagen', $result['successful'], $result['failed']))
                            ->warning()
                            ->send();
                    }
                }),

            Action::make('processVideo')
                ->label('Video verarbeiten')
                ->icon('heroicon-o-video-camera')
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->form([
                    TextInput::make('video_url')
                        ->label('Video URL')
                        ->url()
                        ->required()
                        ->placeholder('https://www.youtube.com/watch?v=...')
                        ->helperText('YouTube, Vimeo oder Brightcove URL'),

                    Select::make('manufacturer_select')
                        ->label('Hersteller (optional)')
                        ->options(fn () => Manufacturer::query()
                            ->orderBy('name')
                            ->pluck('name', 'id')
                            ->toArray()
                        )
                        ->searchable()
                        ->preload()
                        ->getSearchResultsUsing(fn (string $search) => Manufacturer::query()
                            ->where('name', 'like', "%{$search}%")
                            ->orderBy('name')
                            ->limit(50)
                            ->pluck('name', 'id')
                            ->toArray()),
                ])
                ->action(function (array $data): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $result = $service->processVideo(
                        $record->id,
                        $data['video_url'],
                        $data['manufacturer_select'] ?? null
                    );

                    if ($result['success']) {
                        Notification::make()
                            ->title('Video erfolgreich verarbeitet')
                            ->body(sprintf('Video "%s" (%s) wurde verknüpft', $result['title'], $result['platform']))
                            ->success()
                            ->send();
                    } else {
                        Notification::make()
                            ->title('Video-Verarbeitung fehlgeschlagen')
                            ->body($result['error'] ?? 'Unbekannter Fehler')
                            ->danger()
                            ->send();
                    }
                }),

            Action::make('generateThumbnail')
                ->label('Thumbnail generieren')
                ->icon('heroicon-o-photo')
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->form([
                    TextInput::make('page')
                        ->label('Seite')
                        ->numeric()
                        ->default(0)
                        ->minValue(0)
                        ->helperText('Seitennummer (0 = erste Seite)'),

                    Select::make('size')
                        ->label('Größe')
                        ->options([
                            '300x400' => 'Standard (300x400)',
                            '600x800' => 'Groß (600x800)',
                            '150x200' => 'Klein (150x200)',
                        ])
                        ->default('300x400'),
                ])
                ->action(function (array $data): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $sizeArray = explode('x', $data['size']);
                    $result = $service->generateThumbnail(
                        $record->id,
                        [(int) $sizeArray[0], (int) $sizeArray[1]],
                        (int) ($data['page'] ?? 0)
                    );

                    if ($result['success']) {
                        Notification::make()
                            ->title('Thumbnail erfolgreich generiert')
                            ->body(sprintf('Thumbnail-URL: %s', $result['thumbnail_url']))
                            ->success()
                            ->send();
                    } else {
                        Notification::make()
                            ->title('Thumbnail-Generierung fehlgeschlagen')
                            ->body($result['error'] ?? 'Unbekannter Fehler')
                            ->danger()
                            ->send();
                    }
                }),

            Action::make('reprocessDocument')
                ->label('Neu verarbeiten')
                ->icon('heroicon-o-arrow-path')
                ->requiresConfirmation()
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->action(function (): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $result = $service->reprocessDocument($record->id);

                    if ($result['success']) {
                        Notification::make()
                            ->title('Dokument neu in Verarbeitung')
                            ->body($result['message'] ?? 'Das Dokument wurde erneut zur Verarbeitung eingereiht.')
                            ->success()
                            ->send();

                        // Refresh the form so the stage-status section reflects
                        // the cleared/pending state immediately.
                        $this->refreshFormData(['stage_status', 'processing_status']);
                    } else {
                        Notification::make()
                            ->title('Reprocessing fehlgeschlagen')
                            ->body($result['error'] ?? 'Das Dokument konnte nicht erneut zur Verarbeitung eingereiht werden.')
                            ->danger()
                            ->send();
                    }
                }),
            Action::make('deleteDocument')
                ->label('Dokument löschen')
                ->icon('heroicon-o-trash')
                ->color('danger')
                ->requiresConfirmation()
                ->visible(function (): bool {
                    $user = auth()->user();

                    if (! $user) {
                        return false;
                    }

                    if (method_exists($user, 'canManageContent')) {
                        return $user->canManageContent();
                    }

                    return false;
                })
                ->action(function (): void {
                    $record = $this->getRecord();
                    $service = app(KraiEngineService::class);

                    $result = $service->deleteDocument($record->id);

                    if ($result['success']) {
                        Notification::make()
                            ->title('Dokument gelöscht')
                            ->body($result['message'] ?? 'Das Dokument wurde gelöscht.')
                            ->success()
                            ->send();

                        $this->redirect(DocumentResource::getUrl());

                        return;
                    }

                    Notification::make()
                        ->title('Löschen fehlgeschlagen')
                        ->body($result['error'] ?? 'Das Dokument konnte nicht gelöscht werden.')
                        ->danger()
                        ->send();
                }),
        ];
    }
}
