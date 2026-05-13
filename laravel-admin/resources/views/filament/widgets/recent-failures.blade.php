<x-filament::section>
    <x-slot name="heading">
        Recent Pipeline Failures
    </x-slot>

        @if ($recentErrors->isEmpty())
            <div class="flex flex-col items-center justify-center py-12 text-center">
                <x-filament::icon
                    icon="heroicon-o-check-circle"
                    class="h-12 w-12 text-success-500 dark:text-success-400 mb-4"
                />
                <p class="text-sm text-gray-500 dark:text-gray-400">
                    No active errors
                </p>
            </div>
        @else
            <div class="relative">
                <div wire:loading.delay class="absolute inset-0 bg-white/50 dark:bg-gray-900/50 z-10 flex items-center justify-center">
                    <x-filament::loading-indicator class="h-8 w-8" />
                </div>

                <div class="overflow-x-auto">
                    <table class="w-full text-sm divide-y divide-gray-200 dark:divide-gray-700">
                        <thead class="bg-gray-50 dark:bg-gray-800">
                            <tr>
                                <th class="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Error ID
                                </th>
                                <th class="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Document
                                </th>
                                <th class="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Stage
                                </th>
                                <th class="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Error Type
                                </th>
                                <th class="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Status
                                </th>
                                <th class="px-3 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Created
                                </th>
                                <th class="px-3 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody class="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
                            @foreach ($recentErrors as $error)
                                <tr class="hover:bg-gray-50 dark:hover:bg-gray-800 transition">
                                    <td class="px-3 py-4 whitespace-nowrap">
                                        <div class="flex items-center">
                                            <span
                                                class="text-xs font-mono text-gray-900 dark:text-gray-100 truncate max-w-[120px]"
                                                title="{{ $error->error_id }}"
                                            >
                                                {{ Str::limit($error->error_id, 12, '...') }}
                                            </span>
                                        </div>
                                    </td>
                                    <td class="px-3 py-4 whitespace-nowrap">
                                        @if ($error->document)
                                            <a
                                                href="{{ \App\Filament\Resources\Documents\DocumentResource::getUrl('edit', ['record' => $error->document_id]) }}"
                                                class="text-sm text-primary-600 dark:text-primary-400 hover:underline"
                                            >
                                                {{ Str::limit($error->document->filename, 30) }}
                                            </a>
                                        @else
                                            <span class="text-sm text-gray-500 dark:text-gray-400">—</span>
                                        @endif
                                    </td>
                                    <td class="px-3 py-4 whitespace-nowrap">
                                        <x-filament::badge color="gray">
                                            {{ $error->stage ?? 'Unknown' }}
                                        </x-filament::badge>
                                    </td>
                                    <td class="px-3 py-4 whitespace-nowrap">
                                        <x-filament::badge
                                            :color="match($error->error_type) {
                                                'validation_error' => 'warning',
                                                'processing_error' => 'danger',
                                                'timeout_error' => 'warning',
                                                'network_error' => 'danger',
                                                default => 'gray'
                                            }"
                                        >
                                            {{ Str::headline($error->error_type ?? 'Unknown') }}
                                        </x-filament::badge>
                                    </td>
                                    <td class="px-3 py-4 whitespace-nowrap">
                                        <x-filament::badge
                                            :color="\App\Filament\Resources\Monitoring\PipelineErrorResource::getStatusBadgeColor($error->status)"
                                            :icon="\App\Filament\Resources\Monitoring\PipelineErrorResource::getStatusIcon($error->status)"
                                        >
                                            {{ Str::headline($error->status) }}
                                        </x-filament::badge>
                                    </td>
                                    <td class="px-3 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                        {{ $error->created_at->diffForHumans() }}
                                    </td>
                                    <td class="px-3 py-4 whitespace-nowrap text-right text-sm font-medium">
                                        <div class="flex items-center justify-end gap-2">
                                            @if ($error->status !== 'resolved')
                                                <x-filament::button
                                                    wire:click="retryError('{{ $error->error_id }}')"
                                                    size="xs"
                                                    color="warning"
                                                    icon="heroicon-o-arrow-path"
                                                >
                                                    Retry
                                                </x-filament::button>
                                            @endif

                                            <x-filament::button
                                                tag="a"
                                                href="{{ $this->getErrorUrl($error) }}"
                                                size="xs"
                                                color="gray"
                                                icon="heroicon-o-eye"
                                            >
                                                View
                                            </x-filament::button>

                                            <x-filament::button
                                                size="xs"
                                                color="gray"
                                                icon="heroicon-o-clipboard"
                                                x-data
                                                x-on:click="
                                                    navigator.clipboard.writeText('{{ $error->error_id }}');
                                                    $tooltip('Copied!', { timeout: 2000 });
                                                "
                                            >
                                                Copy ID
                                            </x-filament::button>
                                        </div>
                                    </td>
                                </tr>
                            @endforeach
                        </tbody>
                    </table>
                </div>
            </div>
        @endif
    </x-filament::section>
