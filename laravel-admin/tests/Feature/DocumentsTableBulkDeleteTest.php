<?php

namespace Tests\Feature;

use App\Filament\Resources\Documents\Tables\DocumentsTable;
use App\Services\KraiEngineService;
use Illuminate\Support\Collection;
use Mockery;
use PHPUnit\Framework\Attributes\Test;
use Tests\TestCase;

class DocumentsTableBulkDeleteTest extends TestCase
{
    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    private function makeRecord(string $id): object
    {
        $record = new \stdClass;
        $record->id = $id;

        return $record;
    }

    #[Test]
    public function bulk_delete_calls_krai_service_for_every_record(): void
    {
        $service = Mockery::mock(KraiEngineService::class);
        $service->shouldReceive('deleteDocument')->with('doc-1')->once()->andReturn(['success' => true]);
        $service->shouldReceive('deleteDocument')->with('doc-2')->once()->andReturn(['success' => true]);

        $records = new Collection([
            $this->makeRecord('doc-1'),
            $this->makeRecord('doc-2'),
        ]);

        $result = DocumentsTable::runBulkDelete($records, $service);

        $this->assertSame(2, $result['success']);
        $this->assertSame(0, $result['failed']);
    }

    #[Test]
    public function bulk_delete_counts_failures_and_skips_successful_records(): void
    {
        $service = Mockery::mock(KraiEngineService::class);
        $service->shouldReceive('deleteDocument')->with('doc-1')->andReturn(['success' => true]);
        $service->shouldReceive('deleteDocument')->with('doc-2')->andReturn(['success' => false, 'error' => 'boom']);
        $service->shouldReceive('deleteDocument')->with('doc-3')->andReturn(['success' => true]);

        $records = new Collection([
            $this->makeRecord('doc-1'),
            $this->makeRecord('doc-2'),
            $this->makeRecord('doc-3'),
        ]);

        $result = DocumentsTable::runBulkDelete($records, $service);

        $this->assertSame(2, $result['success']);
        $this->assertSame(1, $result['failed']);
    }

    #[Test]
    public function bulk_delete_handles_empty_collection_without_calling_service(): void
    {
        $service = Mockery::mock(KraiEngineService::class);
        $service->shouldNotReceive('deleteDocument');

        $result = DocumentsTable::runBulkDelete(new Collection, $service);

        $this->assertSame(0, $result['success']);
        $this->assertSame(0, $result['failed']);
    }

    #[Test]
    public function bulk_action_is_wired_through_kra_service_not_eloquent_delete(): void
    {
        // Source-level safety net: regression guard against accidental revert
        // to DeleteBulkAction (which would bypass the backend cleanup pipeline).
        $source = file_get_contents(app_path('Filament/Resources/Documents/Tables/DocumentsTable.php'));

        $this->assertStringContainsString("BulkAction::make('deleteDocuments')", $source);
        $this->assertStringContainsString('self::runBulkDelete', $source);
        $this->assertStringNotContainsString('DeleteBulkAction::make()', $source);
    }
}
