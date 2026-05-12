<?php

namespace App\Filament\Resources\OptionDependencies\Tables;

use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Enums\ActionsPosition;
use Filament\Tables\Table;

class OptionDependenciesTable
{
    public static function configure(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('option.model_number')
                    ->label('Option (Zubehör)')
                    ->sortable()
                    ->searchable(),

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

                TextColumn::make('created_at')
                    ->label('Erstellt am')
                    ->dateTime('d.m.Y H:i')
                    ->sortable(),
            ])
            ->actions(function (): array {
                return [
                    \Filament\Tables\Actions\EditAction::make(),
                    \Filament\Tables\Actions\DeleteAction::make(),
                ];
            }, position: ActionsPosition::BeforeColumns)
            ->bulkActions([
                \Filament\Tables\Actions\BulkActionGroup::make([
                    \Filament\Tables\Actions\DeleteBulkAction::make(),
                ]),
            ])
            ->defaultSort('created_at', 'desc')
            ->paginated([10, 25, 50]);
    }
}
