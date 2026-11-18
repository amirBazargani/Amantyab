from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.middleware import RequestLogMiddleware

User = get_user_model()


class RequestLogMiddlewareTests(TestCase):
    """Tests for RequestLogMiddleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="loguser",
            email="loguser@example.com",
            phone="09121112233",
            password="password123",
        )

    def test_anonymous_request_logged(self):
        middleware = RequestLogMiddleware(lambda req: HttpResponse("OK", status=200))
        request = self.factory.get("/some/path/?page=1")
        request.user = AnonymousUser()

        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            response = middleware(request)
            self.assertEqual(response.status_code, 200)

        output = " ".join(cm.output)
        self.assertIn("GET /some/path/?page=1", output)
        self.assertIn("user=anonymous", output)
        self.assertIn("status=200", output)
        self.assertIn("duration=", output)

    def test_authenticated_request_logged(self):
        middleware = RequestLogMiddleware(lambda req: HttpResponse("OK", status=200))
        request = self.factory.post("/catalog/create/")
        request.user = self.user

        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            response = middleware(request)
            self.assertEqual(response.status_code, 200)

        output = " ".join(cm.output)
        self.assertIn("POST /catalog/create/", output)
        self.assertIn(f"user={self.user.pk}", output)
        self.assertIn("status=200", output)
        self.assertIn("duration=", output)

    def test_exception_in_view_logs_exception_and_raises(self):
        def failing_view(req):
            raise ValueError("Something broke")

        middleware = RequestLogMiddleware(failing_view)
        request = self.factory.get("/broken/")
        request.user = self.user

        with self.assertLogs("amanatyab.core", level="ERROR") as cm:
            with self.assertRaises(ValueError):
                middleware(request)

        output = " ".join(cm.output)
        self.assertIn("GET /broken/", output)
        self.assertIn(f"user={self.user.pk}", output)
        self.assertIn("status=500", output)

    def test_real_client_request_writes_to_log(self):
        with self.assertLogs("amanatyab.core", level="INFO") as cm:
            response = self.client.get(reverse("core:home"))
            self.assertEqual(response.status_code, 200)

        output = " ".join(cm.output)
        self.assertIn("GET /", output)
        self.assertIn("status=200", output)
