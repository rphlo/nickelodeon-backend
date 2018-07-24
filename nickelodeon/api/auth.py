from django.utils import timezone
from knox.auth import TokenAuthentication
from knox.settings import knox_settings


class TokenAuthSupportQueryString(TokenAuthentication):
    """
    Extend the TokenAuthentication class to support querystring authentication
    in the form of "http://www.example.com/?auth_token=<token_key>" and auto
    renewal of the token expiracy.
    """
    def authenticate(self, request):
        # Check if 'auth_token' is in the request query params.
        # Give precedence to 'Authorization' header.
        if 'auth_token' in request.query_params and \
                        'HTTP_AUTHORIZATION' not in request.META:
            return self.authenticate_credentials(
                request.query_params.get('auth_token').encode("utf-8")
            )
        return super().authenticate(request)

    def authenticate_credentials(self, token):
        result = super().authenticate_credentials(token)
        if result:
            user, auth_token = result
            current_expiry = auth_token.expires
            new_expiry = timezone.now() + knox_settings.TOKEN_TTL
            auth_token.expires = new_expiry
            # Update once per second max
            if (new_expiry - current_expiry).total_seconds() > 1:
                auth_token.save(update_fields=('expires',))
        return result
