<?php

namespace App\Filament\Resources\Documents\RelationManagers;

use Filament\Actions\ViewAction;
use Filament\Resources\RelationManagers\RelationManager;
use Filament\Tables;
use Filament\Tables\Table;

class RelatedDocumentsRelationManager extends RelationManager
{
    protected static string $relationship = 'relatedDocuments';

    protected static ?string $recordTitleAttribute = 'secondaryDocument.filename';

    public function table(Table $table): Table
    {
        return $table
            ->columns([
                Tables\Columns\TextColumn::make('secondaryDocument.filename')
                    ->label('Related Document')
                    ->searchable()
                    ->sortable(),
                Tables\Columns\TextColumn::make('relationship_type')
                    ->label('Type')
                    ->badge()
                    ->sortable(),
                Tables\Columns\TextColumn::make('relationship_strength')
                    ->label('Strength')
                    ->formatStateUsing(fn (mixed $state) => number_format($state, 2))
                    ->sortable(),
                Tables\Columns\BooleanColumn::make('auto_discovered')
                    ->label('Auto-Discovered')
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\BooleanColumn::make('manual_verification')
                    ->label('Verified')
                    ->sortable(),
                Tables\Columns\TextColumn::make('verified_by')
                    ->label('Verified By')
                    ->toggleable(isToggledHiddenByDefault: true),
                Tables\Columns\TextColumn::make('created_at')
                    ->label('Created')
                    ->dateTime()
                    ->sortable()
                    ->toggleable(isToggledHiddenByDefault: true),
            ])
            ->filters([
                Tables\Filters\SelectFilter::make('relationship_type')
                    ->options([
                        'supersedes' => 'Supersedes',
                        'related' => 'Related',
                        'version_of' => 'Version Of',
                        'replacement' => 'Replacement',
                    ]),
                Tables\Filters\TernaryFilter::make('manual_verification')
                    ->label('Verified'),
            ])
            ->headerActions([
                // Read-only - relationships are auto-discovered or managed separately
            ])
            ->actions([
                ViewAction::make()
                    ->url(fn (Tables\Contracts\HasTable $livewire) => route(
                        'filament.app.resources.documents.edit',
                        $livewire->getOwnerRecord()->secondaryDocument,
                    )),
            ])
            ->bulkActions([
                // Read-only
            ]);
    }
}
