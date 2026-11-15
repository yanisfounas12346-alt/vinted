# Repère — Arbitrage sur PC

Application PC avec tableau de bord futuriste sombre, orientée Windows, sans Telegram et sans achat automatique. Une interface navigateur communique avec un petit serveur Python lié uniquement à 127.0.0.1 ; aucun hébergement externe. Première version : moteur de règles explicables, pas de modèle ML entraîné ni de rendement promis.

## Démarrage Windows

1. Installer Python 3.11 ou supérieur depuis https://www.python.org/downloads/ avec **Add Python to PATH** et Tcl/Tk.
2. Sur GitHub : **Code → Download ZIP**, puis extraire le ZIP dans un dossier où vous pouvez écrire.
3. Double-cliquer sur **Lancer.bat**.
4. Cliquer sur **Explorer la démo** pour essayer des annonces fictives. Le portefeuille démo utilise une base séparée du portefeuille réel.

Aucune installation pip obligatoire pour le nouveau tableau de bord. Tkinter est uniquement nécessaire pour l’ancienne interface. Linux (ancienne interface) : installer le paquet `python3-tk` si nécessaire. macOS : utiliser une installation Python avec Tk. Lancer avec `python desktop.py`. La fenêtre navigateur s’ouvre automatiquement. Garder le terminal ouvert ; Ctrl+C arrête le serveur local. L’ancienne interface Tkinter reste accessible avec `python app.py`.

## Ce qui fonctionne

- Import CSV ou JSON normalisé ; validation du lot avant écriture, dédoublonnage par identifiant stable.
- Dans l’ancienne interface Tkinter uniquement, surveillance d'un fichier local toutes les 5 secondes : un collecteur autorisé externe peut le remplacer atomiquement.
- Reconnaissance par alias exacts, filtrage des défauts et revue du vendeur.
- Cote documentée de moins de 31 jours obligatoire pour une alerte ; toutes les cotes réelles sont initialement à zéro.
- Coût achat + transport + protection acheteur ; estimation de marge après frais configurables, emballage et réserve défauts.
- Nouveau tableau de bord : cartes illustrées, filtres, tri, recherche, portefeuille, cotes, paramètres, export et panneau d’inspection. Les illustrations SVG sont génériques, pas les photos réelles. Le radar est une animation d’état explicitement signalée, pas un scan du marché.
- Alertes sonores dans le nouveau tableau de bord après activation avec le bouton ♪. Ancienne interface : son, titre de fenêtre et ligne verte lors d'une nouvelle opportunité. Notifications système facultatives avec `python -m pip install -r requirements-optional.txt` ; disponibilité selon le système.
- Capital initial 100 €, plafond par objet 33 € frais inclus, achats et encaissements saisis manuellement, export du suivi CSV.
- Recherche eBay Browse API à la demande dans un thread pour garder la fenêtre réactive.

Le programme et les alertes doivent rester ouverts sur le PC ; pas de service en arrière-plan à la fermeture. Pas de photo réelle/OCR dans cette version. Aucun délai de revente garanti. Les alertes ne sont pas des probabilités d'absence d'arnaque.

## Références et frais

Modifier **references.csv** dans un éditeur de texte : `reference,aliases,floor,checked_on,source`. Séparer les alias par `|`. Prix en euros, date ISO `AAAA-MM-JJ`, source précise (URL d'une vente comparable ou devis). La date de vérification doit être renouvelée uniquement après contrôle effectif. Distinguer strictement les générations, capacités, états et accessoires ; ne pas ajouter d'alias génériques tels que « console » ou « Sony RX100 » pour plusieurs variantes. Une référence absente ou ambiguë exige une vérification.

Le fichier est un petit modèle à enrichir, pas une base de cotes de marché. Les valeurs de **references_demo.csv** sont fictives. Un prix plancher est une estimation, pas une offre de rachat garantie. Le programme ne calcule pas automatiquement le 20e percentile.

Dans **Paramètres**, renseigner frais de vente, port de revente et réserve sur chiffre d'affaires selon votre situation. Les taux sont des fractions : 0,10 = 10 %. Ils sont à zéro par défaut, donc à régler avant utilisation réelle. Le taux de réserve n'est pas un conseil fiscal. Le calcul ne constitue pas un résultat comptable.

## Import Vinted / Leboncoin / autre

Pas de connecteur automatique Vinted ou Leboncoin intégré à cette version. **Ouvrir Vinted** affiche une recherche dans votre navigateur. Importer ensuite les données obtenues manuellement ou par une source à laquelle vous avez droit d'accès. Aucune rotation d'identité, aucun contournement de CAPTCHA ou de blocage.

Format CSV : voir **annonces_demo.csv**. Champs obligatoires : `id,title,price,shipping,buyer_fee`. Frais inconnus : ne pas mettre zéro par défaut, vérifier d'abord. `seller_reviews` absent signifie contrôle nécessaire. Facultatifs : `description,seller_reviews,url`. Utiliser des identifiants préfixés par plateforme (`vinted:123`, `ebay:456`). Le JSON doit contenir une liste d'objets avec ces mêmes clés. UTF-8, maximum 5 Mo, montants positifs en euros. Les lots doivent être contrôlés manuellement : pas de délotage automatique.

La surveillance locale relit les données modifiées ; elle n'interroge pas Vinted. Arrêter la surveillance en cliquant à nouveau sur le bouton. Les annonces achetées gardent leur description historique. Une alerte sonne une fois par identifiant et session, pas à chaque modification de prix.

## eBay : accès réel facultatif

Créer une application dans le programme développeurs eBay, obtenir l'accès requis en production et un jeton OAuth d'application pour Browse API. Dans PowerShell, depuis le dossier :

```powershell
$env:EBAY_ACCESS_TOKEN = 'VOTRE_JETON_OAUTH'
py -3 desktop.py
```

Le jeton reste dans l'environnement, jamais dans le dépôt. Il expire : le remplacer lorsque nécessaire. Recherche manuelle uniquement, maximum 50 résultats par appel. Pas d'achat ni d'accès aux ventes terminées. Les résultats sans frais de port explicites en EUR sont ignorés. Les frais, la destination, les taxes éventuelles et la disponibilité doivent être revérifiés sur l'annonce avant paiement. Le nombre d'avis eBay n'est pas une certification de confiance.

## Suivi du capital

**Enregistrer un achat** enregistre une opération déjà effectuée et demande le coût payé total. **Enregistrer la vente** crédite uniquement la somme nette effectivement reçue, toutes réserves et frais déduits. Une annonce « vendue » dont le paiement est bloqué ne doit pas encore être enregistrée comme encaissée. Aucun paiement n'est effectué par l'application.

Les données sont dans **data/**, ignoré par Git. Sauvegarder ce dossier pour préserver l'historique. La version initiale ne propose pas d'annulation d'opération ni de baisse automatique de prix après 7 jours. L'export conserve les dates d'achat et de vente pour une revue manuelle.

## Projets GitHub étudiés

Sélection ciblée, pas un classement universel des « meilleurs » projets. Aucun code de ces dépôts n'est recopié dans ce projet.

| Projet | Utilité et décision |
| --- | --- |
| https://github.com/drego85/VintedScanner | Étude de la collecte et du dédoublonnage. GPL-3.0 ; utilise une API interne non documentée et signale des changements de schéma. Non intégré. |
| https://github.com/kivy/plyer | Bibliothèque MIT, intégration facultative pour les notifications PC. |
| https://github.com/rapidfuzz/RapidFuzz | Correspondance approximative MIT ; option future. Pas de rapprochement flou des références sensibles dans cette version. |
| https://github.com/timotheus/ebaysdk-python | SDK étudié ; pas retenu ici car son périmètre historique n'est pas le connecteur Browse REST utilisé. |
| https://github.com/Textualize/textual | Interface terminal étudiée ; Tkinter retenu pour une fenêtre Windows sans dépendance obligatoire. |

Documentation eBay : https://developer.ebay.com/develop/api/buy/browse_api et https://developer.ebay.com/api-docs/buy/static/ref-marketplace-supported.html . L'API Marketplace Insights des ventes terminées est restreinte et n'est pas ouverte aux nouveaux utilisateurs selon la documentation consultée le 15 novembre 2026.

## Vérification développeur

```text
python -m unittest discover -s tests -v
```

Tests du moteur et du serveur local : coûts, défauts, budget, cotes périmées, dédoublonnage, validation atomique, achat unique et encaissement unique. Le connecteur eBay nécessite des identifiants utilisateur pour un test en production.

## Interface V.02

Navigation : radar d’opportunités, portefeuille et références. Les cartes ouvrent une inspection avec les raisons du signal, les montants et un formulaire d’enregistrement manuel. Importer des CSV/JSON via le sélecteur de fichiers. Le bouton Actualiser relit les données locales, sans lancer de scan réseau. Le mode Démo reste nettement signalé. La surveillance de fichier et les notifications système Plyer restent propres à l’ancienne interface Tkinter ; la nouvelle utilise ses propres alertes sonores de navigateur.

Le serveur local utilise un jeton de session et vérifie l’hôte et l’origine des requêtes. Aucun secret n’est écrit dans Git. Le contenu des annonces est affiché comme du texte.

Validation V.02 : 12 tests automatisés passent (moteur, serveur HTTP, isolation démo/réel, validation des paramètres et contrôle de session). La prévisualisation graphique distante ne peut pas joindre le serveur local de cet environnement ; le rendu et les interactions navigateur restent à vérifier sur le PC Windows.
