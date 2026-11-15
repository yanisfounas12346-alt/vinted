# REPÈRE V.04.1 — Surveillance et arbitrage sur PC

Tableau de bord local Windows : annonces réelles, images disponibles, surveillance, journal, cotes documentées, calcul de marge et suivi des achats/encaissements. Aucun achat automatique et aucun Telegram.

## Correction V.04.1 — identité des jeux

Un poster Zelda pouvait hériter du prix de la cartouche en raison du titre partagé. Le moteur exclut désormais les posters, affiches, guides, figurines, vêtements et autres produits dérivés identifiés dans le titre des 20 jeux ciblés, ou une description qui identifie explicitement un dérivé. Ces annonces affichent « Objet différent », sans cote, marge ni signal de jeu. Les jeux avec un bonus explicitement identifié restent analysables. Les anciennes annonces sont recalculées après redémarrage, sans réimportation. L’identification reste textuelle : un titre incomplet ou trompeur doit toujours être contrôlé.

## Nouveautés V.04 — analyses et livraison intégrées

- **Analyses des 50 produits** : conclusions individuelles, liens des observations, exclusions (HS, boîte vide, mauvaises versions, ventes non prouvées, prix d’offre masqués), qualité des données et contrôles du produit. Rapport complet : **ANALYSE_50_PRODUITS.md**.
- **Frais & livraison** : coût d’achat expédié ou main propre, Mondial Relay ou Colissimo, port de revente offert ou facturé à l’acheteur, frais eBay sur objet + port, TVA sur frais, réserves d’activité/risques et marge cible. Tous les montants sont en euros ; les taux sont des fractions.
- Les cartes reconnues affichent **marge prévue**, **plafond du prix de l’article** et port de revente. Si les frais d’achat ne sont pas connus, ils sont estimés et clairement signalés. Les plafonds ne sont plus un simple ratio de 50 % du prix de revente.
- Chaque fiche peut être simulée avec un prix d’achat précis et les frais réellement affichés au paiement. Le poids emballé, l’emballage, les tests et la commission de catégorie se modifient dans la fiche.
- Le tarif public de transport est un scénario : le tarif négocié Vinted peut être différent. Le poids doit être pesé. Le prix capturé est supposé hors protection acheteur ; contrôler le paiement avant de saisir les frais pour ne pas les compter deux fois.
- Les prix de recherche restent des estimations provisoires, pas des prix planchers garantis. Les dossiers insuffisants n’ont aucun plafond actif. Les devis/cotes personnels déjà saisis sont conservés. Un devis manuel documenté ou cinq ventes comparables importées peuvent remplacer l’estimation.
- La réserve d’activité de 15 % est une hypothèse de trésorerie, pas une déclaration de taux légal unique ; la marge est avant impôt sur le revenu et charges fixes. Les tarifs eBay intégrés supposent un compte professionnel France et une TVA de 20 % sur frais non récupérée : ajuster selon la facture et la catégorie réelle.
- Les 2 € de test Instax sont une provision de consommable par objet : s’il faut acheter un pack complet pour tester, renseigner la dépense effective et garder le cash nécessaire. Pas de réparation incluse par défaut.

### Mise à jour sans perdre le portefeuille

Fermer l’ancien terminal, extraire le nouveau ZIP dans un **nouveau dossier**, copier le dossier **data/** de l’ancienne version vers ce nouveau dossier, puis lancer **Lancer.bat**. L’extension reste compatible ; si le port local change, recopier sa configuration depuis Connexions. Ne pas envoyer le contenu de data/ sur GitHub.

## Installation et mise à jour

1. Installer Python 3.11 ou supérieur depuis https://www.python.org/downloads/ (cocher **Add Python to PATH**).
2. Extraire tout le ZIP dans un dossier où vous pouvez écrire. Pour une mise à jour, fermer l’ancien terminal et conserver son dossier **data/** en le copiant dans le nouveau dossier Repere_PC avant lancement. Ne pas fusionner les fichiers source de deux versions.
3. Double-cliquer sur **Lancer.bat**. Le navigateur s’ouvre sur une adresse `127.0.0.1`, normalement port 8765. Garder le terminal ouvert. Ctrl+C pour arrêter.
4. **Connexions** explique comment recevoir les annonces et configurer eBay. L’interface principale démarre sur les données réelles, sans proposition de démonstration.

Aucun pip nécessaire pour le tableau de bord. Le serveur est lié exclusivement à 127.0.0.1, pas à votre réseau local. Le port est alternatif si 8765 est déjà occupé ; dans ce cas recopier la configuration du pont.

## Recevoir des annonces Vinted et Leboncoin

### Pont Chrome / Edge fourni

Le pont transmet les cartes d’annonces présentes dans les pages de recherche que vous ouvrez vous-même. Il ne copie pas votre session, vos cookies ou votre mot de passe. Il ne résout pas de CAPTCHA et ne passe pas outre un refus du site.

1. Edge : ouvrir `edge://extensions`. Chrome : ouvrir `chrome://extensions`.
2. Activer **Mode développeur**, cliquer **Charger l’extension non empaquetée**, sélectionner le dossier **extension** livré avec Repère.
3. Dans Repère, **Connexions → Copier la configuration du pont**.
4. Ouvrir l’extension Repère depuis le menu Extensions du navigateur. Coller la configuration et cliquer **Enregistrer la connexion locale**.
5. Ouvrir une page de résultats sur Vinted.fr ou Leboncoin.fr avec des titres et prix en euros affichés. Cliquer l’extension → **Envoyer les annonces de cet onglet**.
6. Les cartes apparaissent dans le tableau de bord (actualisation locale toutes les 5 s). Le journal confirme les lots réellement reçus.

**Surveiller + actualiser toutes les 90 s** active un rafraîchissement de cet onglet et transmet les cartes rendues après chargement. La surveillance est propre à cette URL et doit être réactivée après un changement de recherche. Elle s’arrête au premier échec, refus ou écran de vérification. Le chargement différé de certaines pages peut empêcher l’extraction ; dans ce cas, attendre la fin d’affichage puis envoyer manuellement les annonces. Si le site change son HTML ou refuse l’accès, la lecture peut échouer ; le pont affiche le problème au lieu de simuler des résultats. Cette extension nouvelle n’est pas validée sur les pages authentifiées du PC de l’utilisateur dans cet environnement.

Permission `activeTab` : lecture de la page après clic. `scripting` : extraction des cartes. `storage` : configuration de connexion locale. `alarms` : intervalle de surveillance de 90 secondes. Permission HTTP 127.0.0.1 : transmission uniquement à votre poste. Pas d’accès permanent à tous les sites. La configuration contient un secret local ; ne pas la publier.

### Accès direct Vinted

Dans le panneau de surveillance, choisir **Vinted**, une ou plusieurs recherches (une par ligne), un intervalle d’au moins 60 secondes et **Démarrer**. La première recherche est immédiate, les suivantes sont séquentielles. **Arrêter** interrompt l’attente et empêche l’import d’une réponse qui reviendrait ensuite.

Le connecteur utilise le catalogue interne non documenté de Vinted, pas une API officielle garantie. Un test réel réalisé depuis cet environnement le 15 novembre 2026 a reçu **HTTP 403**. Son fonctionnement n’est donc pas garanti sur votre PC. Après un refus 401/403/429, une erreur réseau ou un changement de schéma, la surveillance est suspendue sans nouvelle tentative automatique. L’état et le journal affichent l’erreur. Aucun proxy, usurpation de navigateur, rotation d’identité ou contournement. Utiliser le pont pour les annonces que vous pouvez normalement consulter.

Le catalogue ne fournit pas nécessairement la description complète, les avis, le port et la protection acheteur. Ces données restent inconnues jusqu’à votre vérification.

## eBay officiel

Obtenir un jeton OAuth valide et les accès nécessaires à Browse API depuis son propre compte développeur eBay. **Connexions → eBay** : coller le jeton puis **Activer eBay**. Il est conservé en mémoire uniquement, jamais dans Git ni dans les fichiers du portefeuille. Il faut le remettre après fermeture ou expiration. L’environnement `EBAY_ACCESS_TOKEN` reste pris en charge.

Choisir eBay dans le panneau, renseigner les recherches puis démarrer. Maximum 50 résultats par appel ; annonces d’achat immédiat en EUR. Pas d’historique automatique des ventes terminées. La note de feedback eBay n’est pas assimilée à un nombre d’avis positifs. Port, taxes, destination et frais restent à vérifier sur le site.

Documentation : https://developer.ebay.com/develop/api/buy/browse_api . L’API Marketplace Insights des ventes terminées est restreinte : https://developer.ebay.com/api-docs/buy/static/ref-marketplace-supported.html . Pas de jeton utilisateur disponible pour un test de production ici.

## Cotes et marges

**Analyses des 50 produits** charge 50 fiches de recherche : 32 estimations provisoires et 18 dossiers suspendus. Elles ne constituent pas 50 cotes de ventes validées. **Références & cotes** permet de saisir un devis documenté ou une cote personnelle. Cliquer sur une ligne pour saisir la cote, la date et la source (vente comparable ou devis). La reconnaissance utilise des alias exacts ; elle peut manquer des fautes ou des modèles ambigus. Vérifier la génération, la version, la langue, les accessoires et l’état exacts. Les jeux Pokémon exigent un contrôle d’authenticité ; aucun logiciel ne le garantit.

La cote peut aussi être calculée à partir de vos ventes comparables : **Importer des ventes terminées**. Format CSV du fichier **ventes_modele.csv** :

```text
reference,price,sold_on,source,condition,sold
```

- `reference` : nom exact de la référence dans l’application.
- `price` : prix de vente de l’objet en euros, séparé du transport, comparable à la cote recherchée.
- `sold_on` : date ISO AAAA-MM-JJ dans les 90 derniers jours.
- `source` : lien ou preuve distincte de chaque vente réellement terminée.
- `condition` : même état et configuration pour tout le groupe, sinon séparer les données.
- `sold` : `true` pour confirmer que la vente a effectivement eu lieu.

Au moins cinq ventes distinctes par modèle sont nécessaires. Le programme calcule le 20e percentile avec interpolation linéaire et conserve vos preuves dans **data/sales.json**. Il contrôle la structure et les dates, pas l’authenticité des preuves externes. Les données d’annonces encore en vente ne doivent pas être utilisées comme ventes terminées. Une cote positive exige date et source. Après 30 jours sans nouveau contrôle, la cote ne peut plus déclencher un signal qualifié.

L’outil distingue :

- **À vérifier** : référence/cote manquante, défaut possible ou critères non remplis.
- **Signal à compléter** : prix intéressant par rapport à une cote documentée, mais frais, avis ou état encore incomplets. Ce n’est pas un achat conseillé.
- **Critères remplis** : frais connus, marge suffisante, minimum trois avis positifs déclarés, état confirmé et budget respecté. La disponibilité et le produit doivent encore être vérifiés avant paiement.

Cliquer une carte pour compléter **Port achat**, **Protection / frais achat**, **Avis positifs** et la confirmation d’inspection. Si le prix change lors d’une collecte suivante, les frais précédemment vérifiés sont invalidés pour recalcul. Un coût inconnu ne devient jamais automatiquement zéro ; la marge reste « À compléter ». Les vérifications manuelles d’état et les descriptions sont préservées lors du dédoublonnage.

Pour les 50 fiches, utiliser **Analyses des 50 produits → Frais & livraison** et les coûts de chaque modèle. Les anciens champs de frais dans **Paramètres** restent utilisés pour les références personnelles sans fiche de recherche. Les taux sont des fractions : 0,10 = 10 %. Frais de vente et réserve sur CA sont à zéro initialement, à adapter à votre situation avant usage. Aucune valeur ne constitue un conseil fiscal ou une cote garantie. Pas de garantie de vente, de délai ou de bénéfice.

## Capital, suivi et alertes PC

Capital initial 100 €, plafond par objet 33 € frais inclus. **Enregistrer l’achat** enregistre un achat déjà effectué avec son coût total. **Enregistrer la vente** crédite uniquement le net effectivement reçu, après tous frais et réserves. Ne pas compter un paiement encore bloqué comme encaissé. L’application n’effectue aucun paiement.

Activer les sons avec le bouton ♪. Les nouveaux signaux reçus pendant la session déclenchent un son et un message dans le tableau de bord. Le navigateur doit rester ouvert pour ses alertes. Le processus Python doit rester lancé pour les collectes. Le journal montre les appels réussis, les importations et les refus. Les données sont conservées dans **data/**, exclu de Git et des ZIP livrés. Sauvegarder ce dossier. Les boutons d’export fournissent le suivi réel.

Le radar reste une animation d’état et non une visualisation géographique ou une preuve de collecte. Seuls le compteur de données reçues, les horodatages et le journal attestent des recherches. Pas de baisse automatique des annonces après sept jours : le programme ne modifie pas vos ventes sur les plateformes. Les dates du suivi permettent ce contrôle manuellement.

## Autres entrées et limites

CSV/JSON d’annonces normalisées : `id,title,price`, puis `shipping,buyer_fee,seller_reviews,description,url,image_url,condition_confirmed` si disponibles. Identifiants stables préfixés par plateforme. Fichier UTF-8, maximum 5 Mo. Les frais vides restent inconnus. `condition_confirmed=true` correspond à une inspection que vous avez réellement réalisée.

Pas de modèle ML entraîné, pas d’authentification automatique des objets et pas d’OCR dans cette version. Les règles sont explicables et la calibration est statistique. La collecte n’est pas autorisée ou fiable par le seul fait qu’un dépôt GitHub existe : utiliser les plateformes dans les conditions applicables. Les changements d’API ou de DOM peuvent nécessiter une mise à jour des connecteurs.

L’ancienne interface Tkinter (`python app.py`) est conservée pour compatibilité mais le parcours V.04 décrit ici utilise **desktop.py**. Les anciennes données de démonstration servent aux tests internes, sans bouton de démonstration dans l’interface principale.

## Projets GitHub étudiés

| Projet | Rôle |
| --- | --- |
| https://github.com/drego85/VintedScanner | Documentation de l’évolution du catalogue Vinted et de ses limites ; projet GPL-3.0. Aucun code recopié. Le connecteur présent est une implémentation indépendante. |
| https://github.com/kivy/plyer | Notifications facultatives de l’ancienne interface. |
| https://github.com/rapidfuzz/RapidFuzz | Étudié pour les correspondances floues, non intégré pour éviter les confusions de modèles. |
| https://github.com/timotheus/ebaysdk-python | SDK historique étudié ; connecteur Browse REST utilisé directement ici. |
| https://github.com/Textualize/textual | Framework étudié ; interface navigateur locale retenue. |

## Vérification

```text
python -m unittest discover -s tests -v
node --check web/dashboard.js
```

42 tests Python passent. La syntaxe des quatre scripts JavaScript, le manifeste de l’extension et les cibles HTML ont également été contrôlés. Tests : coûts connus/inconnus, calibration sur ventes, refus de schéma invalide, suspension sans nouvelle tentative après refus, arrêt avant import tardif, séparation réel/test, édition vérifiée, suivi du cash et authentification HTTP locale. Les fixtures et mocks ne constituent pas un test réel des plateformes. Le navigateur de test distant ne peut pas joindre le serveur local dans cet environnement ; la vérification visuelle et le test de l’extension sur votre navigateur restent à faire.
