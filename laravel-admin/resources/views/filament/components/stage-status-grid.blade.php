@php
    /**
     * @var array<string, mixed>  $stageStatus  flat [stage => status] map
     *                                          (back-compat from KraiEngineService::getStageStatus())
     * @var array<string, mixed>  $stageDetails structured [stage => {status, error, duration_seconds, ...}]
     *                                          (only populated when the backend returned structured data)
     * @var array<string, array>  $stages       config('krai.stages')
     */
    $stageDetails = $stageDetails ?? [];
    $groups = config('krai.stage_groups');

    $entryFor = function (string $stageKey) use ($stageStatus, $stageDetails): array {
        if (isset($stageDetails[$stageKey]) && is_array($stageDetails[$stageKey])) {
            $entry = $stageDetails[$stageKey];

            return [
                'status' => strtolower((string) ($entry['status'] ?? 'not_started')),
                'error' => $entry['error'] ?? $entry['message'] ?? null,
                'duration' => $entry['duration_seconds'] ?? $entry['processing_time'] ?? null,
            ];
        }

        return [
            'status' => strtolower((string) ($stageStatus[$stageKey] ?? 'not_started')),
            'error' => null,
            'duration' => null,
        ];
    };

    $colorFor = fn (string $status): string => match ($status) {
        'completed' => 'success',
        'failed' => 'danger',
        'processing', 'running', 'pending' => 'warning',
        'skipped' => 'gray',
        default => 'gray',
    };
@endphp

<div class="space-y-6">
    @if(empty($stageStatus) && empty($stageDetails))
        <div class="text-center py-8">
            <x-filament::icon
                icon="heroicon-o-information-circle"
                class="w-12 h-12 mx-auto text-gray-400 mb-4"
            />
            <p class="text-gray-500">Keine Stage-Informationen verfügbar</p>
        </div>
    @else
        @foreach($groups as $group)
            @php
                $groupStages = collect($stages)->filter(fn ($stage) => ($stage['group'] ?? null) === $group);
            @endphp

            @if($groupStages->isNotEmpty())
                <div>
                    <h3 class="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
                        {{ ucfirst($group) }}
                    </h3>

                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        @foreach($groupStages as $stageKey => $stage)
                            @php
                                $entry = $entryFor($stageKey);
                                $status = $entry['status'];
                                $badgeColor = $colorFor($status);
                                $icon = match($status) {
                                    'completed' => 'heroicon-o-check-circle',
                                    'failed' => 'heroicon-o-x-circle',
                                    'processing', 'running', 'pending' => 'heroicon-o-clock',
                                    'skipped' => 'heroicon-o-minus-circle',
                                    default => 'heroicon-o-minus-circle',
                                };
                            @endphp

                            <div class="flex items-start space-x-3 p-4 rounded-lg border-2 border-{{ $badgeColor }}-200 dark:border-{{ $badgeColor }}-800 bg-{{ $badgeColor }}-50 dark:bg-{{ $badgeColor }}-900/20">
                                <x-filament::icon
                                    :icon="$stage['icon'] ?? $icon"
                                    class="w-6 h-6 text-{{ $badgeColor }}-600 dark:text-{{ $badgeColor }}-400 flex-shrink-0 mt-0.5"
                                />
                                <div class="flex-1 min-w-0">
                                    <div class="flex items-center justify-between mb-1">
                                        <h4 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
                                            {{ $stage['label'] ?? $stageKey }}
                                        </h4>
                                        <x-filament::badge :color="$badgeColor" size="sm">
                                            {{ ucfirst($status) }}
                                        </x-filament::badge>
                                    </div>
                                    <p class="text-xs text-gray-600 dark:text-gray-400">
                                        {{ $stage['description'] ?? '' }}
                                    </p>

                                    @if($status === 'failed' && filled($entry['error']))
                                        <p class="mt-2 text-xs text-red-700 dark:text-red-300 break-words">
                                            {{ $entry['error'] }}
                                        </p>
                                    @endif

                                    @if($status === 'completed' && filled($entry['duration']))
                                        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                            Dauer: {{ number_format((float) $entry['duration'], 1) }}s
                                        </p>
                                    @endif
                                </div>
                            </div>
                        @endforeach
                    </div>
                </div>
            @endif
        @endforeach

        <div class="pt-4 border-t border-gray-200 dark:border-gray-700">
            @php
                $sourceForCounts = ! empty($stageDetails) ? $stageDetails : $stageStatus;
                $countByStatus = collect($sourceForCounts)
                    ->map(function ($entry) {
                        if (is_array($entry)) {
                            return strtolower((string) ($entry['status'] ?? ''));
                        }

                        return strtolower((string) $entry);
                    })
                    ->countBy()
                    ->all();

                $total = count($sourceForCounts);
                $completed = $countByStatus['completed'] ?? 0;
                $failed = $countByStatus['failed'] ?? 0;
                $pending = ($countByStatus['pending'] ?? 0) + ($countByStatus['processing'] ?? 0) + ($countByStatus['running'] ?? 0);
                $skipped = $countByStatus['skipped'] ?? 0;
                $progress = $total > 0 ? round(($completed + $skipped) / $total * 100) : 0;
            @endphp

            <div class="flex items-center justify-between text-sm">
                <div class="space-x-4">
                    <span class="text-green-600 dark:text-green-400">✓ {{ $completed }} Abgeschlossen</span>
                    <span class="text-red-600 dark:text-red-400">✗ {{ $failed }} Fehlgeschlagen</span>
                    <span class="text-yellow-600 dark:text-yellow-400">⏳ {{ $pending }} Ausstehend</span>
                    @if($skipped > 0)
                        <span class="text-gray-500 dark:text-gray-400">⊘ {{ $skipped }} Übersprungen</span>
                    @endif
                </div>
                <div class="text-gray-600 dark:text-gray-400 font-semibold">
                    {{ $progress }}% Fortschritt
                </div>
            </div>

            <div class="mt-2 w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                <div class="bg-green-600 dark:bg-green-500 h-2 rounded-full transition-all duration-300" style="width: {{ $progress }}%"></div>
            </div>
        </div>
    @endif
</div>
