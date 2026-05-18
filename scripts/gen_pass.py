import secrets
import string


def gen_pass(length=32):
    alpha = string.ascii_letters + string.digits
    # ensure at least one upper, lower, digit
    while True:
        p = "".join(secrets.choice(alpha) for _ in range(length))
        if any(c.isupper() for c in p) and any(c.islower() for c in p) and any(c.isdigit() for c in p):
            return p


print("DB_PASS=" + gen_pass(32))
print("ADMIN_PASS=" + gen_pass(24))
print("MINIO_ACCESS=" + gen_pass(20))
