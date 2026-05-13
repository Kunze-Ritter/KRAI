<?php

namespace App\Filament\Resources\Documents\Pages;

use App\Filament\Resources\Documents\DocumentResource;
use App\Models\Manufacturer;
use App\Models\Product;
use App\Models\ProductSeries;
use App\Services\KraiEngineService;
use Filament\Actions\Action;
use Filament\Forms\Components\CheckboxList;
use Filament\Forms\Components\FileUpload;
use Filament\Forms\Components\Grid;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Toggle;
use Filament\Notifications\Notification;
use Filament\Resources\Pages\ListRecords;
use Filament\Schemas\Components\Utilities\Get;
use Filament\Schemas\Components\Utilities\Set;
use Illuminate\Http\UploadedFile;
use InvalidArgumentException;
use Livewire\Features\SupportFileUploads\TemporaryUploadedFile;

class ListDocuments extends ListRecords
{
    protected static string $resource = DocumentResource::class;

    protected function getHeaderActions(): array
    {
        return [
            Action::make('uploadDocument')
                ->label('Dokument hochladen')
                ->icon('heroicon-o-arrow-up-on-square')
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
                    FileUpload::make('file')
                        ->label('PDF-Datei')
                        ->acceptedFileTypes(['application/pdf'])
                        ->maxSize(102400)
                        ->storeFiles(false)
                        ->helperText('Maximale Dateigröße: 100 MB')
                        ->required(),
                    Select::make('document_type')
                        ->label('Dokumenttyp')
                        ->options([
                            'service_manual' => 'Service Manual',
                            'parts_catalog' => 'Parts Catalog',
                            'technical_bulletin' => 'Technical Bulletin',
                            'cpmd_database' => 'CPMD (Control Panel Message Document)',
                            'user_manual' => 'User Manual',
                            'installation_guide' => 'Installation Guide',
                            'troubleshooting_guide' => 'Troubleshooting Guide',
                        ])
                        ->required()
                        ->default('service_manual'),
                    TextInput::make('language')
                        ->label('Sprache')
                        ->maxLength(10)
                        ->default('en'),
                    Select::make('manufacturer')
                        ->label('Hersteller (optional)')
                        ->options(fn (): array => Manufacturer::query()
                            ->orderBy('name')
                            ->pluck('name', 'name')
                            ->toArray()
                        )
                        ->searchable()
                        ->preload()
                        ->live()
                        ->createOptionForm([
                            TextInput::make('name')
                                ->label('Herstellername')
                                ->required()
                                ->unique(Manufacturer::class, 'name'),
                        ])
                        ->helperText('Leer lassen für Auto-Erkennung. Neue Hersteller können hier angelegt werden.')
                        ->afterStateUpdated(function (Set $set): void {
                            $set('series', null);
                            $set('model', null);
                        }),
                    Select::make('series')
                        ->label('Serie (optional)')
                        ->options(fn (Get $get): array => $this->getSeriesOptions($get('manufacturer')))
                        ->searchable()
                        ->preload()
                        ->live()
                        ->createOptionForm([
                            TextInput::make('name')
                                ->label('Serienname')
                                ->required(),
                        ])
                        ->disabled(fn (Get $get): bool => blank($get('manufacturer')))
                        ->helperText('Optional. Für Serie und Modell zuerst Hersteller wählen. Neue Serien können hier angelegt werden.')
                        ->afterStateUpdated(function (Set $set): void {
                            $set('model', null);
                        }),
                    Select::make('model')
                        ->label('Modell (optional)')
                        ->options(fn (Get $get): array => $this->getModelOptions($get('manufacturer'), $get('series')))
                        ->searchable()
                        ->preload()
                        ->disabled(fn (Get $get): bool => blank($get('manufacturer')))
                        ->helperText('Leer lassen für Auto-Erkennung.'),
                    Grid::make(1)
                        ->schema([
                            Toggle::make('select_all_stages')
                                ->label('Alle Stages aktivieren')
                                ->helperText('Aktivieren Sie diese Option, um automatisch alle verfügbaren Stages auszuwählen')
                                ->live()
                                ->afterStateUpdated(function (Get $get, Set $set): void {
                                    if ($get('select_all_stages')) {
                                        $allStages = collect(config('krai.stages'))
                                            ->except(['upload'])
                                            ->keys()
                                            ->toArray();
                                        $set('stages', $allStages);
                                    } else {
                                        $set('stages', null);
                                    }
                                }),
                            CheckboxList::make('stages')
                                ->label('Stages zur Verarbeitung (optional)')
                                ->options(collect(config('krai.stages'))->except(['upload'])->mapWithKeys(fn ($stage, $key) => [$key => $stage['label']]))
                                ->columns(3)
                                ->helperText('Leer lassen für vollständige Verarbeitung (alle Stages). Oder nutzen Sie "Alle Stages aktivieren" oben.')
                                ->default(null),
                        ]),
                    Toggle::make('stop_on_error')
                        ->label('Bei Fehler stoppen')
                        ->default(true)
                        ->helperText('Verarbeitung bei erstem Fehler abbrechen')
                        ->visible(fn ($get) => ! empty($get('stages'))),
                ])
                ->action(function (array $data): void {
                    try {
                        $file = $this->normalizeUploadedFile($data['file'] ?? null);
                    } catch (InvalidArgumentException $exception) {
                        Notification::make()
                            ->title('Upload fehlgeschlagen')
                            ->body($exception->getMessage())
                            ->danger()
                            ->send();

                        return;
                    }

                    $service = app(KraiEngineService::class);
                    $user = auth()->user();

                    // Upload document using service
                    $uploadResult = $service->uploadDocument(
                        $file,
                        $data['document_type'],
                        $data['language'] ?? 'en',
                        $user,
                        $this->buildUploadContextPayload($data)
                    );

                    if (! $uploadResult['success']) {
                        Notification::make()
                            ->title('Upload fehlgeschlagen')
                            ->body($uploadResult['error'] ?? 'Der Upload konnte nicht durchgeführt werden.')
                            ->danger()
                            ->send();

                        return;
                    }

                    $documentId = $uploadResult['document_id'];

                    if (! $documentId) {
                        Notification::make()
                            ->title('Upload fehlgeschlagen')
                            ->body('Dokument-ID konnte nicht ermittelt werden.')
                            ->danger()
                            ->send();

                        return;
                    }

                    // If custom stages selected, process them
                    if (! empty($data['stages'])) {
                        $stageResult = $service->processMultipleStages(
                            $documentId,
                            $data['stages'],
                            $data['stop_on_error'] ?? true,
                            $user
                        );

                        if ($stageResult['success']) {
                            Notification::make()
                                ->title('Dokument hochgeladen und verarbeitet')
                                ->body(sprintf('Upload erfolgreich. %d von %d Stages abgeschlossen.', $stageResult['successful'], $stageResult['total_stages']))
                                ->success()
                                ->send();
                        } else {
                            Notification::make()
                                ->title('Dokument hochgeladen, Verarbeitung teilweise fehlgeschlagen')
                                ->body(sprintf('%d erfolgreich, %d fehlgeschlagen', $stageResult['successful'], $stageResult['failed']))
                                ->warning()
                                ->send();
                        }
                    } else {
                        $reprocessResult = $service->reprocessDocument($documentId, $user);

                        if ($reprocessResult['success']) {
                            Notification::make()
                                ->title('Dokument hochgeladen und eingereiht')
                                ->body('Das Dokument wurde hochgeladen und zur vollständigen Verarbeitung eingereiht.')
                                ->success()
                                ->send();
                        } else {
                            Notification::make()
                                ->title('Dokument hochgeladen, aber Verarbeitung nicht gestartet')
                                ->body($reprocessResult['error'] ?? 'Die vollständige Verarbeitung konnte nicht automatisch gestartet werden.')
                                ->warning()
                                ->send();
                        }
                    }

                    // Refresh the documents table to show the new document
                    $this->resetTable();
                }),
            // Kein Create-Button, Upload läuft (später) über eigenen Flow
        ];
    }

    protected function normalizeUploadedFile(mixed $file): UploadedFile
    {
        if (is_array($file)) {
            $file = reset($file) ?: null;
        }

        if ($file instanceof UploadedFile) {
            return $file;
        }

        if (is_string($file) && TemporaryUploadedFile::canUnserialize($file)) {
            $file = TemporaryUploadedFile::unserializeFromLivewireRequest($file);

            if ($file instanceof UploadedFile) {
                return $file;
            }
        }

        throw new InvalidArgumentException('Die temporäre Upload-Datei konnte nicht verarbeitet werden. Bitte Datei erneut auswählen.');
    }

    protected function buildUploadContextPayload(array $data): array
    {
        return array_filter([
            'manufacturer' => $this->normalizeOptionalSelection($data['manufacturer'] ?? null),
            'series' => $this->normalizeOptionalSelection($data['series'] ?? null),
            'model' => $this->normalizeOptionalSelection($data['model'] ?? null),
        ], static fn (?string $value): bool => filled($value));
    }

    protected function getSeriesOptions(?string $manufacturer): array
    {
        if (blank($manufacturer)) {
            return [];
        }

        return ProductSeries::query()
            ->whereHas('manufacturer', fn ($query) => $query->where('name', $manufacturer))
            ->orderBy('series_name')
            ->pluck('series_name', 'series_name')
            ->toArray();
    }

    protected function getModelOptions(?string $manufacturer, ?string $series): array
    {
        if (blank($manufacturer)) {
            return [];
        }

        return Product::query()
            ->whereHas('manufacturer', fn ($query) => $query->where('name', $manufacturer))
            ->when(
                filled($series),
                fn ($query) => $query->whereHas('series', fn ($seriesQuery) => $seriesQuery->where('series_name', $series))
            )
            ->orderBy('model_number')
            ->get(['model_number', 'model_name'])
            ->mapWithKeys(function (Product $product): array {
                $label = $product->model_number;

                if (filled($product->model_name) && $product->model_name !== $product->model_number) {
                    $label .= ' - '.$product->model_name;
                }

                return [$product->model_number => $label];
            })
            ->all();
    }

    protected function normalizeOptionalSelection(mixed $value): ?string
    {
        if (! is_string($value)) {
            return null;
        }

        $value = trim($value);

        return $value !== '' ? $value : null;
    }
}
