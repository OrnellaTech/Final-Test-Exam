import json
import pytest
from bs4 import BeautifulSoup
from django.urls import reverse
from customer.models import Customer
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User, AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from shop.models import CategorieProduit, Favorite, Produit, CategorieEtablissement, Etablissement 
from shop.views import (
    paiement_success, post_paiement_details, product_detail, 
    single, shop, cart, 
    commande_reçu_detail
)


# ============================================================================
# TESTS UNITAIRES - VALIDATION DES VUES DE LA BOUTIQUE
# ============================================================================

class ValidationVuesBoutique(TestCase):
    """
    Vérification du comportement individuel des vues de l'application shop :
    pages publiques, détails produit, gestion du panier, paiement, etc.
    """
    
    def setUp(self):
        """Initialisation de l'environnement de test avec données factices."""
        self.fabricant_requete = RequestFactory()
        self.client_navigation = Client()

        # 1. Création d'un utilisateur standard
        self.utilisateur_courant = User.objects.create_user(
            username='utilisateur_test',
            password='motdepasse',
            email='test@exemple.com',
            first_name='Test',
            last_name='Utilisateur',
        )

        # 2. Création d'un profil client associé
        self.profil_client = Customer.objects.create(
            user=self.utilisateur_courant,
        )

        # 3. Création d'une catégorie d'établissement
        self.type_enseigne = CategorieEtablissement.objects.create(
            nom="Restauration",
            description="Catégorie pour les tests",
        )

        # 4. Création d'un établissement
        self.enseigne_test = Etablissement.objects.create(
            user=self.utilisateur_courant,
            nom="Enseigne Test",
            description="Description pour les tests",
            logo="media/etablissements/logo/defaut.jpg",
            couverture="media/etablissements/couvertures/defaut.jpg",
            categorie=self.type_enseigne,
            nom_du_responsable="Martin",
            prenoms_duresponsable="Pierre",
            adresse="456 Avenue Test",
            pays="France",
            contact_1="0123456789",
            email="contact@enseigne.com",
        )

        # 5. Création d'une catégorie de produit
        self.type_article = CategorieProduit.objects.create(
            nom="Plat principal",
            description="Catégorie pour les tests",
            categorie=self.type_enseigne,
        )

        # 6. Création d'un produit
        self.article_test = Produit.objects.create(
            nom="Article Test",
            slug="slug-test",
            description="Description article",
            description_deal="Offre spéciale",
            prix=150,
            prix_promotionnel=120,
            categorie=self.type_article,
            etablissement=self.enseigne_test,
        )

    # ------------------------------------------------------------------------
    # VALIDATION DES PAGES PUBLIQUES
    # ------------------------------------------------------------------------

    def test_page_boutique_repond_200(self):
        """La page principale de la boutique doit être accessible."""
        requete = self.fabricant_requete.get("/boutique/")
        requete.user = AnonymousUser()
        reponse = shop(requete)
        self.assertEqual(reponse.status_code, 200)

    def test_detail_produit_visiteur_anonyme(self):
        """Un visiteur non connecté peut consulter les détails d'un produit."""
        requete = self.fabricant_requete.get("/produit/")
        requete.user = AnonymousUser()
        reponse = product_detail(requete, self.article_test.slug)
        self.assertEqual(reponse.status_code, 200)

    def test_detail_produit_utilisateur_connecte_avec_favori(self):
        """Un utilisateur connecté voit ses favoris sur la page produit."""
        Favorite.objects.create(user=self.utilisateur_courant, produit=self.article_test)
        requete = self.fabricant_requete.get("/produit/")
        requete.user = self.utilisateur_courant
        reponse = product_detail(requete, self.article_test.slug)
        self.assertEqual(reponse.status_code, 200)

    def test_page_panier_accessible(self):
        """La page du panier doit être accessible sans authentification."""
        requete = self.fabricant_requete.get("/panier/")
        requete.user = AnonymousUser()
        reponse = cart(requete)
        self.assertEqual(reponse.status_code, 200)

    @patch("shop.models.CategorieProduit.objects.get")
    def test_page_categorie_produit(self, mock_recuperation):
        """Affichage des produits d'une catégorie spécifique."""
        mock_categorie = MagicMock()
        mock_categorie.produit.all.return_value = []
        mock_recuperation.return_value = mock_categorie
        requete = self.fabricant_requete.get("/categorie/")
        reponse = single(requete, "slug-categorie")
        self.assertEqual(reponse.status_code, 200)

    # ------------------------------------------------------------------------
    # VALIDATION DES PAGES PROTÉGÉES
    # ------------------------------------------------------------------------

    def test_redirection_paiement_sans_authentification(self):
        """L'accès à la page de paiement redirige les visiteurs anonymes."""
        reponse = self.client_navigation.get(reverse('checkout'))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn('next=/deals/checkout', reponse.url)

    def test_paiement_succes_visiteur_anonyme(self):
        """Page de succès de paiement inaccessible sans authentification."""
        requete = self.fabricant_requete.get("/succes/")
        requete.user = AnonymousUser()
        reponse = paiement_success(requete)
        self.assertEqual(reponse.status_code, 302)

    def test_paiement_succes_utilisateur_connecte(self):
        """Page de succès de paiement accessible aux utilisateurs connectés."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.get(reverse('paiement_success'))
        self.assertEqual(reponse.status_code, 200)

    def test_envoi_details_paiement_donnees_invalides(self):
        """Traitement d'une requête de paiement avec données erronées."""
        requete = self.fabricant_requete.post(
            "/paiement/details",
            data=json.dumps({
                "transaction_id": "transaction_test_123",
                "notify_url": "http://exemple.com/notification",
                "return_url": "http://exemple.com/retour",
                "panier": [],
                "amount": "montant_invalide"
            }),
            content_type="application/json"
        )
        requete.user = self.utilisateur_courant

        reponse = post_paiement_details(requete)
        self.assertEqual(reponse.status_code, 200)

        contenu = json.loads(reponse.content)
        self.assertFalse(contenu["success"])

    # ------------------------------------------------------------------------
    # VALIDATION DES ACCÈS AUX RESSOURCES SPÉCIFIQUES
    # ------------------------------------------------------------------------

    def test_tableau_de_bord_utilisateur_connecte(self):
        """Le tableau de bord doit être accessible après authentification."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.get(reverse('dashboard'))
        self.assertEqual(reponse.status_code, 200)

    @patch("shop.views.get_object_or_404")
    def test_detail_recu_commande(self, mock_recuperation):
        """Affichage du détail d'une commande spécifique."""
        mock_commande = MagicMock()
        mock_commande.id = 1
        mock_recuperation.return_value = mock_commande

        requete = self.fabricant_requete.get("/commande/")
        requete.user = self.utilisateur_courant
        reponse = commande_reçu_detail(requete, 1)
        self.assertEqual(reponse.status_code, 200)

    # ------------------------------------------------------------------------
    # VALIDATION DE LA GESTION DES FAVORIS
    # ------------------------------------------------------------------------

    def test_ajout_favori_sans_authentification(self):
        """Tentative d'ajout en favori sans être connecté."""
        reponse = self.client_navigation.get(reverse('toggle_favorite', args=[self.article_test.id]))
        self.assertEqual(reponse.status_code, 302)

    def test_creation_favori_utilisateur_connecte(self):
        """Création d'un favori par un utilisateur authentifié."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.get(reverse('toggle_favorite', args=[self.article_test.id]))
        self.assertTrue(Favorite.objects.filter(user=self.utilisateur_courant, produit=self.article_test).exists())

    def test_suppression_favori_existant(self):
        """Suppression d'un favori précédemment créé."""
        Favorite.objects.create(user=self.utilisateur_courant, produit=self.article_test)
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.get(reverse('toggle_favorite', args=[self.article_test.id]))
        self.assertFalse(Favorite.objects.filter(user=self.utilisateur_courant, produit=self.article_test).exists())

    # ------------------------------------------------------------------------
    # VALIDATION DE LA GESTION DES ARTICLES
    # ------------------------------------------------------------------------

    def test_page_ajout_article_acces_get(self):
        """Accès à la page de création d'article."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.get(reverse('ajout-article'))
        self.assertEqual(reponse.status_code, 200)

    def test_modification_article_prix_invalide(self):
        """Tentative de modification avec un prix au format incorrect."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.post(
            reverse('modifier', args=[self.article_test.id]),
            data={"prix": "non_numerique"}
        )
        self.assertEqual(reponse.status_code, 302)

    def test_suppression_article_via_post(self):
        """Suppression d'un article existant via méthode POST."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.post(reverse('supprimer-article', args=[self.article_test.id]))
        self.assertEqual(reponse.status_code, 302)

    def test_parametres_etablissement_acces_get(self):
        """Accès à la page de paramétrage de l'établissement."""
        self.client_navigation.force_login(self.utilisateur_courant)
        reponse = self.client_navigation.get(reverse('etablissement-parametre'))
        self.assertEqual(reponse.status_code, 200)


# ============================================================================
# TESTS FONCTIONNELS - SCÉNARIOS UTILISATEUR COMPLETS
# ============================================================================

@pytest.mark.django_db
class ScenariosUtilisateurComplets:
    """
    Simulation de parcours utilisateur réels dans l'application :
    navigation, achats, gestion des favoris, etc.
    """
    
    @pytest.fixture(autouse=True)
    def preparation_donnees(self, db):
        """Préparation des données de test pour tous les scénarios."""
        
        self.type_enseigne = CategorieEtablissement.objects.create(
            nom="Restauration",
            description="Catégorie pour tests"
        )

        self.acheteur = User.objects.create_user(
            username="acheteur",
            password="acces123",
            first_name="Acheteur",
            last_name="Test",
            email="acheteur@test.com"
        )

        self.commercant = User.objects.create_user(
            username="commercant",
            password="acces123",
            is_staff=True,
            email="commercant@test.com"
        )

        self.magasin = Etablissement.objects.create(
            user=self.commercant,
            nom="Magasin du Commerçant",
            description="Description",
            logo=SimpleUploadedFile("logo.jpg", b""),
            couverture=SimpleUploadedFile("couverture.jpg", b""),
            categorie=self.type_enseigne,
            adresse="789 Avenue Test",
            pays="France",
            contact_1="0123456789",
            email="contact@magasin.com",
            nom_du_responsable="Dubois",
            prenoms_duresponsable="Marc",
        )

        self.famille_produit = CategorieProduit.objects.create(
            nom="Informatique",
            description="Catégorie tests",
            categorie=self.type_enseigne,
        )

        self.article_disponible = Produit.objects.create(
            nom="Ordinateur Portable",
            slug="ordinateur-portable",
            description="Ordinateur haute performance",
            description_deal="Offre de lancement",
            prix=1200,
            prix_promotionnel=999,
            etablissement=self.magasin,
            categorie=self.famille_produit,
        )

        Customer.objects.create(user=self.acheteur)
        Customer.objects.create(user=self.commercant)
    
    # ------------------------------------------------------------------------
    # SCÉNARIOS DE NAVIGATION BOUTIQUE
    # ------------------------------------------------------------------------

    def test_affichage_boutique_avec_images_produits(self, client):
        """Vérification que les images des produits s'affichent correctement."""
        reponse = client.get(reverse("shop"))
        assert reponse.status_code == 200

        analyse_html = BeautifulSoup(reponse.content, "html.parser")
        elements_image = analyse_html.find_all("img")
        assert len(elements_image) > 0

        assert any(self.article_disponible.image.url in img.get("src", "") for img in elements_image)

    def test_presence_images_produits_page_boutique(self, client):
        """Validation de l'affichage des images sur la page boutique."""
        reponse = client.get(reverse("shop"))
        assert reponse.status_code == 200
        contenu_html = reponse.content.decode()
        assert "<img" in contenu_html
        assert self.article_disponible.image.url in contenu_html

    def test_classement_produits_par_date_creation(self, client):
        """Vérification du tri des produits par date (plus récents en premier)."""
        article_ancien = Produit.objects.create(
            nom="Modèle plus ancien", 
            slug="modele-ancien", 
            prix=450,
            etablissement=self.magasin, 
            categorie=self.famille_produit
        )
        
        from django.utils import timezone
        article_ancien.date_add = timezone.now() - timezone.timedelta(days=2)
        article_ancien.save()

        reponse = client.get(reverse("shop"))
        liste_produits = list(reponse.context["produits"])
        
        assert liste_produits[0].nom == "Ordinateur Portable"

    # ------------------------------------------------------------------------
    # SCÉNARIOS DE CONSULTATION DÉTAILS PRODUIT
    # ------------------------------------------------------------------------

    def test_consultation_produit_existant(self, client):
        """Accès à la page de détail d'un produit existant."""
        reponse = client.get(reverse("product_detail", args=[self.article_disponible.slug]))
        assert reponse.status_code == 200

    def test_consultation_produit_inexistant(self, client):
        """Tentative d'accès à un produit qui n'existe pas."""
        reponse = client.get(reverse("product_detail", args=["produit-inexistant"]))
        assert reponse.status_code == 404

    def test_informations_produit_affichees_correctement(self, client):
        """Vérification que toutes les infos produit sont présentes."""
        reponse = client.get(reverse("product_detail", args=[self.article_disponible.slug]))
        assert reponse.status_code == 200
        contenu = reponse.content.decode()
        assert self.article_disponible.nom in contenu
        assert "1200" in contenu

    # ------------------------------------------------------------------------
    # SCÉNARIOS DE NAVIGATION PAR CATÉGORIE
    # ------------------------------------------------------------------------

    def test_categorie_sans_produit(self, client):
        """Affichage d'une catégorie ne contenant aucun produit."""
        categorie_vide = CategorieProduit.objects.create(
            nom="Catégorie Sans Produit",
            slug="categorie-vide",
            categorie=self.type_enseigne,
        )
        reponse = client.get(reverse("categorie", args=[categorie_vide.slug]))
        assert reponse.status_code == 200
        assert len(reponse.context['produits']) == 0

    def test_categorie_contenant_produits(self, client):
        """Affichage d'une catégorie contenant des produits."""
        reponse = client.get(reverse("categorie", args=[self.famille_produit.slug]))
        assert reponse.status_code == 200
        assert self.article_disponible.nom in reponse.content.decode()

    # ------------------------------------------------------------------------
    # SCÉNARIOS DE PAIEMENT
    # ------------------------------------------------------------------------

    def test_page_succes_paiement_utilisateur_connecte(self, client):
        """Accès à la page de succès de paiement après connexion."""
        client.force_login(self.acheteur)
        reponse = client.get(reverse("paiement_success"))
        assert reponse.status_code == 200

    def test_redirection_paiement_pour_visiteur(self, client):
        """Un visiteur anonyme est redirigé depuis la page de succès."""
        reponse = client.get(reverse("paiement_success"))
        assert reponse.status_code == 302

    def test_envoi_details_paiement_incomplets(self, client):
        """Tentative d'envoi de données de paiement manquantes."""
        donnees = {
            "transaction_id": None, "notify_url": None, 
            "return_url": None, "panier": None
        }
        reponse = client.post(
            reverse("paiement_detail"), 
            data=json.dumps(donnees), 
            content_type="application/json"
        )
        assert reponse.json()["success"] is False

    def test_envoi_details_paiement_complets(self, client):
        """Envoi réussi de toutes les données de paiement."""
        client.force_login(self.acheteur)
        donnees = {
            "panier": 1,
            "transaction_id": "TX123456",
            "notify_url": "http://test.com/notification",
            "return_url": "http://test.com/retour"
        }
        reponse = client.post(
            reverse("paiement_detail"),
            data=json.dumps(donnees),
            content_type="application/json"
        )
        assert reponse.status_code == 200

    # ------------------------------------------------------------------------
    # SCÉNARIOS DE GESTION DES FAVORIS
    # ------------------------------------------------------------------------

    def test_creation_favori_utilisateur_connecte(self, client):
        """Ajout d'un produit aux favoris."""
        client.force_login(self.acheteur)
        reponse = client.get(reverse("toggle_favorite", args=[self.article_disponible.id]))
        assert reponse.status_code in [200, 302]
        assert Favorite.objects.filter(user=self.acheteur, produit=self.article_disponible).exists()

    def test_retrait_favori_existant(self, client):
        """Suppression d'un produit des favoris."""
        client.force_login(self.acheteur)
        Favorite.objects.create(user=self.acheteur, produit=self.article_disponible)
        reponse = client.get(reverse("toggle_favorite", args=[self.article_disponible.id]))
        assert reponse.status_code in [200, 302]
        assert not Favorite.objects.filter(user=self.acheteur, produit=self.article_disponible).exists()

    def test_favori_sans_authentification(self, client):
        """Tentative d'ajout en favori sans être connecté."""
        reponse = client.get(reverse("toggle_favorite", args=[self.article_disponible.id]))
        assert reponse.status_code == 302

    # ------------------------------------------------------------------------
    # SCÉNARIOS D'ACCÈS AU TABLEAU DE BORD
    # ------------------------------------------------------------------------

    def test_acces_tableau_bord_commercant(self, client):
        """Un commerçant peut accéder à son tableau de bord."""
        client.force_login(self.commercant)
        reponse = client.get(reverse("dashboard"))
        assert reponse.status_code == 200

    def test_acces_tableau_bord_acheteur_simple(self, client):
        """Un acheteur simple ne peut pas accéder au tableau de bord commerçant."""
        client.force_login(self.acheteur)
        reponse = client.get(reverse("dashboard"))
        assert reponse.status_code in [302, 403, 404]

    # ------------------------------------------------------------------------
    # SCÉNARIOS DE GESTION DES ARTICLES
    # ------------------------------------------------------------------------

    def test_creation_article_reussie(self, client):
        """Création d'un nouvel article avec données valides."""
        client.force_login(self.commercant)
        reponse = client.post(reverse("ajout-article"), {
            "nom": "Nouvel Article Test",
            "description": "Description détaillée de l'article",
            "prix": "750",
            "quantite": 15,
            "categorie": self.famille_produit.id,
        })
        assert reponse.status_code in [200, 302]

    def test_creation_article_donnees_incompletes(self, client):
        """Tentative de création d'article avec données manquantes."""
        client.force_login(self.commercant)
        
        reponse = client.post(reverse("ajout-article"), {
            "nom": "",
            "description": "",
            "prix": "",
            "categorie": "",
        })
        
        assert reponse.status_code in [200, 302, 404]
        assert Produit.objects.filter(nom="").count() == 0

    def test_modification_article_donnees_valides(self, client):
        """Modification d'un article existant avec données correctes."""
        client.force_login(self.commercant)
        reponse = client.post(reverse("modifier", args=[self.article_disponible.id]), {
            "nom": "Article Mis à Jour",
            "prix": "1350",
            "quantite": "8",
            "description": "Description actualisée",
            "categorie": self.famille_produit.id 
        })
        assert reponse.status_code in [200, 302]

    def test_suppression_article_existant(self, client):
        """Suppression définitive d'un article."""
        client.force_login(self.commercant)
        reponse = client.post(reverse("supprimer-article", args=[self.article_disponible.id]))
        assert reponse.status_code == 302
        assert not Produit.objects.filter(id=self.article_disponible.id).exists()

    # ------------------------------------------------------------------------
    # SCÉNARIOS DE PARAMÉTRAGE ÉTABLISSEMENT
    # ------------------------------------------------------------------------

    def test_acces_parametres_etablissement_commercant(self, client):
        """Un commerçant peut modifier les paramètres de son établissement."""
        client.force_login(self.commercant)
        reponse = client.get(reverse("etablissement-parametre"))
        assert reponse.status_code == 200

    def test_acces_parametres_etablissement_anonyme(self, client):
        """Un visiteur anonyme ne peut pas accéder aux paramètres."""
        reponse = client.get(reverse("etablissement-parametre"))
        assert reponse.status_code == 302