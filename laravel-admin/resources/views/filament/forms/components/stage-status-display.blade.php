@php
    /** @var \App\Models\Document|null $record */
    $record = $getRecord();
    $rawStageStatus = $record?->stage_status ?? [];
    $stages = config('krai.stages');
    $groups = config('krai.stage_groups');

    /**
     * Normalize a stage_status entry to its structured shape.
     * Accepts both legacy flat strings and structured arrays.
     */
    $entryFor = function (mixed $entry): array {
        if (is_array($entry)) {
            return [
                'status' => strtolower((string) ($entry['status'] ?? 'pending')),
                'error' => $entry['error'] ?? $entry['message'] ?? null,
                'duration' => $entry['duration_seconds'] ?? $entry['processing_time'] ?? null,
                'started_at' => $entry['started_at'] ?? null,
                'completed_at' => $entry['completed_at'] ?? null,
            ];
        }

        return [
            'status' => strtolower((string) ($entry ?: 'not_started')),
            'error' => null,
            'duration' => null,
            'started_at' => null,
            'completed_at' => null,
        ];
    };

    $statusColor = fn (string $status): string => match ($status) {
        'completed' => 'success',
        'failed' => 'danger',
        'processing', 'running' => 'warning',
        'skipped' => 'gray',
        'pending' => 'warning',
        default => 'gray',
    };
@endphp

<div class="space-y-4">
    @foreach($groups as $group)
        @php
            $groupStages = collect($stages)->filter(fn ($stage) => ($stage['group'] ?? null) === $group);
        @endphp

        @if($groupStages->isNotEmpty())
            <div>
                <h4 class="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {{ ucfirst($group) }}
                </h4>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
                    @foreach($groupStages as $stageKey => $stage)
                        @php
                            $entry = $entryFor($rawStageStatus[$stageKey] ?? null);
                            $status = $entry['status'];
                            $badgeColor = $statusColor($status);
                            $icon = match($status) {
                                'completed' => 'heroicon-o-check-circle',
                                'failed' => 'heroicon-o-x-circle',
                                'processing', 'running', 'pending' => 'heroicon-o-clock',
                                'skipped' => 'heroicon-o-minus-circle',
                                default => 'heroicon-o-minus-circle',
                            };
                        @endphp

                        <div class="flex flex-col gap-1 p-2 rounded-lg border border-{{ $badgeColor }}-200 dark:border-{{ $badgeColor }}-800">
                            <div class="flex items-center justify-between gap-2">
                                <div class="flex items-center gap-2 min-w-0">
                                    <x-filament::icon
                                        :icon="$icon"
                                        class="w-5 h-5 text-{{ $badgeColor }}-500 flex-shrink-0"
                                    />
                                    <span class="text-xs font-medium text-gray-900 dark:text-gray-100 truncate">
                                        {{ $stage['label'] ?? $stageKey }}
                                    </span>
                                </div>
                                <x-filament::badge :color="$badgeColor" size="sm">
                                    {{ ucfirst($status) }}
                                </x-filament::badge>
                            </div>

                            @if($status === 'failed' && filled($entry['error']))
                                <p class="text-xs text-red-700 dark:text-red-300 pl-7 break-words">
                                    {{ $entry['error'] }}
                                </p>
                            @endif

                            @if($status === 'completed' && filled($entry['duration']))
                                <p class="text-xs text-gray-500 dark:text-gray-400 pl-7">
                                    {{ number_format((float) $entry['duration'], 1) }}s
                                </p>
                            @endif
                        </div>
                    @endforeach
                </div>
            </div>
        @endif
    @endforeach
</div>
