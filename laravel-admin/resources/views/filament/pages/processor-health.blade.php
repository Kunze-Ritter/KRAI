<x-filament::page>
    <div class="space-y-4">
        @if (!($processorData['success'] ?? false))
            <div class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 flex items-start gap-3">
                <x-filament::icon icon="heroicon-o-exclamation-triangle" class="h-6 w-6 text-red-500" />
                <div>
                    <div class="font-semibold">Fehler beim Laden der Prozessor-Daten</div>
                    <div class="text-sm">{{ $processorData['error'] ?? 'Unbekannter Fehler' }}</div>
                </div>
            </div>
        @else
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                @foreach ($processorData['processors'] as $processor)
                    <x-filament::section>
                        <div class="flex items-center justify-between">
                            <div>
                                <div class="flex items-center gap-2">
                                    <span class="font-semibold text-lg">{{ $processor['name'] ?? 'Unbekannt' }}</span>
                                    @if ($processor['is_active'] ?? false)
                                        <span class="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse"></span>
                                    @endif
                                </div>
                                <div class="text-sm text-gray-500">
                                    {{ krai_stage_label($processor['stage_name'] ?? '') }}
                                </div>
                            </div>
                            <x-filament::badge :color="$this->getStatusBadgeColor($processor['status'] ?? '')">
                                {{ ucfirst($processor['status'] ?? 'unbekannt') }}
                            </x-filament::badge>
                        </div>

                        <div class="mt-4 flex items-center gap-4">
                            @php
                                $health = (float) ($processor['health_score'] ?? 0);
                                $dash = max(0, min(100, $health)) * 3.14;
                            @endphp
                            <div class="relative h-20 w-20">
                                <svg class="h-20 w-20 rotate-[-90deg]" viewBox="0 0 36 36">
                                    <circle cx="18" cy="18" r="16" fill="none" class="stroke-gray-200" stroke-width="3" />
                                    <circle
                                        cx="18"
                                        cy="18"
                                        r="16"
                                        fill="none"
                                        stroke-width="3"
                                        class="{{ $this->getHealthScoreColor($health) }}"
                                        stroke-dasharray="100"
                                        stroke-dashoffset="{{ 100 - min(100, $health) }}"
                                    />
                                </svg>
                                <div class="absolute inset-0 flex items-center justify-center">
                                    <span class="text-xl font-semibold">{{ number_format($health, 0) }}%</span>
                                </div>
                            </div>
                            <div class="grid grid-cols-2 gap-3 text-sm w-full">
                                <div>
                                    <div class="text-gray-500">Dokumente in Bearbeitung</div>
                                    <div class="font-semibold">{{ $processor['documents_processing'] ?? 0 }}</div>
                                </div>
                                <div>
                                    <div class="text-gray-500">Warteschlange</div>
                                    <div class="font-semibold">{{ $processor['documents_in_queue'] ?? 0 }}</div>
                                </div>
                                <div>
                                    <div class="text-gray-500">Ø Bearbeitungszeit</div>
                                    <div class="font-semibold">
                                        {{ number_format((float) ($processor['avg_processing_time_seconds'] ?? 0), 2) }}s
                                    </div>
                                </div>
                                <div>
                                    <div class="text-gray-500">Fehlerrate</div>
                                    <div class="flex items-center gap-2">
                                        @php
                                            $errorRate = (float) ($processor['error_rate'] ?? 0);
                                        @endphp
                                        <div class="w-full h-2 rounded-full bg-gray-200">
                                            <div class="h-2 rounded-full bg-red-500" style="width: {{ min(100, $errorRate) }}%"></div>
                                        </div>
                                        <span class="font-semibold">{{ number_format($errorRate, 1) }}%</span>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="mt-4 grid grid-cols-2 gap-2 text-xs text-gray-600">
                            <div>
                                <div class="text-gray-500">Letzte Aktivität</div>
                                <div class="font-medium">
                                    @if (!empty($processor['last_activity_at']))
                                        {{ date('d.m.Y H:i:s', strtotime($processor['last_activity_at'])) }}
                                    @else
                                        -
                                    @endif
                                </div>
                            </div>
                            <div class="text-right">
                                <div class="text-gray-500">Dokument</div>
                                <div class="font-mono truncate text-sm">
                                    {{ $processor['current_document_id'] ?? '—' }}
                                </div>
                            </div>
                        </div>
                    </x-filament::section>
                @endforeach
            </div>

            <div class="text-xs text-gray-500 mt-2">
                Aktualisiert um {{ now()->format('H:i:s') }}
            </div>
        @endif
    </div>
</x-filament::page>
