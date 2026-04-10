from rest_framework.throttling import SimpleRateThrottle

class LoginThrottle(SimpleRateThrottle):
    scope = 'login'
    
    def get_cache_key(self, request, view):
        return self.get_ident(request)

class RegisterThrottle(SimpleRateThrottle):
    scope = 'register'
    
    def get_cache_key(self, request, view):
        return self.get_ident(request)

class OTPThrottle(SimpleRateThrottle):
    scope = 'otp'
    
    def get_cache_key(self, request, view):
        return self.get_ident(request)

class ForgotPasswordThrottle(SimpleRateThrottle):
    scope = 'forgot_password'
    
    def get_cache_key(self, request, view):
        email = request.data.get('email', '')
        return f"{self.get_ident(request)}_{email}"