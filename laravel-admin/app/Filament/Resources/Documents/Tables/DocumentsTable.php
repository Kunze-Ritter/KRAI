<?php

namespace App\Filament\Resources\Documents\Tables;

use App\Enums\DocumentProcessingStatus;
use App\Services\KraiEngineService;
use Filament\Actions\BulkAction;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\EditAction;
use Filament\Forms\Components\Select;
use Filament\Notifications\Notification;
use Filament\Tables\Columns\IconColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\Filter;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Filters\TernaryFilter;
use Filament\Tables\Table;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Collection;

class DocumentsTable
{
    /**
     * Count stage_status entries by status. Tolerates both structured payloads
     * ({"text_extraction": {"status": "completed", ...}}) and legacy flat strings
     * ({"text_extraction": "completed"}) so the table never breaks during the
     * structured-projection rollout.
     *
     * @param  array<string, mixed>  $stageStatus
     * @return array{total: int, completed: int, failed: int, processing: int, pending: int, skipped: int}
     */
    private static function countStageStatuses(array $stageStatus): array
    {
        $buckets = [
            'completed' => 0,
            'failed' => 0,
            'processing' => 0,
            'pending' => 0,
            'skipped' => 0,
        ];

        foreach ($stageStatus as $entry) {
            $raw = is_array($entry) ? ($entry['status'] ?? '') : $entry;
            $status = strtolower((string) $raw);
            if ($status === 'running') {
                $status = 'processing';
            }
            if (isset($buckets[$status])) {
                $buckets[$status]++;
            }
        }

        return $buckets + ['total' => count($stageStatus)];
    }

    /**
     * Bulk-delete a collection of documents through KraiEngineService and surface
     * a single notification. Extracted from the BulkAction closure so it can be
     * tested without spinning up a full Livewire panel.
     *
     * @return array{success: int, failed: int}
     */
    public static function runBulkDelete(Collection $records, KraiEngineService $service): array
    {
        $success = 0;
        $failed = 0;

        foreach ($records as $record) {
            $result = $service->deleteDocument($record->id);
            if ($result['success'] ?? false) {
                $success++;
            } else {
                $failed++;
            }
        }

        $notification = Notification::make()
            ->title('Löschen abgeschlossen')
            ->body(sprintf('%d erfolgreich, %d fehlgeschlagen', $success, $failed));

        if ($failed === 0) {
            $notification->success();
        } elseif ($success === 0) {
            $notification->danger();
        } else {
            $notification->warning();
        }

        $notification->send();

        return ['success' => $success, 'failed' => $failed];
    }

    public static function configure(Table $table): Table
    {
        return $table

            ->columns([
                TextColumn::make('filename')
                    ->label('Dateiname')
                    ->searchable()
                    ->sortable(),

                TextColumn::make('document_type')
                    ->label('Typ')
                    ->sortable(),

                TextColumn::make('language')
                    ->label('Sprache')
                    ->sortable(),

                TextColumn::make('manufacturer')
                    ->label('Hersteller')
                    ->searchable()
                    ->sortable(),

                TextColumn::make('series')
                    ->label('Serie')
                    ->searchable()
                    ->sortable(),

                TextColumn::make('processing_status')
                    ->label('Status')
                    ->formatStateUsing(fn ($state) => DocumentProcessingStatus::labelFor($state))
                    ->sortable(),

                TextColumn::make('stage_status')
                    ->label('Stage Status')
                    ->getStateUsing(function ($record) {
                        $counts = self::countStageStatuses($record->stage_status ?? []);
                        if ($counts['total'] === 0) {
                            return 'Keine Stages';
                        }

                        return sprintf('%d/%d ✓ | %d ✗', $counts['completed'], $counts['total'], $counts['failed']);
                    })
                    ->badge()
                    ->color(function ($record) {
                        $counts = self::countStageStatuses($record->stage_status ?? []);
                        if ($counts['total'] === 0) {
                            return 'gray';
                        }
                        if ($counts['failed'] > 0) {
                            return 'danger';
                        }
                        if (($counts['completed'] + $counts['skipped']) === $counts['total']) {
                            return 'success';
                        }

                        return 'warning';
                    })
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: false),

                TextColumn::make('extracted_metadata')
                    ->label('Hochgeladen von')
                    ->getStateUsing(function ($record) {
                        $metadata = $record->extracted_metadata ?? [];

                        return data_get($metadata, 'upload.uploaded_by.username');
                    })
                    ->toggleable(isToggledHiddenByDefault: true),

                IconColumn::make('manual_review_required')
                    ->label('Review erforderlich')
                    ->boolean(),

                IconColumn::make('manual_review_completed')
                    ->label('Review fertig')
                    ->boolean(),

                TextColumn::make('priority_level')
                    ->label('Prio')
                    ->sortable(),

                TextColumn::make('created_at')
                    ->label('Erstellt am')
                    ->dateTime()
                    ->sortable(),

                TextColumn::make('updated_at')
                    ->label('Aktualisiert am')
                    ->dateTime()
                    ->sortable(),
            ])
            ->filters([
                SelectFilter::make('document_type')
                    ->label('Dokumenttyp')
                    ->options([
                        'service_manual' => 'Service Manual',
                        'parts_catalog' => 'Parts Catalog',
                        'user_guide' => 'User Guide',
                    ]),

                SelectFilter::make('processing_status')
                    ->label('Status')
                    ->options(DocumentProcessingStatus::options()),

                TernaryFilter::make('manual_review_required')
                    ->label('Review erforderlich'),

                TernaryFilter::make('manual_review_completed')
                    ->label('Review fertig'),

                Filter::make('uploader')
                    ->label('Uploader')
                    ->form([
                        \Filament\Forms\Components\TextInput::make('username')
                            ->label('Username')
                            ->placeholder('z.B. kradmin'),
                    ])
                    ->query(function (Builder $query, array $data): Builder {
                        $username = $data['username'] ?? null;

                        if (! $username) {
                            return $query;
                        }

                        $escaped = str_replace(['\\', '%', '_'], ['\\\\', '\\%', '\\_'], $username);

                        return $query->whereRaw(
                            "extracted_metadata->'upload'->'uploaded_by'->>'username' ILIKE ?",
                            ['%'.$escaped.'%']
                        );
                    }),
            ])
            ->recordActions([
                EditAction::make(),
            ])
            ->toolbarActions([
                BulkActionGroup::make([
                    BulkAction::make('deleteDocuments')
                        ->label('Dokumente löschen')
                        ->icon('heroicon-o-trash')
                        ->color('danger')
                        ->requiresConfirmation()
                        ->authorize(fn () => auth()->user()?->canManageContent() ?? false)
                        ->action(fn (Collection $records) => self::runBulkDelete($records, app(KraiEngineService::class)))
                        ->deselectRecordsAfterCompletion(),

                    BulkAction::make('smartProcessBulk')
                        ->label('Smart verarbeiten')
                        ->icon('heroicon-o-sparkles')
                        ->authorize(fn () => auth()->user()?->canManageContent() ?? false)
                        ->action(function (Collection $records) {
                            $service = app(KraiEngineService::class);
                            $stages = config('krai.default_stages', []);
                            $success = 0;
                            $failed = 0;

                            foreach ($records as $record) {
                                $result = $service->processMultipleStages($record->id, $stages, true);
                                if ($result['success'] && ($result['failed'] ?? 0) === 0) {
                                    $success++;
                                } else {
                                    $failed++;
                                }
                            }

                            $notification = Notification::make()
                                ->title('Smart-Verarbeitung abgeschlossen')
                                ->body(sprintf('%d erfolgreich, %d fehlgeschlagen', $success, $failed));

                            if ($failed === 0) {
                                $notification->success();
                            } elseif ($success === 0) {
                                $notification->danger();
                            } else {
                                $notification->warning();
                            }

                            $notification->send();
                        })
                        ->deselectRecordsAfterCompletion(),

                    BulkAction::make('processStageBulk')
                        ->label('Stage verarbeiten')
                        ->icon('heroicon-o-play')
                        ->authorize(fn () => auth()->user()?->canManageContent() ?? false)
                        ->form([
                            Select::make('stage')
                                ->label('Stage auswählen')
                                ->options(collect(config('krai.stages'))->except(['upload'])->mapWithKeys(fn ($stage, $key) => [$key => $stage['label']]))
                                ->required(),
                        ])
                        ->action(function (Collection $records, array $data) {
                            $service = app(KraiEngineService::class);
                            $stage = $data['stage'];
                            $success = 0;
                            $failed = 0;

                            foreach ($records as $record) {
                                $result = $service->processStage($record->id, $stage);
                                if ($result['success']) {
                                    $success++;
                                } else {
                                    $failed++;
                                }
                            }

                            // Determine notification color based on results
                            $notification = Notification::make()
                                ->title('Stage-Verarbeitung abgeschlossen')
                                ->body(sprintf('%d erfolgreich, %d fehlgeschlagen', $success, $failed));

                            if ($failed === 0) {
                                $notification->success();
                            } elseif ($success === 0) {
                                $notification->danger();
                            } else {
                                $notification->warning();
                            }

                            $notification->send();
                        })
                        ->deselectRecordsAfterCompletion(),

                    BulkAction::make('generateThumbnailsBulk')
                        ->label('Thumbnails generieren')
                        ->icon('heroicon-o-photo')
                        ->authorize(fn () => auth()->user()?->canManageContent() ?? false)
                        ->action(function (Collection $records) {
                            $service = app(KraiEngineService::class);
                            $success = 0;
                            $failed = 0;

                            foreach ($records as $record) {
                                $result = $service->generateThumbnail($record->id);
                                if ($result['success']) {
                                    $success++;
                                } else {
                                    $failed++;
                                }
                            }

                            // Determine notification color based on results
                            $notification = Notification::make()
                                ->title('Thumbnail-Generierung abgeschlossen')
                                ->body(sprintf('%d erfolgreich, %d fehlgeschlagen', $success, $failed));

                            if ($failed === 0) {
                                $notification->success();
                            } elseif ($success === 0) {
                                $notification->danger();
                            } else {
                                $notification->warning();
                            }

                            $notification->send();
                        })
                        ->deselectRecordsAfterCompletion(),
                ]),
            ]);
    }
}
