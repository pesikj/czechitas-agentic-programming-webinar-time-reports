import hashlib
import time

from django.db import connection, transaction
from django.http import HttpResponse

from .models import RateBucket


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response["Referrer-Policy"] = "same-origin"
        if "/password/" in request.path or "/setup-link/" in request.path:
            response["Referrer-Policy"] = "no-referrer"
        if request.user.is_authenticated or "/password/" in request.path:
            response["Cache-Control"] = "no-store, private"
        return response


class SensitiveRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        scope = None
        if request.path == "/imports/" and request.method == "POST":
            scope = "upload"
        elif request.path.startswith("/password/"):
            scope = "password"
        if scope:
            identity = (
                str(request.user.pk)
                if request.user.is_authenticated
                else request.META.get("REMOTE_ADDR", "unknown")
            )
            key = hashlib.sha256((scope + ":" + identity).encode()).hexdigest()
            window = int(time.time()) // 3600
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int(key[:15], 16)])
                bucket, _ = RateBucket.objects.get_or_create(key=key, window=window)
                if bucket.count >= (20 if scope == "upload" else 60):
                    response = HttpResponse("Příliš mnoho pokusů. Zkuste to později.", status=429)
                    response["Retry-After"] = "3600"
                    return response
                bucket.count += 1
                bucket.save(update_fields=["count"])
                RateBucket.objects.filter(key=key, window__lt=window - 24).delete()
        return self.get_response(request)
