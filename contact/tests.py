import unittest
from unittest.mock import patch, MagicMock
import json
import pytest

from django.http import HttpRequest
from django.urls import reverse
from bs4 import BeautifulSoup

from contact import views
from contact.models import Contact, NewsLetter


# ============================================================
# 🔹 TESTS UNITAIRES (Isolation avec Mock)
# ============================================================

class TestContactViewUnit(unittest.TestCase):
    """
    Vérifie la logique interne des vues contact
    sans interaction réelle avec la base de données.
    """

    def setUp(self):
        self.request = MagicMock(spec=HttpRequest)
        self.request.method = "POST"
        self.request.content_type = "application/json"

    # ---------------------------
    # PAGE CONTACT (GET)
    # ---------------------------

    @patch("contact.views.render")
    def test_contact_page_render(self, mock_render):
        mock_render.return_value = MagicMock()

        views.contact(self.request)

        mock_render.assert_called_once_with(
            self.request,
            "contact-us.html",
            {}
        )

    # ---------------------------
    # POST CONTACT
    # ---------------------------

    @patch("contact.views.models.Contact")
    def test_post_contact_success(self, mock_contact_model):
        payload = {
            "email": "user@test.com",
            "nom": "Test User",
            "sujet": "Sujet",
            "messages": "Message valide"
        }

        self.request.body = json.dumps(payload).encode("utf-8")

        mock_instance = MagicMock()
        mock_contact_model.return_value = mock_instance

        response = views.post_contact(self.request)
        data = json.loads(response.content.decode())

        self.assertTrue(data["success"])
        self.assertEqual(data["message"], "Merci pour votre message")
        mock_instance.save.assert_called_once()

    @patch("contact.views.models.Contact")
    def test_post_contact_invalid_data(self, mock_contact_model):
        payload = {
            "email": "bad-email",
            "nom": "User",
            "sujet": "Sujet",
            "messages": "Message"
        }

        self.request.body = json.dumps(payload).encode("utf-8")

        response = views.post_contact(self.request)
        data = json.loads(response.content.decode())

        self.assertFalse(data["success"])
        self.assertEqual(
            data["message"],
            "Merci de renseigner correctement les champs"
        )
        self.assertFalse(mock_contact_model.return_value.save.called)

    # ---------------------------
    # POST NEWSLETTER
    # ---------------------------

    @patch("contact.views.models.NewsLetter")
    def test_newsletter_valid_email(self, mock_newsletter_model):
        payload = {"email": "newsletter@test.com"}
        self.request.body = json.dumps(payload).encode("utf-8")

        mock_instance = MagicMock()
        mock_newsletter_model.return_value = mock_instance

        response = views.post_newsletter(self.request)
        data = json.loads(response.content.decode())

        self.assertTrue(data["success"])
        mock_instance.save.assert_not_called()

    @patch("contact.views.models.NewsLetter")
    def test_newsletter_invalid_email(self, mock_newsletter_model):
        payload = {"email": "invalid-email"}
        self.request.body = json.dumps(payload).encode("utf-8")

        response = views.post_newsletter(self.request)
        data = json.loads(response.content.decode())

        self.assertFalse(data["success"])
        self.assertFalse(mock_newsletter_model.return_value.save.called)


 

@pytest.mark.django_db
class TestContactFonctionnel:
    """
    Simulation réelle du comportement utilisateur :
    - Accès à la page
    - Soumission formulaire
    - Vérification base de données
    """

    # ---------------------------
    # PAGE CONTACT
    # ---------------------------

    def test_contact_page_access(self, client):
        response = client.get(reverse("contact"))
        assert response.status_code == 200

    def test_contact_form_elements_exist(self, client):
        response = client.get(reverse("contact"))
        soup = BeautifulSoup(response.content, "html.parser")

        form = soup.find("form", {"id": "contact-form"})
        assert form is not None

        assert soup.find("input", {"v-model": "nom"})
        assert soup.find("input", {"v-model": "email"})
        assert soup.find("textarea", {"v-model": "messages"})
        assert soup.find("button", {"type": "submit"})

    # ---------------------------
    # POST CONTACT
    # ---------------------------

    def test_contact_empty_fields(self, client):
        response = client.post(
            reverse("post_contact"),
            data=json.dumps({
                "email": "",
                "nom": "",
                "sujet": "",
                "messages": ""
            }),
            content_type="application/json"
        )

        assert response.status_code == 200
        assert Contact.objects.count() == 0

    def test_contact_invalid_email(self, client):
        response = client.post(
            reverse("post_contact"),
            data=json.dumps({
                "email": "invalid",
                "nom": "User",
                "sujet": "Sujet",
                "messages": "Message"
            }),
            content_type="application/json"
        )

        assert response.status_code == 200
        assert Contact.objects.count() == 0

    def test_contact_valid_submission(self, client):
        response = client.post(
            reverse("post_contact"),
            data=json.dumps({
                "email": "valid@test.com",
                "nom": "User",
                "sujet": "Sujet",
                "messages": "Bonjour"
            }),
            content_type="application/json"
        )

        assert response.status_code == 200
        assert Contact.objects.count() == 1

    # ---------------------------
    # NEWSLETTER
    # ---------------------------

    def test_newsletter_empty_email(self, client):
        response = client.post(
            reverse("post_newsletter"),
            data=json.dumps({"email": ""}),
            content_type="application/json"
        )

        assert response.status_code == 200
        assert NewsLetter.objects.count() == 0

    def test_newsletter_invalid_email(self, client):
        response = client.post(
            reverse("post_newsletter"),
            data=json.dumps({"email": "bad-email"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        assert NewsLetter.objects.count() == 0

    def test_newsletter_valid_email(self, client):
        response = client.post(
            reverse("post_newsletter"),
            data=json.dumps({"email": "newsletter@test.com"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        # La vue actuelle ne fait pas save()
        assert NewsLetter.objects.count() == 0

    def test_newsletter_duplicate_email(self, client):
        NewsLetter.objects.create(email="duplicate@test.com")

        response = client.post(
            reverse("post_newsletter"),
            data=json.dumps({"email": "duplicate@test.com"}),
            content_type="application/json"
        )

        assert response.status_code == 200
        assert NewsLetter.objects.count() == 1