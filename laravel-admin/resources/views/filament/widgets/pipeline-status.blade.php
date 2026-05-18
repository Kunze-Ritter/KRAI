<x-filament::section>
    <x-slot name="heading">
        Pipeline Status
    </x-slot>

        @php
            $data = $this->getPipelineData();
            $success = $data['success'] ?? false;
            $pipelineMetrics = $data['pipeline_metrics'] ?? [];
            $stageMetrics = $data['stage_metrics'] ?? [];
            $hardwareStatus = $data['hardware_status'] ?? [];
        @endphp

        @if(!$success)
            <div class="text-center py-8">
                <x-filament::icon
                    icon="heroicon-o-exclamation-triangle"
                    class="h-12 w-12 text-danger-500 mx-auto mb-4"
                />
                <p class="text-danger-600 font-medium text-lg mb-2">Unable to fetch pipeline data</p>

                @php
                    $errorType = $data['error_type'] ?? 'unknown';
                    $configUrl = $data['config_url'] ?? 'Not configured';
                @endphp

                {{-- User-friendly error message based on type --}}
                <div class="bg-danger-50 dark:bg-danger-900/20 rounded-lg p-4 mb-4 max-w-2xl mx-auto">
                    @if($errorType === 'dns_failure')
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">DNS Resolution Failed</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            The backend service hostname cannot be resolved. Ensure the <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">krai-engine</code> service is running and on the same Docker network.
                        </p>
                    @elseif($errorType === 'connection_refused')
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">Connection Refused</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            The backend service is not accepting connections. Check if the <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">krai-engine</code> container is running: <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">docker ps | grep krai-engine</code>
                        </p>
                    @elseif($errorType === 'timeout')
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">Connection Timeout</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            The backend service is not responding within the timeout period. Check service health and network latency.
                        </p>
                    @elseif($errorType === 'endpoint_not_found')
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">Endpoint Not Found (HTTP 404)</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            The monitoring endpoint <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">/api/v1/monitoring/pipeline</code> does not exist. Verify the backend API version and endpoint registration.
                        </p>
                    @elseif($errorType === 'authentication_error')
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">Authentication Error</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            Invalid or missing JWT token. Check <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">KRAI_ENGINE_SERVICE_JWT</code> in <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">.env</code>.
                        </p>
                    @elseif($errorType === 'server_error')
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">Backend Server Error (HTTP 500)</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            The backend encountered an internal error. Check backend logs: <code class="bg-danger-100 dark:bg-danger-800 px-1 rounded">docker logs krai-engine-prod</code>
                        </p>
                    @else
                        <p class="text-sm text-danger-700 dark:text-danger-300 font-semibold">Unknown Error</p>
                        <p class="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            An unexpected error occurred. See details below.
                        </p>
                    @endif
                </div>

                {{-- Technical details --}}
                <details class="text-left max-w-2xl mx-auto">
                    <summary class="text-sm text-gray-600 dark:text-gray-400 cursor-pointer hover:text-gray-800 dark:hover:text-gray-200">
                        Technical Details
                    </summary>
                    <div class="mt-2 bg-gray-100 dark:bg-gray-800 rounded p-3 text-xs font-mono">
                        <p><strong>Configured URL:</strong> {{ $configUrl }}</p>
                        <p><strong>Error Type:</strong> {{ $errorType }}</p>
                        <p class="mt-2"><strong>Raw Error:</strong></p>
                        <pre class="whitespace-pre-wrap break-words">{{ $data['error'] ?? 'No error message' }}</pre>
                    </div>
                </details>

                {{-- Retry button --}}
                <div class="mt-4">
                    <x-filament::button
                        wire:click="$refresh"
                        color="gray"
                        size="sm"
                    >
                        Retry
                    </x-filament::button>
                </div>
            </div>
        @else
            {{-- Pipeline Metrics --}}
            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-gray-600 dark:text-gray-400">Success Rate</p>
                            <p class="text-2xl font-bold text-success-600">
                                {{ number_format($pipelineMetrics['success_rate'] ?? 0, 1) }}%
                            </p>
                        </div>
                        <x-filament::icon
                            icon="heroicon-o-check-circle"
                            class="h-8 w-8 text-success-500"
                        />
                    </div>
                </div>

                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-gray-600 dark:text-gray-400">Throughput (docs/hr)</p>
                            <p class="text-2xl font-bold text-info-600">
                                {{ number_format($pipelineMetrics['current_throughput_docs_per_hour'] ?? 0) }}
                            </p>
                        </div>
                        <x-filament::icon
                            icon="heroicon-o-arrow-trending-up"
                            class="h-8 w-8 text-info-500"
                        />
                    </div>
                </div>

                <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-4">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-sm text-gray-600 dark:text-gray-400">Avg Processing Time (s)</p>
                            <p class="text-2xl font-bold text-warning-600">
                                {{ number_format($pipelineMetrics['avg_processing_time_seconds'] ?? 0, 1) }}s
                            </p>
                        </div>
                        <x-filament::icon
                            icon="heroicon-o-clock"
                            class="h-8 w-8 text-warning-500"
                        />
                    </div>
                </div>
            </div>

            {{-- Stage Metrics --}}
            @if(!empty($stageMetrics))
                <div class="mb-6">
                    <h3 class="text-lg font-semibold mb-3">Pipeline Stages</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full text-sm">
                            <thead class="bg-gray-50 dark:bg-gray-800">
                                <tr>
                                    <th class="px-4 py-2 text-left">Stage</th>
                                    <th class="px-4 py-2 text-left">Status</th>
                                    <th class="px-4 py-2 text-right">Pending</th>
                                    <th class="px-4 py-2 text-right">Processing</th>
                                    <th class="px-4 py-2 text-right">Completed</th>
                                    <th class="px-4 py-2 text-right">Failed</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-200 dark:divide-gray-700">
                                @foreach($stageMetrics as $stage)
                                    <tr>
                                        <td class="px-4 py-3 font-medium">{{ $stage['stage_name'] ?? 'Unknown' }}</td>
                                        <td class="px-4 py-3">
                                            @php
                                                $status = ($stage['is_active'] ?? false) ? 'processing' : 'healthy';
                                                $badgeColor = match($status) {
                                                    'healthy' => 'success',
                                                    'processing' => 'warning',
                                                    'failed' => 'danger',
                                                    default => 'gray',
                                                };
                                            @endphp
                                            <x-filament::badge :color="$badgeColor">
                                                {{ ucfirst($status) }}
                                            </x-filament::badge>
                                        </td>
                                        <td class="px-4 py-3 text-right">{{ number_format($stage['pending_count'] ?? 0) }}</td>
                                        <td class="px-4 py-3 text-right">{{ number_format($stage['processing_count'] ?? 0) }}</td>
                                        <td class="px-4 py-3 text-right text-success-600">{{ number_format($stage['completed_count'] ?? 0) }}</td>
                                        <td class="px-4 py-3 text-right text-danger-600">{{ number_format($stage['failed_count'] ?? 0) }}</td>
                                    </tr>
                                @endforeach
                            </tbody>
                        </table>
                    </div>
                </div>
            @endif

            {{-- Hardware Status --}}
            @if(!empty($hardwareStatus))
                <div>
                    <h3 class="text-lg font-semibold mb-3">Hardware Status</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        @if(isset($hardwareStatus['cpu_percent']))
                            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                <p class="text-xs text-gray-600 dark:text-gray-400">CPU Usage</p>
                                <p class="text-lg font-bold">{{ number_format($hardwareStatus['cpu_percent'], 1) }}%</p>
                            </div>
                        @endif
                        @if(isset($hardwareStatus['ram_percent']))
                            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                <p class="text-xs text-gray-600 dark:text-gray-400">RAM Usage</p>
                                <p class="text-lg font-bold">{{ number_format($hardwareStatus['ram_percent'], 1) }}%</p>
                            </div>
                        @endif
                        @if(isset($hardwareStatus['ram_available_gb']))
                            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                <p class="text-xs text-gray-600 dark:text-gray-400">RAM Available</p>
                                <p class="text-lg font-bold">{{ number_format($hardwareStatus['ram_available_gb'], 1) }} GB</p>
                            </div>
                        @endif
                        @if(isset($hardwareStatus['gpu_available']))
                            <div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                                <p class="text-xs text-gray-600 dark:text-gray-400">GPU Available</p>
                                <p class="text-lg font-bold">{{ $hardwareStatus['gpu_available'] ? 'Yes' : 'No' }}</p>
                                @if(isset($hardwareStatus['gpu_percent']))
                                    <p class="text-xs text-gray-500 mt-1">Usage: {{ number_format($hardwareStatus['gpu_percent'], 1) }}%</p>
                                @endif
                                @if(isset($hardwareStatus['gpu_memory_used_gb']) && isset($hardwareStatus['gpu_memory_total_gb']))
                                    <p class="text-xs text-gray-500 mt-1">Memory: {{ number_format($hardwareStatus['gpu_memory_used_gb'], 1) }} / {{ number_format($hardwareStatus['gpu_memory_total_gb'], 1) }} GB</p>
                                @endif
                            </div>
                        @endif
                    </div>
                </div>
            @endif
        @endif
    </x-filament::section>
