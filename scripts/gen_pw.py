import secrets
import string

a = string.ascii_letters + string.digits


def gen(n):
    while True:
        p = "".join(secrets.choice(a) for _ in range(n))
        if any(c.isupper() for c in p) and any(c.islower() for c in p) and any(c.isdigit() for c in p):
            return p


print(gen(32))
print(gen(24))
print(gen(20))
