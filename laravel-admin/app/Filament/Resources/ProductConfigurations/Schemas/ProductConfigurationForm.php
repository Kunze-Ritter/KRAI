<?php

namespace App\Filament\Resources\ProductConfigurations\Schemas;

use App\Models\Product;
use Filament\Forms\Components\Grid;
use Filament\Forms\Components\RichEditor;
use Filament\Forms\Components\Section;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TagsInput;
use Filament\Forms\Components\TextInput;
use Filament\Schemas\Schema;

class ProductConfigurationForm
{
    public static function configure(Schema $schema): Schema
    {
        return $schema
            ->schema([
                Grid::make(2)
                    ->schema([
                        Select::make('base_product_id')
                            ->label('Basisprodukt')
                            ->required()
                            ->searchable()
                            ->preload()
                            ->columnSpan(1)
                            ->options(
                                Product::query()
                                    ->whereIn('product_type', ['multifunction_device', 'printer', 'copier'])
                                    ->get()
                                    ->pluck('model_number', 'id')
                            ),

                        TextInput::make('name')
                            ->label('Konfigurationsname')
                            ->required()
                            ->columnSpan(1),

                        RichEditor::make('description')
                            ->label('Beschreibung')
                            ->columnSpan(2),
                    ]),

                Section::make('Zubehör')
                    ->icon('heroicon-o-tag')
                    ->schema([
                        TagsInput::make('accessory_ids')
                            ->label('Zubehör IDs')
                            ->helperText('UUIDs der kompatiblen Zubehörteile'),
                    ]),

                Section::make('Validierungsergebnisse')
                    ->icon('heroicon-o-check-badge')
                    ->schema([
                        Select::make('validation_status')
                            ->label('Status')
                            ->options([
                                'valid' => 'Gültig',
                                'invalid' => 'Ungültig',
                            ])
                            ->required(),
                    ]),

                Section::make('Metadaten')
                    ->icon('heroicon-o-information-circle')
                    ->collapsible()
                    ->schema([
                        TextInput::make('created_by')
                            ->label('Erstellt von')
                            ->disabled()
                            ->helperText('Wird automatisch gesetzt'),
                    ]),
            ]);
    }
}
