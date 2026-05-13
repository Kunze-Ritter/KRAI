<?php

namespace App\Filament\Resources\Documents\Schemas;

use App\Enums\DocumentProcessingStatus;
use App\Models\Manufacturer;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Toggle;
use Filament\Forms\Components\ViewField;
use Filament\Schemas\Components\Section;
use Filament\Schemas\Schema;

class DocumentForm
{
    public static function configure(Schema $schema): Schema
    {
        return $schema
            ->components([
                TextInput::make('filename')
                    ->label('Dateiname')
                    ->disabled(),

                TextInput::make('document_type')
                    ->label('Dokumenttyp')
                    ->maxLength(100),

                TextInput::make('language')
                    ->label('Sprache')
                    ->maxLength(10),

                TextInput::make('version')
                    ->label('Version')
                    ->maxLength(50),

                TextInput::make('publish_date')
                    ->label('Veröffentlichungsdatum')
                    ->type('date'),

                TextInput::make('page_count')
                    ->label('Seiten')
                    ->numeric()
                    ->disabled(),

                TextInput::make('file_size')
                    ->label('Dateigröße (Bytes)')
                    ->numeric()
                    ->disabled(),

                TextInput::make('processing_status')
                    ->label('Processing Status')
                    ->formatStateUsing(fn ($state) => DocumentProcessingStatus::labelFor($state))
                    ->disabled(),

                TextInput::make('confidence_score')
                    ->label('Confidence')
                    ->numeric()
                    ->disabled(),

                Select::make('manufacturer_id')
                    ->label('Hersteller')
                    ->relationship('manufacturer', 'name')
                    ->searchable()
                    ->preload()
                    ->createOptionForm([
                        TextInput::make('name')
                            ->label('Herstellername')
                            ->required()
                            ->unique(Manufacturer::class, 'name'),
                    ])
                    ->nullable(),

                TextInput::make('series')
                    ->label('Serie')
                    ->maxLength(100),

                Toggle::make('manual_review_required')
                    ->label('Manuelle Prüfung erforderlich'),

                Toggle::make('manual_review_completed')
                    ->label('Manuelle Prüfung abgeschlossen'),

                Textarea::make('manual_review_notes')
                    ->label('Review Notizen')
                    ->rows(3),

                TextInput::make('priority_level')
                    ->label('Priorität')
                    ->numeric(),

                TextInput::make('uploaded_by')
                    ->label('Hochgeladen von')
                    ->disabled()
                    ->dehydrated(false)
                    ->afterStateHydrated(function ($component, $state, $record) {
                        if (! $record) {
                            return;
                        }

                        $metadata = $record->extracted_metadata ?? [];

                        $username = data_get($metadata, 'upload.uploaded_by.username');

                        $component->state($username);
                    }),

                TextInput::make('uploaded_at')
                    ->label('Hochgeladen am')
                    ->disabled()
                    ->dehydrated(false)
                    ->afterStateHydrated(function ($component, $state, $record) {
                        if (! $record) {
                            return;
                        }

                        $metadata = $record->extracted_metadata ?? [];

                        $uploadedAt = data_get($metadata, 'upload.uploaded_by.uploaded_at');

                        $component->state($uploadedAt);
                    }),

                Section::make('Stage Verarbeitungsstatus')
                    ->schema([
                        ViewField::make('stage_status_display')
                            ->label('')
                            ->view('filament.forms.components.stage-status-display')
                            ->columnSpanFull(),
                    ])
                    ->collapsible()
                    ->collapsed(false)
                    ->visible(fn ($record) => $record && ! empty($record->stage_status)),
            ]);
    }
}
