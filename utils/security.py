def hash_password(password: str):
    raise RuntimeError("Password hashing is managed by Supabase Auth")


def verify_password(plain_password, hashed_password):
    raise RuntimeError("Password verification is managed by Supabase Auth")
