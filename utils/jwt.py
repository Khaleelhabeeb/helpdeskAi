from services.supabase_auth import verify_supabase_token


get_current_user = verify_supabase_token


def verify_token(token: str):
    raise RuntimeError("Hand-rolled JWT verification has been replaced by Supabase Auth")
