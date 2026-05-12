<?php

namespace App\Filament\Resources\Products\RelationManagers;

use Filament\Forms\Components\RichEditor;
use Filament\Forms\Components\Select;
use Filament\Forms\Form;
use Filament\Resources\RelationManagers\RelationManager;
use Filament\Tables\Actions\CreateAction;
use Filament\Tables\Actions\DeleteAction;
use Filament\Tables\Actions\EditAction;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Enums\ActionsPosition;
use Filament\Tables\Table;

class DependenciesRelationManager extends RelationManager
{
    protected static string $relationship = 'dependencies';

    protected static ?string $recordTitleAttribute = 'id';

    public function form(Form $form): Form
    {
        return $form
            ->schema([
                Select::make('depends_on_option_id')
                    ->label('Abhängig von')
                    ->required()
                    ->searchable()
                    ->preload()
                    ->relationship('dependsOn', 'model_number'),

                Select::make('dependency_type')
                    ->label('Abhängigkeitstyp')
                    ->required()
                    ->options([
                        'requires' => 'Erfordert',
                        'excludes' => 'Schließt aus',
                        'alternative' => 'Alternative',
                    ])
                    ->native(false),

                RichEditor::make('notes')
                    ->label('Notizen'),
            ]);
    }

    public function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('dependsOn.model_number')
                    ->label('Abhängig von')
                    ->sortable()
                    ->searchable(),

                TextColumn::make('dependency_type')
                    ->label('Typ')
                    ->badge()
                    ->color(fn (string $state): string => match ($state) {
                        'requires' => 'warning',
                        'excludes' => 'danger',
                        'alternative' => 'info',
                        default => 'gray',
                    })
                    ->formatStateUsing(fn (string $state): string => match ($state) {
                        'requires' => 'Erfordert',
                        'excludes' => 'Schließt aus',
                        'alternative' => 'Alternative',
                        default => $state,
                    }),

                TextColumn::make('notes')
                    ->label('Notizen')
                    ->html()
                    ->limit(50),
            ])
            ->actions([
                EditAction::make(),
                DeleteAction::make(),
            ], position: ActionsPosition::BeforeColumns)
            ->bulkActions([
                \Filament\Tables\Actions\BulkActionGroup::make([
                    \Filament\Tables\Actions\DeleteBulkAction::make(),
                ]),
            ])
            ->headerActions([
                CreateAction::make(),
            ]);
    }
}
