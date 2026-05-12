<?php

namespace App\Filament\Resources\Products\RelationManagers;

use Filament\Forms\Components\Checkbox;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Form;
use Filament\Resources\RelationManagers\RelationManager;
use Filament\Tables\Actions\AttachAction;
use Filament\Tables\Actions\DetachAction;
use Filament\Tables\Actions\EditAction;
use Filament\Tables\Columns\CheckboxColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Enums\ActionsPosition;
use Filament\Tables\Table;

class AccessoriesRelationManager extends RelationManager
{
    protected static string $relationship = 'accessories';

    protected static ?string $recordTitleAttribute = 'model_number';

    public function form(Form $form): Form
    {
        return $form
            ->schema([
                TextInput::make('accessory_type')
                    ->label('Zubehörtyp')
                    ->helperText('z.B. Finisher, Punch Kit, Relay Unit'),

                Checkbox::make('is_required')
                    ->label('Erforderlich')
                    ->helperText('Markieren Sie, wenn dieses Zubehör erforderlich ist'),
            ]);
    }

    public function table(Table $table): Table
    {
        return $table
            ->recordTitleAttribute('model_number')
            ->columns([
                TextColumn::make('model_number')
                    ->label('Modellnummer')
                    ->sortable()
                    ->searchable(),

                TextColumn::make('model_name')
                    ->label('Produktname')
                    ->sortable()
                    ->searchable(),

                TextColumn::make('product_type')
                    ->label('Produkttyp')
                    ->badge(),

                TextColumn::make('pivot.accessory_type')
                    ->label('Zubehörtyp'),

                CheckboxColumn::make('pivot.is_required')
                    ->label('Erforderlich'),
            ])
            ->actions([
                EditAction::make(),
                DetachAction::make(),
            ], position: ActionsPosition::BeforeColumns)
            ->bulkActions([
                \Filament\Tables\Actions\BulkActionGroup::make([
                    \Filament\Tables\Actions\DetachBulkAction::make(),
                ]),
            ])
            ->headerActions([
                AttachAction::make()
                    ->preloadRecordSelect()
                    ->recordSelectOptionsQuery(fn ($query) => $query->where('id', '!=', $this->ownerRecord->id)),
            ]);
    }
}
