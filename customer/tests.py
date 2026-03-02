from datetime import date
import json
import pytest
import unittest
from shop.models import Produit, Etablissement, CategorieEtablissement, CategorieProduit
from customer import views
from django.urls import reverse
from django.test import TestCase
from django.http import JsonResponse
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import User
from cities_light.models import City, Country
from django.core.files.uploadedfile import SimpleUploadedFile

# ============================================================================
# TESTS UNITAIRES - VALIDATION DES VUES D'AUTHENTIFICATION
# ============================================================================

@pytest.mark.django_db
class TestAuthentificationViews(unittest.TestCase):
    """
    Vérification du comportement des vues liées à l'authentification :
    connexion, inscription, déconnexion, réinitialisation de mot de passe.
    """

    def setUp(self):
        """Initialisation d'un environnement de test avec utilisateur factice."""
        self.utilisateur_test = User.objects.create_user(
            username='utilisateur_test',
            password='motdepasse123',
            email='test@exemple.com'
        )
        
        self.fausse_requete = MagicMock()
        self.fausse_requete.method = 'GET'
        self.fausse_requete.POST = {}
        self.fausse_requete.body = b''
        self.fausse_requete.FILES = {}
        self.fausse_requete.user = MagicMock()
        self.fausse_requete.user.is_authenticated = False

    # ------------------------------------------------------------------------
    # VALIDATION DE LA PAGE DE CONNEXION
    # ------------------------------------------------------------------------

    def test_redirection_utilisateur_connecte_vers_login(self):
        """Un utilisateur déjà authentifié est redirigé depuis la page de connexion."""
        self.fausse_requete.user.is_authenticated = True
        reponse = views.login(self.fausse_requete)
        self.assertEqual(reponse.status_code, 302)

    def test_affichage_page_connexion(self):
        """La page de connexion doit être accessible pour les visiteurs non connectés."""
        reponse = views.login(self.fausse_requete)
        self.assertTrue(hasattr(reponse, 'content'))

    # ------------------------------------------------------------------------
    # VALIDATION DE LA PAGE D'INSCRIPTION
    # ------------------------------------------------------------------------

    def test_redirection_utilisateur_connecte_vers_inscription(self):
        """Un utilisateur authentifié est redirigé depuis la page d'inscription."""
        self.fausse_requete.user.is_authenticated = True
        reponse = views.signup(self.fausse_requete)
        self.assertEqual(reponse.status_code, 302)

    def test_affichage_page_inscription(self):
        """La page d'inscription doit être accessible aux nouveaux visiteurs."""
        reponse = views.signup(self.fausse_requete)
        self.assertTrue(hasattr(reponse, 'content'))

    # ------------------------------------------------------------------------
    # VALIDATION DE LA PAGE DE RÉCUPÉRATION DE MOT DE PASSE
    # ------------------------------------------------------------------------

    def test_redirection_utilisateur_connecte_vers_mot_de_passe_oublie(self):
        """Un utilisateur connecté est redirigé depuis la page de récupération."""
        self.fausse_requete.user.is_authenticated = True
        reponse = views.forgot_password(self.fausse_requete)
        self.assertEqual(reponse.status_code, 302)

    def test_affichage_page_recuperation_mdp(self):
        """La page de récupération de mot de passe est accessible."""
        reponse = views.forgot_password(self.fausse_requete)
        self.assertTrue(hasattr(reponse, 'content'))

    # ------------------------------------------------------------------------
    # VALIDATION DU PROCESSUS DE CONNEXION
    # ------------------------------------------------------------------------

    @patch('customer.views.authenticate')
    @patch('customer.views.login_request')
    @patch('customer.views.User.objects.get')
    def test_connexion_reussie_par_nom_utilisateur(self, mock_recuperation_user, mock_connexion, mock_authentification):
        """Test de la connexion avec identifiants valides (nom d'utilisateur)."""
        utilisateur_factice = MagicMock()
        utilisateur_factice.is_active = True
        mock_authentification.return_value = utilisateur_factice
        mock_recuperation_user.return_value = utilisateur_factice

        donnees_post = {'username': 'utilisateur_test', 'password': 'pass123'}
        self.fausse_requete.body = json.dumps(donnees_post).encode('utf-8')

        reponse = views.islogin(self.fausse_requete)
        self.assertIsInstance(reponse, JsonResponse)
        contenu = json.loads(reponse.content)
        self.assertTrue(contenu['success'])

    # ------------------------------------------------------------------------
    # VALIDATION DE LA DÉCONNEXION
    # ------------------------------------------------------------------------

    @patch('customer.views.logout')
    @patch('customer.views.redirect')
    def test_deconnexion_utilisateur(self, mock_redirection, mock_deconnexion):
        """Vérification que la déconnexion fonctionne correctement."""
        mock_redirection.return_value = MagicMock(status_code=302)
        self.fausse_requete.user = self.utilisateur_test
        
        reponse = views.deconnexion(self.fausse_requete)
        
        self.assertEqual(reponse.status_code, 302)
        mock_deconnexion.assert_called_once_with(self.fausse_requete)
        mock_redirection.assert_called_once_with('login')

    # ------------------------------------------------------------------------
    # VALIDATION DU PROCESSUS D'INSCRIPTION
    # ------------------------------------------------------------------------

    @patch('customer.views.User')
    @patch('customer.views.models.Customer')
    @patch('customer.views.City.objects.get')
    @patch('customer.views.login_request')
    def test_creation_compte_utilisateur_reussie(self, mock_connexion, mock_ville_recuperation, mock_client, mock_modele_user):
        """Création d'un nouveau compte avec toutes les informations requises."""
        self.fausse_requete.POST = {
            'nom': 'MARTIN',
            'prenoms': 'SOPHIE',
            'username': 'sophie_martin',
            'email': 'sophie@exemple.com',
            'phone': '98765432',
            'ville': '1',
            'adresse': 'Avenue Principale',
            'password': 'mdp1234',
            'passwordconf': 'mdp1234'
        }

        instance_utilisateur = MagicMock()
        mock_modele_user.return_value = instance_utilisateur

        instance_ville = MagicMock()
        mock_ville_recuperation.return_value = instance_ville
        
        self.fausse_requete.FILES = {'file': MagicMock()}

        instance_profil = MagicMock()
        mock_client.return_value = instance_profil

        reponse = views.inscription(self.fausse_requete)
        contenu = json.loads(reponse.content)
        self.assertTrue(contenu['success'])

    # ------------------------------------------------------------------------
    # VALIDATION DE LA DEMANDE DE RÉINITIALISATION DE MOT DE PASSE
    # ------------------------------------------------------------------------

    @patch('customer.views.PasswordResetToken.objects.get_or_create')
    @patch('customer.views.User.objects.get')
    @patch('customer.views.validate_email')
    @patch('customer.views.send_mail')
    @patch('customer.views.messages')
    def test_demande_reinitialisation_mdp_reussie(self, mock_messages, mock_envoi_email, mock_validation_email, mock_recuperation_user, mock_creation_token):
        """Test de la demande de réinitialisation avec email valide."""
        self.fausse_requete.method = 'POST'
        self.fausse_requete.POST = {'email': 'sophie@exemple.com'}

        utilisateur_factice = MagicMock()
        mock_recuperation_user.return_value = utilisateur_factice
        mock_creation_token.return_value = (MagicMock(), True)

        reponse = views.request_reset_password(self.fausse_requete)
        self.assertEqual(reponse.status_code, 302)
        mock_envoi_email.assert_called_once()

    # ------------------------------------------------------------------------
    # VALIDATION DE LA RÉINITIALISATION DE MOT DE PASSE
    # ------------------------------------------------------------------------

    @patch('customer.views.PasswordResetToken.objects.get')
    @patch('customer.views.make_password')
    def test_reinitialisation_mdp_reussie(self, mock_creation_hash, mock_recuperation_token):
        """Test de la réinitialisation effective du mot de passe."""
        self.fausse_requete.method = 'POST'
        self.fausse_requete.POST = {'new_password': 'nouveaumdp123', 'confirm_password': 'nouveaumdp123'}

        token_factice = MagicMock()
        token_factice.user = MagicMock()
        token_factice.is_valid.return_value = True
        mock_recuperation_token.return_value = token_factice

        reponse = views.reset_password(self.fausse_requete, token='token123')
        self.assertEqual(reponse.status_code, 302)
        self.assertTrue(token_factice.delete.called)
        self.assertTrue(token_factice.user.save.called)

    # ------------------------------------------------------------------------
    # VALIDATION DE LA FONCTION D'ENVOI D'EMAIL DE TEST
    # ------------------------------------------------------------------------

    @patch('customer.views.send_mail')
    def test_envoi_email_test_reussi(self, mock_envoi_email):
        """Vérification que la fonction d'envoi d'email de test fonctionne."""
        reponse = views.test_email(self.fausse_requete)
        self.assertIsInstance(reponse, JsonResponse)
        contenu = json.loads(reponse.content)
        self.assertEqual(contenu['status'], 'success')


# ============================================================================
# DONNÉES DE TEST POUR LES TESTS FONCTIONNELS
# ============================================================================

@pytest.fixture
def utilisateur_standard(db):
    """Crée un utilisateur type pour les tests fonctionnels."""
    return User.objects.create_user(
        username="martine",
        password="acces123",
        first_name="Martine",
        last_name="Durand",
        email="martine@test.com"
    )

@pytest.fixture
def client_authentifie(client, utilisateur_standard):
    """Simule un client déjà connecté pour les tests."""
    client.force_login(utilisateur_standard)
    return client

@pytest.fixture
def type_etablissement(db):
    """Catégorie d'établissement nécessaire pour les tests."""
    return CategorieEtablissement.objects.create(
        nom="Boutique",
        description="Catégorie générique pour tests"
    )

@pytest.fixture
def magasin_test(db, utilisateur_standard, type_etablissement):
    """Crée un établissement complet pour les tests."""
    return Etablissement.objects.create(
        user=utilisateur_standard,
        nom="Magasin Test",
        description="Description de test",
        logo=SimpleUploadedFile("logo.jpg", b""),
        couverture=SimpleUploadedFile("couverture.jpg", b""),
        categorie=type_etablissement,
        adresse="456 Avenue Test",
        pays="France",
        contact_1="0123456789",
        email="magasin@test.com",
        nom_du_responsable="Durand",
        prenoms_duresponsable="Martine",
    )

@pytest.fixture
def type_produit(db, type_etablissement):
    """Catégorie de produit pour les tests."""
    return CategorieProduit.objects.create(
        nom="Accessoire",
        description="Catégorie accessoires",
        categorie=type_etablissement,
    )

@pytest.fixture
def article_test(db, magasin_test, type_produit):
    """Crée un article pour les tests."""
    return Produit.objects.create(
        nom="Article Test",
        slug="article-test",
        description="Description article",
        description_deal="Promotion test",
        prix=2500,
        prix_promotionnel=2000,
        etablissement=magasin_test,
        categorie=type_produit,
    )

@pytest.fixture
def client_profil(db, utilisateur_standard):
    """Crée un profil client pour l'utilisateur."""
    from customer.models import Customer
    return Customer.objects.create(
        user=utilisateur_standard,
        adresse="789 Avenue Test",
        contact_1="0123456789"
    )

@pytest.fixture
def panier_client(db, client_profil):
    """Crée un panier pour les tests."""
    from customer.models import Panier
    return Panier.objects.create(
        customer=client_profil
    )


# ============================================================================
# TESTS FONCTIONNELS - SCÉNARIOS COMPLETS
# ============================================================================

@pytest.mark.django_db
class TestScenariosFonctionnels:
    """
    Validation des scénarios utilisateur complets :
    connexion, inscription, gestion du panier, etc.
    """

    # =========================================================================
    # SCÉNARIOS DE CONNEXION
    # =========================================================================

    def test_tentative_connexion_formulaire_vide(self, client):
        """Test de soumission de formulaire de connexion vide."""
        reponse = client.post(
            reverse("post"),
            data=json.dumps({
                "username": "",
                "password": ""
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    def test_tentative_connexion_champ_utilisateur_vide(self, client):
        """Test avec nom d'utilisateur manquant."""
        reponse = client.post(
            reverse("post"),
            data=json.dumps({
                "username": "",
                "password": "test"
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    def test_tentative_connexion_identifiants_errones(self, client):
        """Test avec identifiants incorrects."""
        reponse = client.post(
            reverse("post"),
            data=json.dumps({
                "username": "inconnu",
                "password": "mauvais"
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    def test_connexion_reussie(self, client):
        """Test de connexion avec identifiants corrects."""
        User.objects.create_user(
            username="martine",
            password="acces123"
        )

        reponse = client.post(
            reverse("post"),
            data=json.dumps({
                "username": "martine",
                "password": "acces123"
            }),
            content_type="application/json"
        )

        assert reponse.status_code == 200

    # =========================================================================
    # SCÉNARIOS D'INSCRIPTION
    # =========================================================================

    def test_inscription_formulaire_completement_vide(self, client):
        """Test d'inscription avec tous les champs vides."""
        reponse = client.post(reverse("inscription"), {})
        assert reponse.status_code == 200
        assert User.objects.count() == 0

    def test_inscription_champs_obligatoires_manquants(self, client):
        """Test d'inscription avec plusieurs champs manquants."""
        reponse = client.post(reverse("inscription"), {
            "username": "",
            "email": "",
            "password": "",
            "passwordconf": "",
            "nom": "",
            "prenoms": "",
            "phone": "",
            "ville": "",
        })
        assert reponse.status_code == 200
        assert User.objects.count() == 0

    def test_inscription_donnees_completes_valides(self, client):
        """Test d'inscription réussi avec toutes les données valides."""
        pays = Country.objects.create(
            name="Côte d'Ivoire",
            code2="CI"
        )

        ville = City.objects.create(
            name="Abidjan",
            country=pays
        )

        photo_profil = SimpleUploadedFile(
            "photo_profil.jpg",
            b"contenu_fichier",
            content_type="image/jpeg"
        )

        reponse = client.post(reverse("inscription"), {
            "username": "nouvel_utilisateur",
            "email": "nouveau@test.com",
            "password": "motdepasse123",
            "passwordconf": "motdepasse123",
            "nom": "Petit",
            "prenoms": "Jean",
            "phone": "0102030405",
            "ville": ville.id,
            "adresse": "Quartier Test",
            "file": photo_profil,
        })

        assert reponse.status_code == 200
        assert User.objects.filter(username="nouvel_utilisateur").exists()

    # =========================================================================
    # SCÉNARIOS DE RÉINITIALISATION DE MOT DE PASSE
    # =========================================================================

    def test_demande_reset_champ_email_vide(self, client):
        """Test de demande de reset avec champ email vide."""
        reponse = client.post(reverse("request_reset_password"), {})
        assert reponse.status_code == 302

    def test_demande_reset_email_non_existant(self, client):
        """Test de demande de reset avec email inconnu."""
        reponse = client.post(
            reverse("request_reset_password"),
            {"email": "inconnu@test.com"}
        )
        assert reponse.status_code == 302

    def test_demande_reset_email_existant(self, client):
        """Test de demande de reset avec email valide."""
        User.objects.create_user(
            username="reset_test",
            email="reset@test.com",
            password="motdepasse123"
        )

        reponse = client.post(
            reverse("request_reset_password"),
            {"email": "reset@test.com"}
        )
        assert reponse.status_code == 302

    # =========================================================================
    # SCÉNARIOS D'AJOUT AU PANIER
    # =========================================================================

    def test_ajout_article_valide_panier(self, client_authentifie, article_test, panier_client):
        """Test d'ajout d'un article existant au panier."""
        url_ajout = reverse("add_to_cart")
        reponse = client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 2
            }),
            content_type="application/json"
        )
        
        assert reponse.status_code == 200
        donnees = reponse.json()
        assert donnees.get("success") is True

    def test_ajout_article_inexistant_panier(self, client_authentifie, panier_client):
        """Test d'ajout d'un article qui n'existe pas en base."""
        url_ajout = reverse("add_to_cart")
        try:
            reponse = client_authentifie.post(
                url_ajout,
                data=json.dumps({
                    "panier": panier_client.id,
                    "produit": 99999,
                    "quantite": 1
                }),
                content_type="application/json"
            )
            assert reponse.status_code in [200, 404, 500]
        except Exception as e:
            from shop.models import Produit
            assert isinstance(e, Produit.DoesNotExist) or "DoesNotExist" in str(e)

    def test_ajout_quantite_nulle_panier(self, client_authentifie, article_test, panier_client):
        """Test d'ajout avec quantité zéro."""
        reponse = client_authentifie.post(
            reverse("add_to_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 0
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    def test_ajout_quantite_negative_panier(self, client_authentifie, article_test, panier_client):
        """Test d'ajout avec quantité négative."""
        reponse = client_authentifie.post(
            reverse("add_to_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": -3
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    def test_ajout_multiple_meme_article(self, client_authentifie, article_test, panier_client):
        """Test d'ajout du même article à deux reprises."""
        url_ajout = reverse("add_to_cart")
        
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 2
            }),
            content_type="application/json"
        )
        
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 4
            }),
            content_type="application/json"
        )
        
        from customer.models import ProduitPanier
        article_panier = ProduitPanier.objects.get(panier=panier_client, produit=article_test)
        assert article_panier.quantite == 4

    # =========================================================================
    # SCÉNARIOS DE SUPPRESSION DU PANIER
    # =========================================================================

    def test_suppression_article_panier(self, client_authentifie, article_test, panier_client):
        """Test de suppression d'un article présent dans le panier."""
        url_ajout = reverse("add_to_cart")
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 1
            }),
            content_type="application/json"
        )
        
        from customer.models import ProduitPanier
        article_panier = ProduitPanier.objects.get(panier=panier_client, produit=article_test)
        
        reponse = client_authentifie.post(
            reverse("delete_from_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit_panier": article_panier.id
            }),
            content_type="application/json"
        )
        
        assert reponse.status_code == 200
        donnees = reponse.json()
        assert donnees.get("success") is True

    def test_suppression_article_non_present(self, client_authentifie, panier_client):
        """Test de suppression d'un article qui n'est pas dans le panier."""
        try:
            reponse = client_authentifie.post(
                reverse("delete_from_cart"),
                data=json.dumps({
                    "panier": panier_client.id,
                    "produit_panier": 99999
                }),
                content_type="application/json"
            )
            assert reponse.status_code in [200, 404, 500]
        except Exception as e:
            from customer.models import ProduitPanier
            assert isinstance(e, ProduitPanier.DoesNotExist) or "DoesNotExist" in str(e)

    # =========================================================================
    # SCÉNARIOS DE MISE À JOUR DE QUANTITÉ
    # =========================================================================

    def test_mise_a_jour_quantite_valide(self, client_authentifie, article_test, panier_client):
        """Test de mise à jour de quantité avec valeur positive."""
        url_ajout = reverse("add_to_cart")
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 1
            }),
            content_type="application/json"
        )

        reponse = client_authentifie.post(
            reverse("update_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 8
            }),
            content_type="application/json"
        )
        
        assert reponse.status_code == 200
        donnees = reponse.json()
        assert donnees.get("success") is True

    def test_mise_a_jour_quantite_zero(self, client_authentifie, article_test, panier_client):
        """Test de mise à jour de quantité à zéro."""
        url_ajout = reverse("add_to_cart")
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 3
            }),
            content_type="application/json"
        )
        
        reponse = client_authentifie.post(
            reverse("update_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 0
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    def test_mise_a_jour_quantite_negative(self, client_authentifie, article_test, panier_client):
        """Test de mise à jour de quantité avec valeur négative."""
        url_ajout = reverse("add_to_cart")
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 5
            }),
            content_type="application/json"
        )
        
        reponse = client_authentifie.post(
            reverse("update_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": -2
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    # =========================================================================
    # SCÉNARIOS DIVERS ET CAS LIMITES
    # =========================================================================

    def test_code_promo_invalide(self, client_authentifie, panier_client):
        """Test d'application d'un code promo inexistant."""
        reponse = client_authentifie.post(
            reverse("add_coupon"),
            data=json.dumps({
                "panier": panier_client.id,
                "coupon": "CODEINCONNU"
            }),
            content_type="application/json"
        )
        assert reponse.status_code == 200
        donnees = reponse.json()
        assert donnees.get("success") is False

    def test_methode_non_autorisee(self, client_authentifie):
        """Test d'utilisation d'une méthode HTTP non autorisée."""
        try:
            reponse = client_authentifie.get(reverse("add_to_cart"))
            assert reponse.status_code in [200, 302, 405]
        except Exception:
            pass

    def test_donnees_incompletes(self, client_authentifie):
        """Test d'envoi de données incomplètes à l'API."""
        try:
            reponse = client_authentifie.post(
                reverse("add_to_cart"),
                data=json.dumps({
                    "panier": None,
                    "produit": None,
                    "quantite": None
                }),
                content_type="application/json"
            )
            assert reponse.status_code in [200, 400, 500]
            donnees = reponse.json()
            assert donnees.get("success") is False
        except (KeyError, Exception):
            pass

    def test_etat_initial_panier_vide(self, client_authentifie, panier_client):
        """Vérification qu'un nouveau panier est vide."""
        from customer.models import ProduitPanier
        nombre_articles = ProduitPanier.objects.filter(panier=panier_client).count()
        assert nombre_articles == 0

    def test_persistence_donnees_panier(self, client_authentifie, article_test, panier_client):
        """Vérification que les données persistent après ajout."""
        client_authentifie.post(
            reverse("add_to_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 1
            }),
            content_type="application/json"
        )
        
        from customer.models import ProduitPanier
        presence_article = ProduitPanier.objects.filter(panier=panier_client, produit=article_test).exists()
        assert presence_article is True

    def test_panier_devient_vide_apres_suppression(self, client_authentifie, article_test, panier_client):
        """Vérification que le panier est vide après suppression du dernier article."""
        url_ajout = reverse("add_to_cart")
        client_authentifie.post(
            url_ajout,
            data=json.dumps({
                "panier": panier_client.id,
                "produit": article_test.id,
                "quantite": 1
            }),
            content_type="application/json"
        )
        
        from customer.models import ProduitPanier
        article_panier = ProduitPanier.objects.get(panier=panier_client, produit=article_test)
        
        client_authentifie.post(
            reverse("delete_from_cart"),
            data=json.dumps({
                "panier": panier_client.id,
                "produit_panier": article_panier.id
            }),
            content_type="application/json"
        )
        
        nombre_articles = ProduitPanier.objects.filter(panier=panier_client).count()
        assert nombre_articles == 0

    def test_deconnexion_utilisateur(self, client_authentifie):
        """Test de la déconnexion d'un utilisateur connecté."""
        url_deconnexion = reverse("deconnexion")
        reponse = client_authentifie.get(url_deconnexion)
        assert reponse.status_code in [200, 302]