from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.utils.translation import gettext_lazy as _

class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that handles token validation properly.
    """
    
    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except (InvalidToken, TokenError) as e:
            raise InvalidToken(_('Invalid or expired token'))
        except Exception as e:
            raise InvalidToken(_('Authentication failed'))

class CookieJWTAuthentication(JWTAuthentication):
    """
    JWT authentication that reads token from cookies instead of headers.
    """
    
    def authenticate(self, request):
        raw_token = request.COOKIES.get('access_token')
        if raw_token is None:
            return None
        
        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token