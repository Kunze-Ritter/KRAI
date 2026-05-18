# JWT Authentication Implementation

## System Overview

### Authentication Flow
1. **Login**: Admin credentials → JWT token generation
2. **Token Storage**: Secure storage (HttpOnly cookies or local storage)
3. **Authorization**: JWT middleware validates tokens for protected endpoints
4. **Token Refresh**: Automatic refresh before expiry
5. **Logout**: Token invalidation

### Security Features
- JWT with RS256 signature (asymmetric encryption)
- Token expiry (1 hour)
- Refresh tokens (30 days)
- Token blacklisting for logout
- Role-based access control
- Session tracking

### Files to Create
- `backend/models/user.py` - User data models
- `backend/services/auth_service.py` - Authentication logic
- `backend/middleware/auth_middleware.py` - JWT validation
- `backend/api/auth_api.py` - Login/logout endpoints
- `backend/config/auth_config.py` - JWT configuration

### Environment Variables
- `JWT_SECRET_KEY` - RSA private key for signing
- `JWT_PUBLIC_KEY` - RSA public key for validation
- `JWT_ALGORITHM` - RS256
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - 60
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS` - 30
