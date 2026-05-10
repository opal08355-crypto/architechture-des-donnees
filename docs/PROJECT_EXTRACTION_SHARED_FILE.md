# Extraction Du Projet Selon Le Fichier Partage

Ce document extrait uniquement les parties de `medical-bigdata-platform` qui correspondent au fichier partage:
`C:\Users\user\Downloads\Projet  Scraping Site web.pdf`.

Le PDF decrit un projet d'architecture de donnees centre sur:
- le web scraping
- l'ingestion batch et streaming
- le Data Lake
- l'architecture Medaillon
- les transformations ETL/ELT
- le Data Warehouse
- la qualite des donnees
- l'orchestration
- la visualisation

Le depot actuel couvre bien une grande partie de ce besoin, mais il est specialise dans le domaine medical au lieu de sites d'actualite generalistes.

## 1. Ce Qui Correspond Directement Au PDF

### 1.1. Sources de donnees et scraping web

Le PDF demande un scraper capable de collecter automatiquement des articles web avec des champs comme le titre, le contenu, la source et l'URL.

Dans le projet, cette partie correspond a:
- [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:48)
- [scraping/scraper_medline.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper_medline.py:43)
- [scraping/scraper_nhs.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper_nhs.py:64)

Ce que fait le code:
- `scrape_medlineplus()` extrait le titre et le contenu principal depuis MedlinePlus.
- `scrape_nhs()` extrait le contenu principal depuis NHS avec plusieurs selecteurs HTML pour etre plus robuste.
- les scripts stockent des champs conformes au besoin du PDF:
  - `title`
  - `content`
  - `source`
  - `url`
  - `scraped_at`

Exemples de points d'entree:
- [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:87)
- [scraping/scraper_medline.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper_medline.py:73)
- [scraping/scraper_nhs.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper_nhs.py:112)

Observation:
- le PDF parle de sites d'actualite marocains et internationaux
- votre implementation applique exactement la meme logique, mais sur des sites medicaux fiables

### 1.2. Ingestion batch

Le PDF demande un mode batch avec scraping planifie.

Dans le projet, la version batch est representee par:
- [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:87)

Ce script:
- lit une liste d'URLs avec [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:81)
- scrape chaque page
- sauvegarde le resultat brut dans MinIO

La logique de stockage en batch vers le bronze est geree par:
- [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:19)

### 1.3. Ingestion streaming

Le PDF demande aussi un mode streaming ou chaque article publie devient un evenement.

Dans le projet, cette partie correspond a:
- [kafka/producer.py](/c:/Users/user/medical-bigdata-platform/kafka/producer.py:43)
- [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:49)

Ce que fait le flux:
1. le producer scrape un article puis l'envoie sur le topic Kafka `medical_articles`
   - [kafka/producer.py](/c:/Users/user/medical-bigdata-platform/kafka/producer.py:8)
2. le consumer lit les messages Kafka
   - [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:49)
3. le consumer sauvegarde ensuite les articles dans MinIO
   - [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:17)

C'est la correspondance la plus directe avec l'exigence "batch et streaming" du PDF.

### 1.4. Data Lake

Le PDF demande un Data Lake de stockage brut avec historique.

Dans le projet, ce role est joue par MinIO:
- [docker-compose.yml](/c:/Users/user/medical-bigdata-platform/docker-compose.yml:5)

Les scripts utilisent plusieurs buckets et prefixes:
- bronze pour les donnees brutes:
  - [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:15)
  - [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:13)
- silver pour les donnees nettoyees:
  - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:11)
- gold pour les donnees analytiques:
  - [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:13)

Cela correspond tres bien a l'idee de conservation de l'historique et de separation par niveaux de traitement.

### 1.5. Architecture Medaillon

Le PDF mentionne explicitement:
- Bronze: donnees brutes
- Silver: nettoyage et normalisation
- Gold: tables analytiques

Dans le projet:

Bronze:
- les donnees scrappees sont stockees telles quelles dans MinIO
- voir [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:19)
- voir [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:17)

Silver:
- nettoyage HTML, normalisation, detection de langue, categorisation
- voir [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:34)
- voir [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:73)
- voir [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:84)
- voir [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:93)
- voir [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:127)

Gold:
- calcul des statistiques analytiques
- voir [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:67)

Le projet suit donc bien la logique Medaillon attendue par le PDF.

### 1.6. Transformations ETL / ELT

Le PDF demande des transformations pour nettoyer, normaliser et enrichir les donnees.

Dans votre code, cela correspond surtout a:
- [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:127)

Transformations appliquees:
- suppression du HTML:
  - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:34)
- suppression du bruit propre a MedlinePlus:
  - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:41)
- normalisation du texte:
  - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:73)
- detection de langue:
  - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:84)
- enrichissement par categorie:
  - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:93)

### 1.7. Qualite des donnees

Le PDF insiste sur la completude, la coherence et la validite.

Dans le projet, cette exigence est partiellement implementee avec:
- [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:110)

Le controle actuel verifie:
- titre present
- contenu present
- longueur minimale du contenu
- URL presente

Ce point repond directement a la partie "tests de qualite" du PDF, meme si cela peut encore etre enrichi.

### 1.8. Data Warehouse

Le PDF demande un entrepot analytique pour les donnees consolidees.

Dans le projet:
- PostgreSQL est declare dans [docker-compose.yml](/c:/Users/user/medical-bigdata-platform/docker-compose.yml:18)
- les tables analytiques sont definies dans [warehouse/create_tables.sql](/c:/Users/user/medical-bigdata-platform/warehouse/create_tables.sql:1)
- le chargement du gold vers PostgreSQL est gere par [spark/load_gold_to_postgres.py](/c:/Users/user/medical-bigdata-platform/spark/load_gold_to_postgres.py:71)

Les tables actuelles sont:
- `articles_by_source`
- `articles_by_category`
- `top_keywords`
- `global_stats`

Cela correspond a la partie du PDF qui parle de tables analytiques pour l'aide a la decision.

### 1.9. Analytique et indicateurs

Le PDF cite des resultats attendus comme:
- nombre d'articles par source
- themes dominants
- mots cles frequents
- tendances

Dans le projet, la couche Gold calcule deja:
- articles par source:
  - [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:110)
- articles par categorie:
  - [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:111)
- top keywords:
  - [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:112)
- statistiques globales:
  - [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:114)

## 2. Ce Qui Est Seulement Partiellement Couvre

### 2.1. Orchestration Airflow

Le PDF demande une orchestration avec Apache Airflow.

Dans le depot, le fichier existe:
- [airflow/dags/pipeline_medical.py](/c:/Users/user/medical-bigdata-platform/airflow/dags/pipeline_medical.py:1)

Cette partie est maintenant implemente pour le mode batch.

La DAG orchestre:
- le scraping batch
- la transformation `bronze -> silver`
- la transformation `silver -> gold`
- la creation des tables analytiques PostgreSQL
- le chargement du Gold vers PostgreSQL

Important:
- l'orchestration Airflow couvre le pipeline batch horaire
- le streaming reste porte par Kafka, ce qui est normal car un flux streaming n'est pas pilote comme une tache batch classique

### 2.2. Visualisation

Le PDF demande des dashboards et de la visualisation.

Dans le projet, la partie analytique est prete cote donnees:
- Gold dans MinIO
- tables dans PostgreSQL

En revanche, je n'ai pas trouve dans ce depot:
- dashboard Power BI
- dashboard Streamlit
- dashboard Superset
- visualisation web dediee a ces indicateurs

Conclusion:
- la preparation des donnees pour la visualisation existe
- la couche de visualisation n'est pas encore visible dans le code fourni

### 2.3. Multiplication des sources

Le PDF vise plusieurs sites.

Dans le projet:
- MedlinePlus est bien implemente
- NHS est implemente
- [scraping/scraper_who.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper_who.py:1) existe mais est vide

Donc la logique multi-source est bien amorcee, mais pas encore complete.

## 3. Ce Qui Ne Concerne Pas Le Fichier Partage

Le PDF partage parle d'une plateforme Big Data de scraping, ingestion, transformation et analyse.

Par consequent, les elements suivants du depot ne sont pas au coeur du document partage:
- le chatbot conversationnel dans [chatbot](/c:/Users/user/medical-bigdata-platform/chatbot:1)
- l'interface de chat HTML/JS
- le pipeline RAG local
- l'integration `gpt-4o`
- la recherche web conversationnelle

Ces parties peuvent enrichir votre projet final, mais elles ne sont pas necessaires pour expliquer la portion du travail demandee par le PDF.

## 4. Lecture Simple Du Projet Par Rapport Au PDF

Si on extrait uniquement le noyau "conforme au sujet partage", alors votre projet se resume ainsi:

1. Scraper des sites web medicaux
   - [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:48)
   - [scraping/scraper_nhs.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper_nhs.py:64)

2. Ingestion batch et streaming
   - batch via [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:87)
   - streaming via [kafka/producer.py](/c:/Users/user/medical-bigdata-platform/kafka/producer.py:43) et [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:49)

3. Stockage brut dans un Data Lake
   - MinIO dans [docker-compose.yml](/c:/Users/user/medical-bigdata-platform/docker-compose.yml:5)

4. Transformation Bronze vers Silver
   - [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:165)

5. Transformation Silver vers Gold
   - [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:67)

6. Chargement du Gold dans PostgreSQL
   - [spark/load_gold_to_postgres.py](/c:/Users/user/medical-bigdata-platform/spark/load_gold_to_postgres.py:71)

7. Creation des tables analytiques
   - [warehouse/create_tables.sql](/c:/Users/user/medical-bigdata-platform/warehouse/create_tables.sql:1)

## 5. Conclusion

Par rapport au fichier partage, la partie la plus pertinente de `medical-bigdata-platform` n'est pas le chatbot, mais plutot la chaine Big Data suivante:

`Scraping -> Kafka/Batch -> MinIO Bronze -> Nettoyage Silver -> Agregation Gold -> PostgreSQL`

En une phrase:
- le projet repond bien au cahier des charges du PDF sur la collecte, l'ingestion, le stockage et la transformation
- il couvre partiellement l'orchestration et la visualisation
- il va plus loin que le PDF avec une couche chatbot, mais cette couche est hors du perimetre du document partage
