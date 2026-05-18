"""Root conftest for all backend tests."""

import os

# Set database URL for integration tests
if not os.getenv("POSTGRES_URL") and not os.getenv("DATABASE_CONNECTION_URL"):
    os.environ["POSTGRES_URL"] = "postgresql://krai_user:Krai_Secure_Pass123!@localhost:5432/krai"
