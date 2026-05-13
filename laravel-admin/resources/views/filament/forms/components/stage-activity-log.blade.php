@php
    $stageTracking = $getState() ?? [];
    $sortedStages = collect($stageTracking)
        ->sortBy('created_at')
        ->values();

    $statusColors = [
        'completed' => 'bg-green-50 border-green-200 hover:border-green-300',
        'processing' => 'bg-blue-50 border-blue-200 hover:border-blue-300',
        'failed' => 'bg-red-50 border-red-200 hover:border-red-300',
        'pending' => 'bg-gray-50 border-gray-200 hover:border-gray-300',
        'queued' => 'bg-yellow-50 border-yellow-200 hover:border-yellow-300',
    ];

    $statusBadgeColors = [
        'completed' => 'bg-green-100 text-green-800',
        'processing' => 'bg-blue-100 text-blue-800',
        'failed' => 'bg-red-100 text-red-800',
        'pending' => 'bg-gray-100 text-gray-800',
        'queued' => 'bg-yellow-100 text-yellow-800',
    ];

    $statusLabels = [
        'completed' => '✓ Abgeschlossen',
        'processing' => '⏳ Wird verarbeitet',
        'failed' => '✗ Fehlgeschlagen',
        'pending' => '◯ Ausstehend',
        'queued' => '◆ In Warteschlange',
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
                    $badgeColorClass = $statusBadgeColors[$status] ?? $statusBadgeColors['pending'];
                    $label = $statusLabels[$status] ?? $statusLabels['pending'];
                @endphp

                <div class="relative flex gap-4">
                    {{-- Timeline line --}}
                    @if ($index < $sortedStages->count() - 1)
                        <div class="absolute left-4 top-10 h-[calc(100%+1rem)] w-0.5 bg-gray-200"></div>
                    @endif

                    {{-- Icon with indicator ring --}}
                    <div class="relative flex flex-shrink-0 items-center justify-center">
                        <div class="flex h-10 w-10 items-center justify-center rounded-full bg-white ring-2 {{ $status === 'failed' ? 'ring-red-300' : 'ring-gray-200' }}">
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

                    {{-- Content with enhanced styling --}}
                    <div class="flex-1 rounded-lg border px-4 py-3 transition-all {{ $colorClass }}">
                        <div class="flex items-start justify-between gap-4">
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2">
                                    <h4 class="font-semibold text-gray-900">
                                        {{ str($stage['stage_name'] ?? 'unknown')->replace('_', ' ')->title() }}
                                    </h4>
                                    <span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium {{ $badgeColorClass }}">
                                        {{ $label }}
                                    </span>
                                </div>
                                @if ($status === 'processing')
                                    <div class="mt-1 flex items-center gap-1">
                                        <div class="h-1 w-1 rounded-full bg-blue-600 animate-pulse"></div>
                                        <p class="text-xs text-blue-600 font-medium">Wird gerade verarbeitet...</p>
                                    </div>
                                @endif
                            </div>
                            <div class="flex-shrink-0 text-right">
                                <p class="text-xs text-gray-600 font-medium">
                                    @if ($stage['created_at'])
                                        {{ \Carbon\Carbon::parse($stage['created_at'])->format('H:i:s') }}
                                    @endif
                                </p>
                            </div>
                        </div>

                        {{-- Error message with enhanced visibility --}}
                        @if ($status === 'failed' && !empty($stage['error_message']))
                            <div class="mt-3 rounded-md bg-gradient-to-r from-red-50 to-red-100 border-l-4 border-red-600 px-4 py-3">
                                <div class="flex items-start gap-2">
                                    <svg class="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd" />
                                    </svg>
                                    <div class="flex-1">
                                        <p class="font-semibold text-red-900 text-sm">Fehler aufgetreten</p>
                                        <p class="text-xs text-red-800 mt-1">{{ $stage['error_message'] }}</p>
                                    </div>
                                </div>
                            </div>
                        @endif

                        {{-- Retry information --}}
                        @if (!empty($stage['retry_count']) && $stage['retry_count'] > 0)
                            <div class="mt-2 flex items-center gap-2 px-2 py-1.5 bg-orange-50 rounded text-xs">
                                <svg class="h-4 w-4 text-orange-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 1119.519 4.287 1 1 0 01-1.788-.876A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1z" clip-rule="evenodd" />
                                </svg>
                                <span class="text-orange-900 font-medium">
                                    {{ $stage['retry_count'] }} {{ $stage['retry_count'] === 1 ? 'Versuch' : 'Versuche' }}
                                </span>
                            </div>
                        @endif
                    </div>
                </div>
            @endforeach
        </div>
    @endif
</div>
