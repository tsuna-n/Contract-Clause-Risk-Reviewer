from authlib.integrations.starlette_client import OAuth

from auth.config import auth_settings

oauth = OAuth()
oauth.register(
    name="google",
    client_id=auth_settings.google_oauth_api,
    client_secret=auth_settings.google_key_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
