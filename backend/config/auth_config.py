"""
JWT Authentication Configuration
Handles JWT signing, validation and token management
"""

import base64
import logging
import os
from datetime import UTC, timedelta
from typing import Any

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

# Setup logging
logger = logging.getLogger("krai.auth.config")


class JWTConfig:
    """JWT Configuration class"""

    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._algorithm = "RS256"
        self._access_token_expire_minutes = 60  # 1 hour
        self._refresh_token_expire_days = 30  # 30 days
        self._load_keys()

    def _load_keys(self):
        """Load JWT keys from environment or generate new ones"""
        private_key_env = os.getenv("JWT_PRIVATE_KEY", "")
        public_key_env = os.getenv("JWT_PUBLIC_KEY", "")

        if private_key_env and public_key_env:
            # Load keys from environment
            try:
                # Handle different formats (with/without headers)
                if "BEGIN PRIVATE KEY" in private_key_env:
                    self._private_key = private_key_env.strip().encode()
                else:
                    # Assume base64 encoded PEM without headers
                    pem_content = f"""-----BEGIN PRIVATE KEY-----
{private_key_env}
-----END PRIVATE KEY-----"""
                    self._private_key = pem_content.encode()

                if "BEGIN PUBLIC KEY" in public_key_env:
                    self._public_key = public_key_env.strip().encode()
                else:
                    # Assume base64 encoded PEM without headers
                    pem_content = f"""-----BEGIN PUBLIC KEY-----
{public_key_env}
-----END PUBLIC KEY-----"""
                    self._public_key = pem_content.encode()

                logger.info("✅ JWT keys loaded from environment variables")

            except Exception as e:
                logger.error(f"❌ Failed to load JWT keys from environment: {e}")
                self._generate_keys()
        else:
            # Generate new keys
            logger.info("🔑 Generating new JWT key pair...")
            self._generate_keys()

    def _generate_keys(self):
        """Generate new RSA key pair"""
        try:
            # Generate 2048-bit RSA key
            private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())

            # Serialize private key
            self._private_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            # Serialize public key
            public_key = private_key.public_key()
            self._public_key = public_key.public_bytes(
                encoding=serialization.Encoding.PEM, format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            # Store in environment for future use
            private_key_b64 = base64.b64encode(self._private_key).decode("utf-8")
            public_key_b64 = base64.b64encode(self._public_key).decode("utf-8")

            # Log generated keys (WARNING: Don't do this in production!)
            logger.warning("🔑 Generated new JWT keys. Add these to your .env file:")
            logger.warning(f'JWT_PRIVATE_KEY="{private_key_b64}"')
            logger.warning(f'JWT_PUBLIC_KEY="{public_key_b64}"')

            # In development, save to .env file
            if os.getenv("ENVIRONMENT", "development").lower() == "development":
                self._save_keys_to_env_file(private_key_b64, public_key_b64)

        except Exception as e:
            logger.error(f"❌ Failed to generate JWT keys: {e}")
            raise

    def _save_keys_to_env_file(self, private_key_b64: str, public_key_b64: str):
        """Save generated keys to .env file for development"""
        try:
            env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".env.auth")
            with open(env_file, "w") as f:
                f.write("# JWT Keys - Generated automatically\n")
                f.write("# Keep these secret and add to your main .env file\n")
                f.write(f'JWT_PRIVATE_KEY="{private_key_b64}"\n')
                f.write(f'JWT_PUBLIC_KEY="{public_key_b64}"\n')
                f.write(f'JWT_ALGORITHM="{self._algorithm}"\n')
            logger.info(f"✅ JWT keys saved to {env_file}")
        except Exception as e:
            logger.warning(f"⚠️ Could not save JWT keys to .env file: {e}")

    @property
    def private_key(self) -> bytes:
        """Get private key for signing"""
        return self._private_key

    @property
    def public_key(self) -> bytes:
        """Get public key for validation"""
        return self._public_key

    @property
    def algorithm(self) -> str:
        """Get signing algorithm"""
        return self._algorithm

    @property
    def access_token_expire_minutes(self) -> int:
        """Get access token expiry in minutes"""
        return self._access_token_expire_minutes

    @property
    def refresh_token_expire_days(self) -> int:
        """Get refresh token expiry in days"""
        return self._refresh_token_expire_days

    @property
    def access_token_expire(self) -> timedelta:
        """Get access token expiry as timedelta"""
        return timedelta(minutes=self._access_token_expire_minutes)

    @property
    def refresh_token_expire(self) -> timedelta:
        """Get refresh token expiry as timedelta"""
        return timedelta(days=self._refresh_token_expire_days)


class JWTValidator:
    """JWT Token validation and error handling"""

    def __init__(self, jwt_config: JWTConfig):
        self.config = jwt_config

    def decode(self, token: str, key: bytes, algorithms=None, options=None) -> dict[str, Any] | None:
        """Compatibility wrapper used by auth_middleware.

        Delegates to PyJWT.decode with the provided key and options.
        """
        return jwt.decode(
            token,
            key,
            algorithms=algorithms or [self.config.algorithm],
            options=options or {},
        )

    def decode_token(self, token: str) -> dict[str, Any] | None:
        """
        Decode and validate JWT token
        Returns payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(token, self.config.public_key, algorithms=[self.config.algorithm])
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None

        except Exception as e:
            logger.error(f"JWT decode error: {e}")
            return None

    def encode_token(self, payload: dict[str, Any], token_type: str = "access") -> str:
        """
        Encode payload into JWT token
        """
        try:
            # Set expiry based on token type
            from datetime import datetime

            now = datetime.now(UTC)

            if token_type == "access":
                payload["exp"] = now + self.config.access_token_expire
            elif token_type == "refresh":
                payload["exp"] = now + self.config.refresh_token_expire
            else:
                payload["exp"] = now + self.config.access_token_expire

            payload["iat"] = now  # issued at
            payload["jti"] = payload.get("jti")  # token ID for blacklisting

            token = jwt.encode(payload, self.config.private_key, algorithm=self.config.algorithm)

            return token

        except Exception as e:
            logger.error(f"JWT encode error: {e}")
            raise


# Global JWT configuration instance
jwt_config = JWTConfig()
jwt_validator = JWTValidator(jwt_config)

# JWT Configuration constants
JWT_ALGORITHM = jwt_config.algorithm
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = jwt_config.access_token_expire_minutes
JWT_REFRESH_TOKEN_EXPIRE_DAYS = jwt_config.refresh_token_expire_days

# Token type constants
ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"

# JWT Claim constants
CLAIM_USER_ID = "sub"  # subject
CLAIM_EMAIL = "email"
CLAIM_ROLE = "role"
CLAIM_TOKEN_TYPE = "token_type"
CLAIM_JTI = "jti"  # JWT ID for blacklisting
CLAIM_IAT = "iat"  # issued at
CLAIM_EXP = "exp"  # expiry

# Required JWT claims
REQUIRED_CLAIMS = [CLAIM_USER_ID, CLAIM_EMAIL, CLAIM_ROLE, CLAIM_TOKEN_TYPE, CLAIM_JTI]


def get_jwt_config() -> JWTConfig:
    """Get global JWT configuration instance"""
    return jwt_config


def get_jwt_validator() -> JWTValidator:
    """Get global JWT validator instance"""
    return jwt_validator


# Test JWT functionality
def test_jwt_functionality():
    """Test JWT functionality (for development only)"""
    try:
        import json

        from models.user import generate_jti

        # Test payload
        test_payload = {
            CLAIM_USER_ID: "test-user-123",
            CLAIM_EMAIL: "test@example.com",
            CLAIM_ROLE: "admin",
            CLAIM_TOKEN_TYPE: ACCESS_TOKEN,
            CLAIM_JTI: generate_jti(),
        }

        # Encode
        token = jwt_validator.encode_token(test_payload, ACCESS_TOKEN)
        print(f"Generated token: {token[:50]}...")

        # Decode
        decoded = jwt_validator.decode_token(token)
        if decoded:
            print("✅ JWT functionality test passed")
            print(f"Decoded payload: {json.dumps(decoded, indent=2, default=str)}")
        else:
            print("❌ JWT functionality test failed")

    except Exception as e:
        print(f"❌ JWT test error: {e}")


if __name__ == "__main__":
    # Run test if called directly
    test_jwt_functionality()
