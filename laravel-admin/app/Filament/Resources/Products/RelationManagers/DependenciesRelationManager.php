<?php

namespace App\Filament\Resources\Products\RelationManagers;

use Filament\Resources\RelationManagers\RelationManager;
use Filament\Tables;
use Filament\Tables\Table;

class DependenciesRelationManager extends RelationManager
{
    protected static string $relationship = 'dependencies';

    protected static ?string $recordTitleAttribute = 'id';

    public function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('dependsOn.model_number')
                    ->label('Abhängig von')
                    ->sortable()
                    ->searchable(),

                Tables\Columns\TextColumn::make('dependency_type')
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

                Tables\Columns\TextColumn::make('notes')
                    ->label('Notizen')
                    ->html()
                    ->limit(50),
            ])
            ->actions([
                Tables\Actions\DeleteAction::make(),
            ])
            ->bulkActions([
                Tables\Actions\BulkActionGroup::make([
                    Tables\Actions\DeleteBulkAction::make(),
                ]),
            ])
            ->headerActions([
                Tables\Actions\CreateAction::make(),
            ]);
    }
}
