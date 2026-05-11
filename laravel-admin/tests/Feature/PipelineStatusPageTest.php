<?php

namespace Tests\Feature;

use App\Filament\Pages\PipelineStatusPage;
use App\Services\MonitoringService;
use Mockery;
use PHPUnit\Framework\Attributes\Test;
use Tests\TestCase;

class PipelineStatusPageTest extends TestCase
{
    protected function tearDown(): void
    {
        Mockery::close();
        parent::tearDown();
    }

    /**
     * The page should consume the single /monitoring/pipeline-activity endpoint
     * (plan Task 6) and surface active_documents, activity, recent_failures,
     * and terminal_lines for the blade view.
     */
    #[Test]
    public function pipeline_status_page_exposes_pipeline_activity_from_single_endpoint(): void
    {
        $monitoring = Mockery::mock(MonitoringService::class);
        $monitoring->shouldReceive('getPipelineActivity')
            ->once()
            ->andReturn([
                'success' => true,
                'data' => [
                    'pipeline_metrics' => [
                        'total_documents' => 12,
                        'documents_completed' => 7,
                    ],
                    'active_documents' => [
                        [
                            'document_id' => 'doc-1',
                            'filename' => 'manual.pdf',
                            'processing_status' => 'processing',
                            'current_stage' => 'embedding',
                            'progress' => 0.4,
                            'updated_at' => '2026-03-25T12:00:00Z',
                        ],
                    ],
                    'recent_activity' => [
                        [
                            'timestamp' => '2026-03-25T12:00:30Z',
                            'type' => 'stage',
                            'document_id' => 'doc-1',
                            'stage_name' => 'embedding',
                            'status' => 'processing',
                            'message' => 'Stage started',
                        ],
                    ],
                    'recent_failures' => [
                        [
                            'error_id' => 'err-1',
                            'document_id' => 'doc-2',
                            'stage_name' => 'image_processing',
                            'error_message' => 'File missing in object storage',
                            'created_at' => '2026-03-25T11:59:00Z',
                        ],
                    ],
                ],
                'error' => null,
            ]);

        app()->instance(MonitoringService::class, $monitoring);

        $page = app(PipelineStatusPage::class);
        $data = $page->getPipelineActivityData();

        $this->assertTrue($data['success']);
        $this->assertCount(1, $data['active_documents']);
        $this->assertSame('embedding', $data['active_documents'][0]['current_stage']);

        $this->assertCount(1, $data['recent_failures']);
        $this->assertSame('err-1', $data['recent_failures'][0]['error_id']);

        // activity merges recent_activity + recent_failures, sorted by timestamp desc
        $this->assertCount(2, $data['activity']);
        $this->assertSame('stage', $data['activity'][0]['type']);
        $this->assertSame('error', $data['activity'][1]['type']);

        $this->assertNotEmpty($data['terminal_lines']);
        $terminal = implode("\n", $data['terminal_lines']);
        $this->assertStringContainsString('embedding', $terminal);
        $this->assertStringContainsString('File missing in object storage', $terminal);
    }

    #[Test]
    public function pipeline_status_page_surfaces_backend_error_without_throwing(): void
    {
        $monitoring = Mockery::mock(MonitoringService::class);
        $monitoring->shouldReceive('getPipelineActivity')
            ->once()
            ->andReturn([
                'success' => false,
                'data' => [],
                'error' => 'HTTP 503: backend unavailable',
            ]);

        app()->instance(MonitoringService::class, $monitoring);

        $page = app(PipelineStatusPage::class);
        $data = $page->getPipelineActivityData();

        $this->assertFalse($data['success']);
        $this->assertStringContainsString('backend unavailable', $data['error']);
        $this->assertSame([], $data['active_documents']);
        $this->assertSame([], $data['activity']);
        $this->assertSame([], $data['recent_failures']);
        $this->assertSame([], $data['terminal_lines']);
    }
}
