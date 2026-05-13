<?php

namespace App\Services;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

/**
 * Centralized JWT token management for backend authentication
 *
 * Handles caching, refresh, and retrieval of service JWT tokens
 * across all Laravel services that communicate with the FastAPI backend.
 */
class TokenService
{
    private string $baseUrl;
    private ?string $serviceJwt;
    private const CACHE_KEY = 'krai.service_jwt.cached';
    private const CACHE_TTL_MINUTES = 55;

    public function __construct(?string $baseUrl = null, ?string $serviceJwt = null)
    {
        $this->baseUrl = rtrim($baseUrl ?? config('krai.engine_url', 'http://krai-engine:8000'), '/');
        $this->serviceJwt = $serviceJwt ?? config('krai.service_jwt');
    }

    /**
     * Get JWT token - returns static token or fetches cached token
     *
     * @return string|null JWT token or null if unavailable
     */
    public function getToken(): ?string
    {
        // Return static token if configured
        if ($this->serviceJwt) {
            return $this->serviceJwt;
        }

        // Return cached token if available
        $cached = Cache::get(self::CACHE_KEY);
        if (is_string($cached) && $cached !== '') {
            return $cached;
        }

        // Attempt to obtain new token via auto-login
        return $this->obtainToken();
    }

    /**
     * Obtain new token via auto-login with admin credentials
     *
     * @return string|null Token or null on failure
     */
    private function obtainToken(): ?string
    {
        $username = config('krai.engine_admin_username', env('KRAI_ENGINE_ADMIN_USERNAME'));
        $password = config('krai.engine_admin_password', env('KRAI_ENGINE_ADMIN_PASSWORD'));

        if (empty($username) || empty($password)) {
            Log::debug('TokenService: No credentials configured for auto-login');
            return null;
        }

        try {
            $response = Http::timeout(10)
                ->acceptJson()
                ->post("{$this->baseUrl}/api/v1/auth/login", [
                    'username' => $username,
                    'password' => $password,
                    'remember_me' => false,
                ]);

            if ($response->successful()) {
                $token = $response->json('data.access_token');

                if (is_string($token) && $token !== '') {
                    Cache::put(self::CACHE_KEY, $token, now()->addMinutes(self::CACHE_TTL_MINUTES));
                    Log::debug('TokenService: Successfully obtained new token');
                    return $token;
                }
            }

            Log::warning('TokenService: Auto-login failed', [
                'status' => $response->status(),
                'error' => $response->json('detail') ?? $response->body(),
            ]);
        } catch (\Throwable $e) {
            Log::warning('TokenService: Auto-login exception', [
                'message' => $e->getMessage(),
            ]);
        }

        return null;
    }

    /**
     * Force refresh of cached token
     *
     * @return string|null New token or null on failure
     */
    public function refreshToken(): ?string
    {
        Cache::forget(self::CACHE_KEY);
        return $this->obtainToken();
    }

    /**
     * Check if credentials are configured
     *
     * @return bool
     */
    public function hasCredentials(): bool
    {
        $username = config('krai.engine_admin_username', env('KRAI_ENGINE_ADMIN_USERNAME'));
        $password = config('krai.engine_admin_password', env('KRAI_ENGINE_ADMIN_PASSWORD'));

        return !empty($username) && !empty($password);
    }

    /**
     * Clear cached token
     */
    public function clearCache(): void
    {
        Cache::forget(self::CACHE_KEY);
    }
}
