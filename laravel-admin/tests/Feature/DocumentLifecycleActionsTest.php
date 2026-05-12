<?php

namespace Tests\Feature;

use App\Filament\Resources\Documents\Pages\EditDocument;
use PHPUnit\Framework\Attributes\Test;
use Tests\TestCase;

/**
 * Behavior coverage for the EditDocument header actions and related lifecycle
 * helpers. Plan Task 4 / L.
 *
 * Full Livewire interaction tests for these actions would require a Filament
 * panel + Document factory + matching SQLite migration; instead we test the
 * extracted helpers, which is where the actual logic lives.
 */
class DocumentLifecycleActionsTest extends TestCase
{
    #[Test]
    public function check_status_body_includes_status_current_stage_and_progress(): void
    {
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'processing',
            'current_stage' => 'embedding',
            'progress' => 0.4,
            'queue_position' => 0,
            'total_queue_items' => 0,
            'stage_summary' => [],
        ]);

        $this->assertStringContainsString('Dokumentenstatus: processing', $body);
        $this->assertStringContainsString('Aktuelle Stage: embedding', $body);
        $this->assertStringContainsString('Fortschritt: 40.0%', $body);
    }

    #[Test]
    public function check_status_body_falls_back_to_keine_when_no_current_stage(): void
    {
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'completed',
            'current_stage' => null,
            'progress' => 1.0,
            'queue_position' => 0,
            'total_queue_items' => 0,
            'stage_summary' => [],
        ]);

        $this->assertStringContainsString('Aktuelle Stage: keine', $body);
        $this->assertStringContainsString('Fortschritt: 100.0%', $body);
    }

    #[Test]
    public function check_status_body_renders_stage_summary_counts_when_present(): void
    {
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'processing',
            'current_stage' => 'embedding',
            'progress' => 0.4,
            'queue_position' => 0,
            'total_queue_items' => 0,
            'stage_summary' => [
                'completed' => 6,
                'processing' => 1,
                'failed' => 2,
                'pending' => 7,
            ],
        ]);

        $this->assertStringContainsString('✓ 6', $body);
        $this->assertStringContainsString('⏳ 1', $body);
        $this->assertStringContainsString('✗ 2', $body);
        $this->assertStringContainsString('pending 7', $body);
    }

    #[Test]
    public function check_status_body_omits_stage_summary_line_when_empty(): void
    {
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'pending',
            'current_stage' => 'upload',
            'progress' => 0.0,
            'queue_position' => 0,
            'total_queue_items' => 0,
            'stage_summary' => [],
        ]);

        $this->assertStringNotContainsString('✓', $body);
        $this->assertStringNotContainsString('pending ', $body);  // the summary line, not the status word
    }

    #[Test]
    public function check_status_body_renders_queue_position_when_positive(): void
    {
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'pending',
            'current_stage' => 'upload',
            'progress' => 0.0,
            'queue_position' => 3,
            'total_queue_items' => 12,
            'stage_summary' => [],
        ]);

        $this->assertStringContainsString('Queue-Position: 3 von 12', $body);
    }

    #[Test]
    public function check_status_body_skips_queue_line_when_position_is_zero(): void
    {
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'pending',
            'current_stage' => 'upload',
            'progress' => 0.0,
            'queue_position' => 0,
            'total_queue_items' => 0,
            'stage_summary' => [],
        ]);

        $this->assertStringNotContainsString('Queue-Position', $body);
    }

    #[Test]
    public function check_status_body_tolerates_missing_keys(): void
    {
        // KraiEngineService may omit fields if the backend response was partial.
        $body = EditDocument::buildStatusNotificationBody([
            'success' => true,
            'status' => 'processing',
            // no current_stage, no progress, no stage_summary, no queue
        ]);

        $this->assertStringContainsString('Dokumentenstatus: processing', $body);
        $this->assertStringContainsString('Aktuelle Stage: keine', $body);
        $this->assertStringContainsString('Fortschritt: 0.0%', $body);
    }

    #[Test]
    public function edit_document_wires_delete_action_through_krai_service(): void
    {
        $source = file_get_contents(app_path('Filament/Resources/Documents/Pages/EditDocument.php'));

        $this->assertStringContainsString("Action::make('deleteDocument')", $source);
        $this->assertStringContainsString('$service->deleteDocument(', $source);
        $this->assertStringContainsString('DocumentResource::getUrl()', $source);
    }

    #[Test]
    public function edit_document_wires_reprocess_action_through_krai_service(): void
    {
        $source = file_get_contents(app_path('Filament/Resources/Documents/Pages/EditDocument.php'));

        $this->assertStringContainsString("Action::make('reprocessDocument')", $source);
        $this->assertStringContainsString('$service->reprocessDocument(', $source);
    }
}
