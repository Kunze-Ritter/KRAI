<?php

use Illuminate\Database\Seeder;
use App\Models\User;
use Illuminate\Support\Facades\Hash;

class AdminUserSeeder extends Seeder
{
    /**
     * Run the database seeds.
     */
    public function run(): void
    {
        // Delete existing admin users to avoid duplicates
        User::where('email', 'admin@krai.local')->delete();
        User::where('email', 'test@example.com')->delete();

        // Create new admin user
        User::create([
            'name' => 'KRAI Administrator',
            'email' => 'admin@krai.local',
            'email_verified_at' => now(),
            'password' => Hash::make('admin123'),
            'remember_token' => \Illuminate\Support\Str::random(10),
        ]);

        $this->command->info('Admin user created successfully!');
        $this->command->info('Email: admin@krai.local');
        $this->command->info('Password: admin123');
    }
}
