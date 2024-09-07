from typing import cast

from django.http import HttpRequest, HttpResponse
from rest_framework_simplejwt.tokens import AccessToken, Token


class JwtAuthentication:
    # __init__() is called only once, when the web server starts.
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        cookies = request.COOKIES

        if "access" in cookies:
            if request.method == "GET":
                # A 401 error is returned for safe methods when the token
                # expires, even though authentication is not required. To avoid
                # this, the HTTP_AUTHORIZATION header is not set. This is safe
                # because authentication is handled in the view if necessary.

                try:
                    AccessToken(cast(Token, cookies["access"]))
                except Exception:
                    # token is invalid or expired
                    return self.get_response(request)

            request.META["HTTP_AUTHORIZATION"] = ("Bearer %s"
                                                  % cookies["access"])

        return self.get_response(request)
