<x-filament::section>
    <x-slot name="heading">
        Performance Metrics
    </x-slot>

    {{-- Stats cards --}}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        @foreach($this->getCachedStats() as $stat)
            <div class="p-4 rounded-lg border bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500 dark:text-gray-400">{{ $stat->getLabel() }}</p>
                        <p class="text-2xl font-semibold mt-1">{{ $stat->getValue() }}</p>
                    </div>
                    <div class="p-2 rounded-full bg-{{ $stat->getColor() }}-100 dark:bg-{{ $stat->getColor() }}-900">
                        <x-filament::icon :icon="$stat->getDescriptionIcon()" class="w-6 h-6 text-{{ $stat->getColor() }}-600" />
                    </div>
                </div>
                @if($stat->getDescription())
                    <p class="text-sm text-gray-500 dark:text-gray-400 mt-2">{{ $stat->getDescription() }}</p>
                @endif
            </div>
        @endforeach
    </div>

        {{-- Per-stage breakdown table --}}
        @if(!empty($stages))
            <div class="mt-6">
                <h3 class="text-lg font-semibold mb-3">Per-Stage Performance Breakdown</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-sm">
                        <thead class="bg-gray-50 dark:bg-gray-800">
                            <tr>
                                <th class="px-4 py-2 text-left">Stage</th>
                                <th class="px-4 py-2 text-right">Baseline Avg</th>
                                <th class="px-4 py-2 text-right">Current Avg</th>
                                <th class="px-4 py-2 text-right">P95 (Baseline)</th>
                                <th class="px-4 py-2 text-right">P95 (Current)</th>
                                <th class="px-4 py-2 text-right">Improvement</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                            @foreach($stages as $stage)
                                <tr>
                                    <td class="px-4 py-3 font-medium">{{ $stage['stage_name'] }}</td>
                                    <td class="px-4 py-3 text-right">{{ number_format($stage['baseline_avg_seconds'] ?? 0, 3) }}s</td>
                                    <td class="px-4 py-3 text-right">{{ number_format($stage['current_avg_seconds'] ?? 0, 3) }}s</td>
                                    <td class="px-4 py-3 text-right">{{ number_format($stage['baseline_p95_seconds'] ?? 0, 3) }}s</td>
                                    <td class="px-4 py-3 text-right">{{ number_format($stage['current_p95_seconds'] ?? 0, 3) }}s</td>
                                    <td class="px-4 py-3 text-right">
                                        @php
                                            $improvement = $stage['improvement_percentage'] ?? 0;
                                            $badgeColor = $improvement >= 30 ? 'success' : ($improvement >= 10 ? 'warning' : 'danger');
                                        @endphp
                                        <x-filament::badge :color="$badgeColor">
                                            {{ number_format($improvement, 1) }}%
                                        </x-filament::badge>
                                    </td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        @else
            <div class="mt-6 text-center py-4 text-gray-500">
                No performance baseline data available. Run benchmark suite to establish baselines.
            </div>
        @endif
    </x-filament::section>
