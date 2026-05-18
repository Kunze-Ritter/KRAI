# KRAI Authentication System

This document provides an overview of the KRAI authentication system, including setup, configuration, and usage.

## Table of Contents

1. [Features](#features)
2. [Setup](#setup)
3. [API Endpoints](#api-endpoints)
4. [Authentication Flow](#authentication-flow)
5. [Role-Based Access Control](#role-based-access-control)
6. [Security Considerations](#security-considerations)
7. [Troubleshooting](#troubleshooting)

## Features

- JWT-based authentication with access and refresh tokens
- Role-based access control (RBAC)
- Token blacklisting for secure logout
- Password hashing with bcrypt
- Rate limiting for login attempts
- Account lockout after failed attempts
- Email verification (optional)
- Password reset functionality
- Secure password requirements

## Setup

### Prerequisites

- Python 3.8+
- PostgreSQL database
- Redis (for token blacklisting)

### Installation

1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```env
   # JWT Configuration
   SECRET_KEY=your-secret-key-here
   JWT_ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours
   REFRESH_TOKEN_EXPIRE_DAYS=7

   # Database
   DATABASE_URL=postgresql://user:password@localhost:5432/krai_db

   # Redis (for token blacklisting)
   REDIS_URL=redis://localhost:6379/0

   # Email (for password reset)
   SMTP_SERVER=smtp.example.com
   SMTP_PORT=587
   SMTP_USER=your-email@example.com
   SMTP_PASSWORD=your-email-password
   ```

3. Run database migrations:
   ```bash
   alembic upgrade head
   ```

4. Create an admin user:
   ```bash
   python -m backend.scripts.create_admin_user
   ```

## API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register a new user
- `POST /api/v1/auth/login` - Login with email/username and password
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/logout` - Logout (invalidate token)
- `POST /api/v1/auth/forgot-password` - Request password reset
- `POST /api/v1/auth/reset-password` - Reset password with token

### User Management (Admin)

- `GET /api/v1/users` - List all users (admin only)
- `GET /api/v1/users/{user_id}` - Get user by ID
- `POST /api/v1/users` - Create a new user (admin only)
- `PUT /api/v1/users/{user_id}` - Update user
- `DELETE /api/v1/users/{user_id}` - Delete user (admin only)

### User Profile

- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update current user profile
- `PUT /api/v1/users/me/password` - Change password

## Authentication Flow

1. **Registration**
   - User submits registration form with email, username, and password
   - System creates a new user with hashed password
   - Verification email is sent (if enabled)

2. **Login**
   - User submits login credentials
   - System validates credentials and returns access/refresh tokens
   - Access token is short-lived, refresh token is long-lived

3. **Accessing Protected Routes**
   - Client includes access token in `Authorization: Bearer <token>` header
   - Middleware validates token and checks permissions

4. **Token Refresh**
   - When access token expires, client uses refresh token to get new tokens
   - Refresh token is rotated on each use

5. **Logout**
   - Access token is blacklisted
   - Refresh token is invalidated

## Role-Based Access Control

The system supports the following roles:

- `admin`: Full access to all resources
- `editor`: Can create and edit content
- `viewer`: Read-only access
- `user`: Basic authenticated user with limited access

## Security Considerations

- Always use HTTPS in production
- Store secrets in environment variables, not in code
- Use strong password policies
- Implement rate limiting on authentication endpoints
- Set secure, HTTP-only cookies for tokens
- Use CSRF protection for forms
- Regularly rotate secrets and keys
- Monitor and log authentication attempts

## Troubleshooting

### Common Issues

1. **Invalid Credentials**
   - Verify the email/username and password are correct
   - Check if the account is locked after too many failed attempts

2. **Token Expired**
   - Use the refresh token to get a new access token
   - If refresh token is expired, user must log in again

3. **Permission Denied**
   - Verify the user has the required role/permission
   - Check if the account is active and verified

### Logs

Check the application logs for detailed error messages:

```bash
tail -f app.log
```

### Support

For additional help, contact the development team or create an issue in the repository.
