<?php

namespace App\Filament\Pages;

use App\Models\Product;
use App\Models\ProductConfiguration;
use Filament\Forms\Components\RichEditor;
use Filament\Forms\Components\Section;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Step;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Wizard;
use Filament\Forms\Form;
use Filament\Pages\Page;
use Illuminate\Support\Facades\Http;

class ConfigurationBuilder extends Page
{
    protected static ?string $navigationIcon = 'heroicon-o-wrench-screwdriver';

    protected static ?string $navigationLabel = 'Konfigurations-Builder';

    protected static ?string $title = 'Konfigurations-Builder';

    protected static string $view = 'filament.pages.configuration-builder';

    protected static ?string $navigationGroup = 'Konfiguration';

    protected static ?int $navigationSort = 1;

    public array $formData = [];

    public array $compatibleAccessories = [];

    public array $validationResult = [
        'valid' => false,
        'errors' => [],
        'warnings' => [],
        'recommendations' => [],
    ];

    public function form(Form $form): Form
    {
        return $form
            ->schema([
                Wizard::make([
                    Step::make('Basisprodukt auswählen')
                        ->icon('heroicon-o-cube')
                        ->description('Wählen Sie das Basisprodukt für Ihre Konfiguration')
                        ->schema([
                            Select::make('base_product_id')
                                ->label('Basisprodukt')
                                ->required()
                                ->searchable()
                                ->preload()
                                ->options(
                                    Product::query()
                                        ->whereIn('product_type', ['multifunction_device', 'printer', 'copier'])
                                        ->get()
                                        ->pluck('model_number', 'id')
                                )
                                ->live()
                                ->afterStateUpdated(function ($state) {
                                    $this->loadCompatibleAccessories($state);
                                    $this->formData['base_product_id'] = $state;
                                }),
                        ]),

                    Step::make('Zubehör auswählen')
                        ->icon('heroicon-o-tag')
                        ->description('Wählen Sie kompatibles Zubehör')
                        ->schema([
                            Select::make('selected_accessory')
                                ->label('Zubehör hinzufügen')
                                ->options(function () {
                                    return collect($this->compatibleAccessories)
                                        ->mapWithKeys(fn ($acc) => [
                                            $acc['id'] => "{$acc['model_number']} - {$acc['product_type']}",
                                        ])
                                        ->toArray();
                                })
                                ->live()
                                ->afterStateUpdated(function ($state) {
                                    if ($state && ! in_array($state, $this->formData['accessory_ids'] ?? [])) {
                                        $this->formData['accessory_ids'][] = $state;
                                        $this->validateConfiguration();
                                    }
                                }),
                        ]),

                    Step::make('Validierung & Speicherung')
                        ->icon('heroicon-o-check-badge')
                        ->description('Überprüfen Sie die Konfiguration')
                        ->schema([
                            Section::make('Validierungsergebnisse')
                                ->icon('heroicon-o-information-circle')
                                ->schema([
                                    TextInput::make('validation_status')
                                        ->label('Status')
                                        ->disabled()
                                        ->default(fn () => $this->validationResult['valid'] ? '✅ Gültig' : '❌ Ungültig'),

                                    TextInput::make('config_name')
                                        ->label('Konfigurationsname')
                                        ->required()
                                        ->helperText('Name für diese Konfiguration'),

                                    RichEditor::make('config_description')
                                        ->label('Beschreibung')
                                        ->helperText('Optionale Notizen zur Konfiguration'),
                                ]),
                        ]),
                ])
                    ->submitAction(\Filament\Forms\Components\Actions\Action::make('submit')
                        ->label('Konfiguration speichern')
                        ->action('saveConfiguration')),
            ])
            ->statePath('formData');
    }

    public function loadCompatibleAccessories(?string $productId): void
    {
        if (! $productId) {
            $this->compatibleAccessories = [];

            return;
        }

        try {
            $response = Http::get("http://localhost:8000/api/v1/products/{$productId}/compatible-accessories");

            if ($response->successful()) {
                $this->compatibleAccessories = $response->json('compatible_accessories', []);
            }
        } catch (\Exception $e) {
            $this->compatibleAccessories = [];
        }
    }

    public function validateConfiguration(): void
    {
        if (empty($this->formData['base_product_id'])) {
            return;
        }

        try {
            $response = Http::post(
                "http://localhost:8000/api/v1/products/{$this->formData['base_product_id']}/validate-configuration",
                [
                    'accessory_ids' => $this->formData['accessory_ids'] ?? [],
                ]
            );

            if ($response->successful()) {
                $this->validationResult = [
                    'valid' => $response->json('valid', false),
                    'errors' => $response->json('errors', []),
                    'warnings' => $response->json('warnings', []),
                    'recommendations' => $response->json('recommendations', []),
                ];
            }
        } catch (\Exception $e) {
            $this->validationResult = [
                'valid' => false,
                'errors' => ['Validierung fehlgeschlagen: '.$e->getMessage()],
                'warnings' => [],
                'recommendations' => [],
            ];
        }
    }

    public function saveConfiguration(): void
    {
        if (! $this->validationResult['valid']) {
            $this->addError('form', 'Konfiguration ist ungültig. Bitte korrigieren Sie die Fehler.');

            return;
        }

        try {
            ProductConfiguration::create([
                'base_product_id' => $this->formData['base_product_id'],
                'name' => $this->formData['config_name'] ?? 'Unbenannte Konfiguration',
                'description' => $this->formData['config_description'] ?? null,
                'accessory_ids' => $this->formData['accessory_ids'] ?? [],
                'validation_status' => $this->validationResult['valid'] ? 'valid' : 'invalid',
                'validation_errors' => $this->validationResult['errors'],
                'validation_warnings' => $this->validationResult['warnings'],
                'validation_recommendations' => $this->validationResult['recommendations'],
                'created_by' => auth()->user()->email ?? 'unknown',
            ]);

            $this->addSuccess('Konfiguration erfolgreich gespeichert!');

            $this->formData = [];
            $this->compatibleAccessories = [];
            $this->validationResult = [
                'valid' => false,
                'errors' => [],
                'warnings' => [],
                'recommendations' => [],
            ];
        } catch (\Exception $e) {
            $this->addError('form', 'Fehler beim Speichern: '.$e->getMessage());
        }
    }
}
