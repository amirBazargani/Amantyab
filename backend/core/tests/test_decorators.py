from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core.decorators import verified_required

User = get_user_model()


class VerifiedRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.verified_user = User.objects.create_user(
            username="verified_user",
            email="v@example.com",
            phone="09121111111",
            password="Password123!",
            is_email_verified=True,
        )
        self.unverified_user = User.objects.create_user(
            username="unverified_user",
            email="uv@example.com",
            phone="09122222222",
            password="Password123!",
            is_email_verified=False,
        )

    def dummy_view(self, request):
        return HttpResponse("PROTECTED_SUCCESS")

    def test_anonymous_redirected_to_login(self):
        decorated = verified_required(self.dummy_view)
        request = self.factory.get("/dummy/")
        request.user = AnonymousUser()

        response = decorated(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_unverified_user_redirected_to_profile(self):
        decorated = verified_required(self.dummy_view)
        request = self.factory.get("/dummy/")
        request.user = self.unverified_user

        # Add message support
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, "session", {})
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        response = decorated(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:profile"))

    def test_verified_user_can_access_view(self):
        decorated = verified_required(self.dummy_view)
        request = self.factory.get("/dummy/")
        request.user = self.verified_user

        response = decorated(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "PROTECTED_SUCCESS")
