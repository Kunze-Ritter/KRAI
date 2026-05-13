<?php

namespace App\Filament\Resources\ProductConfigurations;

use App\Filament\Resources\ProductConfigurations\Pages\CreateProductConfiguration;
use App\Filament\Resources\ProductConfigurations\Pages\EditProductConfiguration;
use App\Filament\Resources\ProductConfigurations\Pages\ListProductConfigurations;
use App\Filament\Resources\ProductConfigurations\Schemas\ProductConfigurationForm;
use App\Filament\Resources\ProductConfigurations\Tables\ProductConfigurationsTable;
use App\Models\ProductConfiguration;
use BackedEnum;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Tables\Table;
use Illuminate\Database\Eloquent\Builder;
use UnitEnum;

class ProductConfigurationResource extends Resource
{
    protected static ?string $model = ProductConfiguration::class;

    protected static UnitEnum|string|null $navigationGroup = 'Konfiguration';

    protected static ?string $navigationLabel = 'Gespeicherte Konfigurationen';

    protected static string|BackedEnum|null $navigationIcon = 'heroicon-o-cog-6-tooth';

    protected static ?int $navigationSort = 3;

    protected static ?string $recordTitleAttribute = 'name';

    public static function form(Schema $schema): Schema
    {
        return ProductConfigurationForm::configure($schema);
    }

    public static function table(Table $table): Table
    {
        return ProductConfigurationsTable::configure($table);
    }

    public static function getEloquentQuery(): Builder
    {
        return parent::getEloquentQuery()
            ->with(['baseProduct']);
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
            'index' => ListProductConfigurations::route('/'),
            'create' => CreateProductConfiguration::route('/create'),
            'edit' => EditProductConfiguration::route('/{record}/edit'),
        ];
    }
}
