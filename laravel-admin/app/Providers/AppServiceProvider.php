<?php

namespace App\Providers;

use App\Services\FirecrawlService;
use App\Services\KraiEngineService;
use App\Services\MonitoringService;
use Illuminate\Support\Facades\App;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        if (
            App::environment(['local', 'testing']) &&
            (bool) config('telescope.enabled') &&
            class_exists(\Laravel\Telescope\TelescopeApplicationServiceProvider::class)
        ) {
            $this->app->register('App\Providers\TelescopeServiceProvider');
        }

        $this->app->singleton(KraiEngineService::class, function ($app) {
            return new KraiEngineService(
                config('krai.engine_url'),
                config('krai.service_jwt'),
                defaultTimeout: config('krai.default_timeout', 120),
                queryTimeout: config('krai.query_timeout', 60),
                uploadTimeout: config('krai.upload_timeout', 600),
            );
        });

        $this->app->singleton(MonitoringService::class, function ($app) {
            return new MonitoringService(
                config('krai.engine_url'),
                config('krai.service_jwt')
            );
        });

        $this->app->singleton(\App\Services\ImageService::class, function ($app) {
            return new \App\Services\ImageService(
                config('krai.engine_url'),
                config('krai.service_jwt')
            );
        });

        $this->app->singleton(FirecrawlService::class, function ($app) {
            return new FirecrawlService;
        });
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        config([
            'livewire.temporary_file_upload.rules' => [
                'required',
                'file',
                'mimetypes:application/pdf',
                'max:102400',
            ],
            'livewire.temporary_file_upload.max_upload_time' => 30,
        ]);
    }
}
