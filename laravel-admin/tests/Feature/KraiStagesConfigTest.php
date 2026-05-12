<?php

namespace Tests\Feature;

use PHPUnit\Framework\Attributes\Test;
use Tests\TestCase;

class KraiStagesConfigTest extends TestCase
{
    /**
     * Canonical stages tracked by the KRAI pipeline. The first 15 entries
     * mirror backend/models/document.py CANONICAL_STAGES exactly. The 16th
     * (video_enrichment) is an optional Brightcove-gated stage processed by
     * backend/pipeline/master_pipeline.py but absent from the backend
     * CANONICAL_STAGES list — Laravel still renders it because master_pipeline
     * writes its status into the stage_status JSONB.
     */
    private const BACKEND_CANONICAL_STAGES = [
        'upload',
        'text_extraction',
        'table_extraction',
        'svg_processing',
        'image_processing',
        'visual_embedding',
        'link_extraction',
        'chunk_prep',
        'classification',
        'metadata_extraction',
        'parts_extraction',
        'series_detection',
        'storage',
        'embedding',
        'search_indexing',
    ];

    private const LARAVEL_EXTRA_STAGES = [
        'video_enrichment',
    ];

    private const EXPECTED_STAGES = [
        ...self::BACKEND_CANONICAL_STAGES,
        ...self::LARAVEL_EXTRA_STAGES,
    ];

    private const VALID_GROUPS = [
        'initialization',
        'extraction',
        'processing',
        'enrichment',
        'finalization',
    ];

    #[Test]
    public function krai_stages_config_contains_every_canonical_stage(): void
    {
        $stages = config('krai.stages');

        $this->assertIsArray($stages);
        $configKeys = array_keys($stages);

        $missing = array_diff(self::EXPECTED_STAGES, $configKeys);
        $this->assertEmpty(
            $missing,
            'config/krai.php is missing canonical stages: '.implode(', ', $missing)
        );
    }

    #[Test]
    public function every_stage_declares_required_attributes(): void
    {
        $stages = config('krai.stages');

        foreach ($stages as $key => $stage) {
            $this->assertIsArray($stage, "Stage {$key} must be an array");
            $this->assertArrayHasKey('label', $stage, "Stage {$key} missing label");
            $this->assertArrayHasKey('description', $stage, "Stage {$key} missing description");
            $this->assertArrayHasKey('icon', $stage, "Stage {$key} missing icon");
            $this->assertArrayHasKey('group', $stage, "Stage {$key} missing group");
            $this->assertArrayHasKey('order', $stage, "Stage {$key} missing order");
            $this->assertContains(
                $stage['group'],
                self::VALID_GROUPS,
                "Stage {$key} has invalid group '{$stage['group']}'"
            );
        }
    }

    #[Test]
    public function default_stages_excludes_upload_and_covers_canonical_stages(): void
    {
        $defaults = config('krai.default_stages');

        $this->assertIsArray($defaults);
        $this->assertNotContains('upload', $defaults, 'default_stages must not include upload');

        $expected = array_values(array_diff(self::EXPECTED_STAGES, ['upload']));
        $missing = array_diff($expected, $defaults);

        $this->assertEmpty(
            $missing,
            'default_stages is missing: '.implode(', ', $missing)
        );
    }
}
