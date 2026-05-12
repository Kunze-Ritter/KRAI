<?php

namespace App\Filament\Resources\Products\RelationManagers;

use Filament\Resources\RelationManagers\RelationManager;
use Filament\Tables;
use Filament\Tables\Table;

class AccessoriesRelationManager extends RelationManager
{
    protected static string $relationship = 'accessories';

    protected static ?string $recordTitleAttribute = 'model_number';

    public function table(Table $table): Table
    {
        return $table
            ->recordTitleAttribute('model_number')
            ->columns([
                Tables\Columns\TextColumn::make('model_number')
                    ->label('Modellnummer')
                    ->sortable()
                    ->searchable(),

                Tables\Columns\TextColumn::make('model_name')
                    ->label('Produktname')
                    ->sortable()
                    ->searchable(),

                Tables\Columns\TextColumn::make('product_type')
                    ->label('Produkttyp')
                    ->badge(),

                Tables\Columns\TextColumn::make('pivot.accessory_type')
                    ->label('Zubehörtyp'),

                Tables\Columns\CheckboxColumn::make('pivot.is_required')
                    ->label('Erforderlich'),
            ])
            ->actions([
                Tables\Actions\DetachAction::make(),
            ])
            ->bulkActions([
                Tables\Actions\BulkActionGroup::make([
                    Tables\Actions\DetachBulkAction::make(),
                ]),
            ])
            ->headerActions([
                Tables\Actions\AttachAction::make()
                    ->preloadRecordSelect()
                    ->recordSelectOptionsQuery(fn ($query) => $query->where('id', '!=', $this->ownerRecord->id)),
            ]);
    }
}
