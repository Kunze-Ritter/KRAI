<?php

namespace App\Filament\Resources\OptionDependencies\Pages;

use App\Filament\Resources\OptionDependencies\OptionDependencyResource;
use Filament\Actions;
use Filament\Resources\Pages\EditRecord;

class EditOptionDependency extends EditRecord
{
    protected static string $resource = OptionDependencyResource::class;

    protected function getHeaderActions(): array
    {
        return [
            Actions\DeleteAction::make(),
        ];
    }
}
