@php
    $stageTracking = $getState() ?? [];
    $sortedStages = collect($stageTracking)
        ->sortBy('created_at')
        ->values();

    $statusColors = [
        'completed' => 'bg-green-50 border-green-200',
        'processing' => 'bg-blue-50 border-blue-200',
        'failed' => 'bg-red-50 border-red-200',
        'pending' => 'bg-gray-50 border-gray-200',
        'queued' => 'bg-yellow-50 border-yellow-200',
    ];

    $statusIcons = [
        'completed' => 'heroicon-m-check-circle text-green-600',
        'processing' => 'heroicon-m-arrow-path text-blue-600 animate-spin',
        'failed' => 'heroicon-m-x-circle text-red-600',
        'pending' => 'heroicon-m-clock text-gray-600',
        'queued' => 'heroicon-m-clock text-yellow-600',
    ];
@endphp

<div class="space-y-2">
    @if ($sortedStages->isEmpty())
        <div class="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-6 text-center">
            <p class="text-sm text-gray-600">Keine Stage-Aktivität vorhanden</p>
        </div>
    @else
        <div class="relative space-y-4">
            @foreach ($sortedStages as $index => $stage)
                @php
                    $status = $stage['status'] ?? 'pending';
                    $colorClass = $statusColors[$status] ?? $statusColors['pending'];
                    $iconClass = $statusIcons[$status] ?? $statusIcons['pending'];
                @endphp

                <div class="relative flex gap-4">
                    {{-- Timeline line --}}
                    @if ($index < $sortedStages->count() - 1)
                        <div class="absolute left-4 top-10 h-[calc(100%+1rem)] w-0.5 bg-gray-200"></div>
                    @endif

                    {{-- Icon --}}
                    <div class="relative flex flex-shrink-0 items-center justify-center">
                        <div class="flex h-9 w-9 items-center justify-center rounded-full bg-white ring-2 ring-white">
                            @switch($status)
                                @case('completed')
                                    <svg class="h-5 w-5 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                                    </svg>
                                    @break
                                @case('processing')
                                    <svg class="h-5 w-5 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                    @break
                                @case('failed')
                                    <svg class="h-5 w-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                                    </svg>
                                    @break
                                @default
                                    <svg class="h-5 w-5 text-gray-600" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 102 0V6z" clip-rule="evenodd" />
                                    </svg>
                            @endswitch
                        </div>
                    </div>

                    {{-- Content --}}
                    <div class="flex-1 rounded-lg border px-4 py-3 {{ $colorClass }}">
                        <div class="flex items-start justify-between">
                            <div class="flex-1">
                                <h4 class="font-medium text-gray-900">
                                    {{ str($stage['stage_name'] ?? 'unknown')->replace('_', ' ')->title() }}
                                </h4>
                                <p class="mt-0.5 text-xs font-medium uppercase tracking-wide text-gray-600">
                                    @switch($status)
                                        @case('completed')
                                            ✓ Abgeschlossen
                                            @break
                                        @case('processing')
                                            ⏳ Wird verarbeitet
                                            @break
                                        @case('failed')
                                            ✗ Fehlgeschlagen
                                            @break
                                        @case('pending')
                                            ◯ Ausstehend
                                            @break
                                        @case('queued')
                                            ◆ In Warteschlange
                                            @break
                                    @endswitch
                                </p>
                            </div>
                            <div class="text-right">
                                <p class="text-xs text-gray-500">
                                    @if ($stage['created_at'])
                                        {{ \Carbon\Carbon::parse($stage['created_at'])->format('H:i:s') }}
                                    @endif
                                </p>
                            </div>
                        </div>

                        {{-- Error message --}}
                        @if ($status === 'failed' && !empty($stage['error_message']))
                            <div class="mt-3 rounded bg-red-100 px-3 py-2">
                                <p class="text-xs text-red-800">
                                    <strong>Fehler:</strong> {{ $stage['error_message'] }}
                                </p>
                            </div>
                        @endif

                        {{-- Retry count --}}
                        @if (!empty($stage['retry_count']) && $stage['retry_count'] > 0)
                            <p class="mt-2 text-xs text-gray-600">
                                <strong>Versuche:</strong> {{ $stage['retry_count'] }}
                            </p>
                        @endif
                    </div>
                </div>
            @endforeach
        </div>
    @endif
</div>
