<?php

namespace App\Filament\Resources\ErrorCodes;

use App\Filament\Resources\ErrorCodes\Pages\CreateErrorCode;
use App\Filament\Resources\ErrorCodes\Pages\EditErrorCode;
use App\Filament\Resources\ErrorCodes\Pages\ListErrorCodes;
use App\Filament\Resources\ErrorCodes\Schemas\ErrorCodeForm;
use App\Filament\Resources\ErrorCodes\Tables\ErrorCodesTable;
use App\Models\ErrorCode;
use BackedEnum;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Support\Icons\Heroicon;
use Filament\Tables\Table;
use Illuminate\Database\Eloquent\Builder;
use UnitEnum;

class ErrorCodeResource extends Resource
{
    protected static ?string $model = ErrorCode::class;

    protected static UnitEnum|string|null $navigationGroup = 'Data';

    protected static ?string $navigationLabel = 'Fehlercodes';

    protected static string|BackedEnum|null $navigationIcon = 'heroicon-o-exclamation-triangle';

    protected static ?int $navigationSort = 3;

    protected static ?string $recordTitleAttribute = 'error_code';

    public static function form(Schema $schema): Schema
    {
        return ErrorCodeForm::configure($schema);
    }

    public static function table(Table $table): Table
    {
        return ErrorCodesTable::configure($table);
    }

    public static function getEloquentQuery(): Builder
    {
        return parent::getEloquentQuery()->with(['manufacturer']);
    }

    public static function getRelations(): array
    {
        return [
            // Relations können später ergänzt werden
        ];
    }

    public static function getPages(): array
    {
        return [
            'index' => ListErrorCodes::route('/'),
            'create' => CreateErrorCode::route('/create'),
            'edit' => EditErrorCode::route('/{record}/edit'),
        ];
    }
}
