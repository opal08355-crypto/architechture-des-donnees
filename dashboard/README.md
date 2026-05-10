# Dashboard Analytique

Ce dossier prepare la partie visualisation du projet a partir des tables PostgreSQL du warehouse.

Le projet ne contient pas encore un dashboard complet embarque dans une application, mais il fournit maintenant:
- une structure de visualisation
- des requetes SQL prêtes
- une base claire pour Superset, Power BI ou Metabase

## 1. Source De Donnees

Les donnees analytiques proviennent de PostgreSQL:
- base: `medical_dw`
- tables:
  - `articles_by_source`
  - `articles_by_category`
  - `top_keywords`
  - `global_stats`

Definition SQL:
- [warehouse/create_tables.sql](/c:/Users/user/medical-bigdata-platform/warehouse/create_tables.sql:1)

Chargement des donnees:
- [spark/load_gold_to_postgres.py](/c:/Users/user/medical-bigdata-platform/spark/load_gold_to_postgres.py:1)

## 2. Visualisations Recommandees

### 2.1. Nombre d'articles par source

Type de graphique:
- bar chart

Table:
- `articles_by_source`

Utilite:
- montrer quelles sources alimentent le plus la plateforme

### 2.2. Nombre d'articles par categorie

Type de graphique:
- pie chart ou bar chart

Table:
- `articles_by_category`

Utilite:
- montrer la repartition thematique des contenus collectes

### 2.3. Top mots cles

Type de graphique:
- horizontal bar chart

Table:
- `top_keywords`

Utilite:
- montrer les themes dominants des contenus

### 2.4. Statistiques globales

Type de graphique:
- KPI cards

Table:
- `global_stats`

Indicateurs:
- nombre total d'articles
- longueur moyenne du contenu

## 3. Requetes SQL

Les requetes prêtes se trouvent dans:
- [dashboard/queries.sql](/c:/Users/user/medical-bigdata-platform/dashboard/queries.sql:1)

## 4. Outils Possibles

Vous pouvez brancher ces tables dans:
- Apache Superset
- Power BI
- Metabase
- Tableau

Pour un PFA, `Superset` ou `Power BI` sont de bons choix car ils permettent de produire des graphiques clairs rapidement.

## 5. Conseil De Presentation

Pour la soutenance, vous pouvez presenter la visualisation comme suit:

1. montrer les tables Gold
2. montrer PostgreSQL comme entrepot analytique
3. expliquer les indicateurs retenus
4. dire que ces indicateurs peuvent etre visualises dans un dashboard BI

Si vous n'avez pas encore le dashboard final pret, cette base reste deja solide pour justifier la partie visualisation du sujet.
