<?php

namespace App\Filament\Resources\OptionDependencies\Schemas;

use App\Models\Product;
use Filament\Forms\Components\RichEditor;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\TextInput;
use Filament\Schemas\Schema;

class OptionDependencyForm
{
    public static function configure(Schema $schema): Schema
    {
        return $schema
            ->schema([
                Select::make('option_id')
                    ->label('Option (Produkt mit Zubehör)')
                    ->required()
                    ->searchable()
                    ->preload()
                    ->options(
                        Product::query()
                            ->get()
                            ->pluck('model_number', 'id')
                    ),

                Select::make('depends_on_option_id')
                    ->label('Abhängig von (erforderliches Zubehör)')
                    ->required()
                    ->searchable()
                    ->preload()
                    ->options(
                        Product::query()
                            ->get()
                            ->pluck('model_number', 'id')
                    ),

                Select::make('dependency_type')
                    ->label('Abhängigkeitstyp')
                    ->required()
                    ->options([
                        'requires' => 'Erfordert (muss vorhanden sein)',
                        'excludes' => 'Schließt sich gegenseitig aus (kann nicht zusammen verwendet werden)',
                        'alternative' => 'Alternative (kann als Alternative verwendet werden)',
                    ])
                    ->native(false),

                RichEditor::make('notes')
                    ->label('Notizen')
                    ->helperText('Zusätzliche Informationen zur Abhängigkeit'),
            ]);
    }
}
