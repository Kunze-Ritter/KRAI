<?php

namespace App\Filament\Resources\OptionDependencies;

use App\Filament\Resources\OptionDependencies\Pages\CreateOptionDependency;
use App\Filament\Resources\OptionDependencies\Pages\EditOptionDependency;
use App\Filament\Resources\OptionDependencies\Pages\ListOptionDependencies;
use App\Filament\Resources\OptionDependencies\Schemas\OptionDependencyForm;
use App\Filament\Resources\OptionDependencies\Tables\OptionDependenciesTable;
use App\Models\OptionDependency;
use BackedEnum;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Support\Icons\Heroicon;
use Filament\Tables\Table;
use Illuminate\Database\Eloquent\Builder;
use UnitEnum;

class OptionDependencyResource extends Resource
{
    protected static ?string $model = OptionDependency::class;

    protected static UnitEnum|string|null $navigationGroup = 'Konfiguration';

    protected static ?string $navigationLabel = 'Abhängigkeiten';

    protected static string|BackedEnum|null $navigationIcon = 'heroicon-o-link';

    protected static ?int $navigationSort = 2;

    protected static ?string $recordTitleAttribute = 'id';

    public static function form(Schema $schema): Schema
    {
        return OptionDependencyForm::configure($schema);
    }

    public static function table(Table $table): Table
    {
        return OptionDependenciesTable::configure($table);
    }

    public static function getEloquentQuery(): Builder
    {
        return parent::getEloquentQuery()
            ->with(['option', 'dependsOn']);
    }

    public static function getRelations(): array
    {
        return [
            //
        ];
    }

    public static function getPages(): array
    {
        return [
            'index' => ListOptionDependencies::route('/'),
            'create' => CreateOptionDependency::route('/create'),
            'edit' => EditOptionDependency::route('/{record}/edit'),
        ];
    }
}
