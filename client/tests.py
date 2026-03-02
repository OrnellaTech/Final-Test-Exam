import unittest
from unittest.mock import MagicMock, patch
import pytest

from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from website.models import SiteInfo
from customer.models import Commande, Customer
from client.views import (
    profil, commande, commande_detail,
    parametre, invoice_pdf,
    souhait, suivie_commande,
    avis, evaluation
)
from shop.models import (
    CategorieEtablissement,
    CategorieProduit,
    Etablissement,
    Produit,
    Favorite
)

# ============================================================
# 🔹 TESTS UNITAIRES (Logique isolée avec Mock)
# ============================================================

class TestClientViewUnitLogic(unittest.TestCase):

    def setUp(self):
        self.mock_user = MagicMock()
        self.mock_customer = MagicMock()
        self.mock_user.customer = self.mock_customer

        self.request = MagicMock()
        self.request.user = self.mock_user
        self.request.method = "GET"
        self.request.GET = {}

    # ---------------- PROFIL ----------------

    @patch("client.views.render")
    @patch("client.views.Commande")
    def test_profil_returns_last_orders(self, mock_commande, mock_render):
        fake_orders = [MagicMock() for _ in range(8)]
        mock_commande.objects.filter.return_value.order_by.return_value = fake_orders[:5]

        profil(self.request)

        mock_render.assert_called_once()
        context = mock_render.call_args[0][2]

        self.assertEqual(len(context["dernieres_commandes"]), 5)
        self.assertEqual(context["customer"], self.mock_customer)

    @patch("client.views.redirect")
    def test_profil_without_customer_redirect(self, mock_redirect):
        del self.mock_user.customer
        profil(self.request)
        mock_redirect.assert_called_once_with("index")

    # ---------------- PARAMETRE ----------------

    @patch("client.views.redirect")
    def test_parametre_post_updates_user(self, mock_redirect):
        self.request.method = "POST"
        self.request.POST = {
            "first_name": "Test",
            "last_name": "User",
            "contact": "01010101",
            "address": "Test Street",
            "city": ""
        }

        self.mock_user.save = MagicMock()
        self.mock_customer.save = MagicMock()

        parametre(self.request)

        self.assertTrue(self.mock_user.save.called)
        self.assertTrue(self.mock_customer.save.called)
        mock_redirect.assert_called_once_with("parametre")

    # ---------------- INVOICE SECURITY ----------------

    @patch("client.views.redirect")
    @patch("client.views.get_object_or_404")
    def test_invoice_wrong_owner(self, mock_get, mock_redirect):
        fake_order = MagicMock()
        fake_order.customer_id = 99
        mock_get.return_value = fake_order

        self.mock_customer.id = 1

        invoice_pdf(self.request, order_id=10)
        mock_redirect.assert_called_once_with("commande")


# ============================================================
# 🔹 TESTS FONCTIONNELS COMPLETS (DB réelle)
# ============================================================

@pytest.mark.django_db
class TestClientFullWorkflow:

    @pytest.fixture
    def user_customer(self):
        user = User.objects.create_user(
            username="client_demo",
            password="password123",
            first_name="Jean",
            last_name="Test"
        )

        customer = Customer.objects.create(
            user=user,
            adresse="Abidjan",
            contact_1="0700000000",
            photo=SimpleUploadedFile("photo.jpg", b"file_content")
        )

        return user, customer

    @pytest.fixture
    def shop_data(self, user_customer):
        user, customer = user_customer

        cat_etab = CategorieEtablissement.objects.create(
            nom="Restaurant",
            description="Categorie test"
        )

        etablissement = Etablissement.objects.create(
            user=user,
            nom="Shop Test",
            description="Description",
            categorie=cat_etab,
            adresse="Abidjan",
            pays="CI",
            contact_1="0700000000",
            email="shop@test.com",
            nom_du_responsable="Admin",
            prenoms_duresponsable="Client"
        )

        cat_prod = CategorieProduit.objects.create(
            nom="Electronique",
            description="Test",
            categorie=cat_etab
        )

        produit = Produit.objects.create(
            nom="Produit Test",
            slug="produit-test",
            prix=1000,
            description="Produit description",
            description_deal="Promo",
            prix_promotionnel=800,
            etablissement=etablissement,
            categorie=cat_prod
        )

        Favorite.objects.create(user=user, produit=produit)

        commande = Commande.objects.create(
            customer=customer,
            prix_total=1500,
            id_paiment="PAY001",
            status=True
        )

        return {
            "produit": produit,
            "commande": commande
        }

    # ---------------- PROFIL ----------------

    def test_profil_connecte(self, client, user_customer):
        user, _ = user_customer
        client.force_login(user)

        response = client.get(reverse("profil"))
        assert response.status_code == 200

    def test_profil_anonyme(self, client):
        response = client.get(reverse("profil"))
        assert response.status_code == 302

    # ---------------- LISTE COMMANDES ----------------

    # def test_commande_liste(self, client, user_customer, shop_data):
    #     user, _ = user_customer
    #     client.force_login(user)

    #     response = client.get(reverse("commande"))
    #     assert response.status_code == 200

    #     content = response.content.decode()
    #     assert str(shop_data["commande"].prix_total) in content

    # ---------------- DETAIL COMMANDE ----------------

    def test_commande_detail_valide(self, client, user_customer, shop_data):
        user, _ = user_customer
        client.force_login(user)

        cmd = shop_data["commande"]
        response = client.get(reverse("commande-detail", args=[cmd.id]))
        assert response.status_code == 200

    def test_commande_detail_inexistante(self, client, user_customer):
        user, _ = user_customer
        client.force_login(user)

        response = client.get(reverse("commande-detail", args=[99999]))
        assert response.status_code == 404

    # ---------------- FACTURE PDF ----------------

    # def test_invoice_pdf(self, client, user_customer, shop_data):
    #     user, _ = user_customer
    #     client.force_login(user)

    #     cmd = shop_data["commande"]
    #     response = client.get(reverse("invoice_pdf", args=[cmd.id]))

    #     assert response.status_code == 200
    #     assert "pdf" in response["Content-Type"].lower()

    # ---------------- FAVORIS ----------------

    def test_liste_souhait(self, client, user_customer, shop_data):
        user, _ = user_customer
        client.force_login(user)

        response = client.get(reverse("liste-souhait"))
        assert response.status_code == 200

        content = response.content.decode()
        assert shop_data["produit"].nom in content

    # ---------------- PARAMETRE ----------------

    def test_parametre_modification(self, client, user_customer):
        user, customer = user_customer
        client.force_login(user)

        response = client.post(reverse("parametre"), {
            "first_name": "Nouveau",
            "last_name": "Nom",
            "contact": "0102030405",
            "address": "Nouvelle adresse",
            "city": ""
        }, follow=True)

        assert response.status_code == 200

        user.refresh_from_db()
        customer.refresh_from_db()

        assert user.first_name == "Nouveau"
        assert customer.contact_1 == "0102030405"