"""Generate fresh JWT RSA key pair for .env configuration."""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main():
    """Generate and print Base64-encoded DER keys for JWT authentication."""
    print("Generating fresh RSA 2048-bit key pair...")

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    priv_der = key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    priv_b64 = base64.b64encode(priv_der).decode()
    pub_b64 = base64.b64encode(pub_der).decode()

    print("\n" + "=" * 80)
    print("Copy these lines into your .env file:")
    print("=" * 80)
    print(f"JWT_PRIVATE_KEY={priv_b64}")
    print(f"JWT_PUBLIC_KEY={pub_b64}")
    print("=" * 80)
    print(f"\nPrivate key length: {len(priv_b64)} chars")
    print(f"Public key length: {len(pub_b64)} chars")
    print("\nDone! Remember to restart krai-engine after updating .env")


if __name__ == "__main__":
    main()
