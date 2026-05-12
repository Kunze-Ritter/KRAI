<?php

namespace App\Filament\Resources\OptionDependencies\Pages;

use App\Filament\Resources\OptionDependencies\OptionDependencyResource;
use Filament\Actions;
use Filament\Resources\Pages\ListRecords;

class ListOptionDependencies extends ListRecords
{
    protected static string $resource = OptionDependencyResource::class;

    protected function getHeaderActions(): array
    {
        return [
            Actions\CreateAction::make(),
        ];
    }
}
