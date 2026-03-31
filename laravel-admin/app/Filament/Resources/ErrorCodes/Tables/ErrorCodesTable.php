<?php

namespace App\Filament\Resources\ErrorCodes\Tables;

use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteBulkAction;
use Filament\Actions\EditAction;
use Filament\Tables\Columns\IconColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Filters\TernaryFilter;
use Filament\Tables\Table;

class ErrorCodesTable
{
    public static function configure(Table $table): Table
    {
        return $table

            ->columns([
                TextColumn::make('error_code')
                    ->label('Code')
                    ->searchable()
                    ->sortable(),

                TextColumn::make('manufacturer.name')
                    ->label('Hersteller')
                    ->searchable()
                    ->sortable(),

                TextColumn::make('product_list')
                    ->label('Produkt')
                    ->searchable(false)
                    ->toggleable(isToggledHiddenByDefault: true),

                TextColumn::make('severity_level')
                    ->label('Schweregrad')
                    ->toggleable(isToggledHiddenByDefault: true),

                IconColumn::make('requires_parts')
                    ->label('Teile')
                    ->boolean(),

                TextColumn::make('page_number')
                    ->label('Seite')
                    ->toggleable(isToggledHiddenByDefault: true),

                TextColumn::make('created_at')
                    ->label('Erstellt am')
                    ->dateTime()
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
            ])
            ->filters([
                SelectFilter::make('manufacturer_id')
                    ->label('Hersteller')
                    ->relationship('manufacturer', 'name'),

                TernaryFilter::make('requires_parts')
                    ->label('Teile erforderlich'),
            ])
            ->recordActions([
                EditAction::make(),
            ])
            ->toolbarActions([
                BulkActionGroup::make([
                    DeleteBulkAction::make(),
                ]),
            ]);
    }
}
