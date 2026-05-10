# Project Step-by-Step Walkthrough

Ce document explique le projet de bout en bout en s'appuyant directement sur les fichiers de code.

## 1. Vue d'ensemble

Le projet assemble plusieurs briques:

- collecte de donnees medicales depuis des sites fiables
- stockage dans une architecture `Bronze / Silver / Gold`
- indexation locale pour RAG
- recherche hybride `local + web`
- generation de reponses avec `gpt-4o`
- interface conversationnelle web avec memoire et multi-chat

Fichiers centraux:

- [docker-compose.yml](../docker-compose.yml)
- [scraping/scraper.py](../scraping/scraper.py)
- [kafka/producer.py](../kafka/producer.py)
- [kafka/consumer.py](../kafka/consumer.py)
- [spark/bronze_to_silver.py](../spark/bronze_to_silver.py)
- [spark/silver_to_gold.py](../spark/silver_to_gold.py)
- [spark/load_gold_to_postgres.py](../spark/load_gold_to_postgres.py)
- [warehouse/create_tables.sql](../warehouse/create_tables.sql)
- [chatbot/ingest_documents.py](../chatbot/ingest_documents.py)
- [chatbot/rag_pipeline.py](../chatbot/rag_pipeline.py)
- [chatbot/llm_generator.py](../chatbot/llm_generator.py)
- [chatbot/hybrid_pipeline.py](../chatbot/hybrid_pipeline.py)
- [chatbot/app.py](../chatbot/app.py)
- [chatbot/index.html](../chatbot/index.html)

---

## 2. Infrastructure et services

Le projet s'appuie sur plusieurs services dockerises declares dans [docker-compose.yml](../docker-compose.yml):

- `minio`:
  stockage objet pour les couches Bronze / Silver / Gold
- `postgres`:
  stockage analytique final
- `zookeeper` et `kafka`:
  streaming de messages entre producteur et consommateur

Concretement:

- MinIO expose `9000` et `9001`
- PostgreSQL expose `5432`
- Kafka expose `9092`

Ce fichier constitue la base de l'environnement technique.

---

## 3. Collecte des donnees medicales

### 3.1 Scraping batch vers Bronze

Le scraping batch principal se trouve dans [scraping/scraper.py](../scraping/scraper.py):

- `scrape_medlineplus(url)`:
  telecharge une page MedlinePlus, extrait le titre et le contenu
- `upload_json_to_minio(object_name, data)`:
  stocke le resultat dans MinIO, bucket `bronze`
- `read_urls(file_path)`:
  charge une liste d'URLs a partir d'un fichier texte

Le flux est:

1. lire une liste d'URLs
2. scraper chaque page
3. creer un identifiant derive de l'URL
4. sauvegarder chaque article JSON dans MinIO sous `medical_articles/...`

### 3.2 Scrapers specialises

Il existe aussi des variantes ou scrapers cibles:

- [scraping/scraper_medline.py](../scraping/scraper_medline.py)
- [scraping/scraper_nhs.py](../scraping/scraper_nhs.py)
- [scraping/scraper_who.py](../scraping/scraper_who.py)

Par exemple, [scraping/scraper_nhs.py](../scraping/scraper_nhs.py) montre une logique plus robuste:

- plusieurs selecteurs HTML
- nettoyage de texte
- stockage local JSON dans `scraping/output/bronze`

Ce point est important pour la soutenance: vous avez prevu des collecteurs adaptes a plusieurs sources medicales.

---

## 4. Ingestion streaming avec Kafka

Le projet inclut aussi un mode streaming.

### 4.1 Producteur Kafka

[kafka/producer.py](../kafka/producer.py):

- `scrape_medlineplus(url)`:
  scrape un article
- `send_to_kafka(data)`:
  envoie l'article au topic Kafka `medical_articles`

Le producteur sert a simuler ou industrialiser l'arrivee de nouveaux contenus.

### 4.2 Consommateur Kafka

[kafka/consumer.py](../kafka/consumer.py):

- consomme les messages du topic `medical_articles`
- transforme le message en JSON
- l'upload dans MinIO bucket `bronze`

Le schema logique est donc:

```text
Web page -> Kafka Producer -> Kafka Topic -> Kafka Consumer -> MinIO Bronze
```

---

## 5. Architecture Bronze / Silver / Gold

Le projet suit une architecture data engineering classique.

### 5.1 Bronze

La couche Bronze contient la donnee brute ou quasi brute:

- JSON scrapes
- titre
- contenu
- URL
- date de scraping

Sources de Bronze:

- batch scraping via [scraping/scraper.py](../scraping/scraper.py)
- streaming via [kafka/consumer.py](../kafka/consumer.py)

### 5.2 Silver

La transformation Bronze -> Silver est definie dans [spark/bronze_to_silver.py](../spark/bronze_to_silver.py).

Fonctions importantes:

- `clean_html(text)`:
  supprime les balises HTML
- `remove_medlineplus_noise(text)`:
  enleve du bruit de navigation et de structure
- `normalize_text(text)`:
  normalise les caracteres et les espaces
- `detect_language(text)`:
  detecte la langue
- `extract_category(url, title)`:
  attribue une categorie
- `transform_record(raw_data)`:
  fabrique l'enregistrement Silver final
- `process_bronze_to_silver()`:
  lit Bronze et ecrit Silver

Le but de Silver:

- nettoyer les contenus
- conserver uniquement les informations utiles
- enrichir avec des metadonnees

### 5.3 Gold

La transformation Silver -> Gold se trouve dans [spark/silver_to_gold.py](../spark/silver_to_gold.py).

Elle calcule:

- `articles_by_source`
- `articles_by_category`
- `top_keywords`
- `global_stats`

Le script:

- lit tous les objets Silver
- compte les sources
- compte les categories
- extrait les mots-clés les plus frequents
- calcule la longueur moyenne des contenus
- ecrit des fichiers analytiques dans MinIO bucket `gold`

### 5.4 Chargement en PostgreSQL

[spark/load_gold_to_postgres.py](../spark/load_gold_to_postgres.py):

- lit les JSON Gold dans MinIO
- insere les donnees dans PostgreSQL

Tables cibles definies dans [warehouse/create_tables.sql](../warehouse/create_tables.sql):

- `articles_by_source`
- `articles_by_category`
- `top_keywords`
- `global_stats`

Cette partie montre bien la dimension entrepot de donnees du projet.

---

## 6. Ingestion dans ChromaDB pour le chatbot

Le pont entre la pipeline data et le chatbot est [chatbot/ingest_documents.py](../chatbot/ingest_documents.py).

Fonctions importantes:

- `get_minio_client()`:
  acces aux fichiers Silver
- `clean_text(text)`:
  nettoyage supplementaire
- `detect_section(text)`:
  classe un chunk en `symptoms`, `causes`, `prevention`, `treatment`, etc.
- `detect_disease(title, content)`:
  detecte le theme medical principal
- `chunk_text_by_words(text, chunk_size=120, overlap=30)`:
  segmente les contenus
- `is_noisy_chunk(text)`:
  ignore les morceaux trop bruités
- `read_silver_documents()`:
  lit Silver et construit les chunks
- `ingest_into_chroma()`:
  cree la collection ChromaDB et injecte les documents

Le script enrichit les metadonnees avec:

- `title`
- `category`
- `section`
- `source`
- `url`
- `chunk_index`
- `disease`

C'est cette indexation qui alimente ensuite le RAG local.

---

## 7. Recuperation locale (RAG)

Le moteur de recuperation locale se trouve dans [chatbot/rag_pipeline.py](../chatbot/rag_pipeline.py).

### 7.1 Elements principaux

- `TOPIC_MAP`:
  mappe des termes de requete vers des sujets medicaux
- `SECTION_HINTS`:
  aide a detecter si la question parle de causes, symptomes, prevention, etc.
- `detect_main_topic(question)`:
  repere le theme principal
- `detect_target_section(question)`:
  repere l'intention de la question
- `extract_content(chunk_text)`:
  retire les metadonnees stockees et nettoie le contenu

### 7.2 Classement des chunks

La logique de ranking repose sur:

- mots de la question
- sujet principal detecte
- section visee
- metadonnees `disease`

Fonctions importantes:

- `rank_pairs(question, pairs, n_results=8)`
- `retrieve_pairs_with_vector_search(...)`
- `retrieve_pairs_with_keyword_search(...)`
- `retrieve_local_context(question, n_results=8)`

Le projet ne depend donc pas d'une simple similarite brute: il ajoute des heuristiques metier pour mieux choisir le contexte.

---

## 8. Generation de reponses avec OpenAI

Le module [chatbot/llm_generator.py](../chatbot/llm_generator.py) gere la generation finale.

### 8.1 Ce qu'il fait

- charge la cle API via `.env`
- cree un client OpenAI avec `trust_env=False`
- detecte la langue de la question
- construit un prompt structure
- force autant que possible la reponse dans la meme langue que la question
- nettoie la sortie du modele

### 8.2 Fonctions importantes

- `get_client()`
- `detect_question_language(question)`
- `get_no_context_message(question)`
- `build_input_messages(...)`
- `build_web_messages(...)`
- `generate_answer(...)`
- `generate_web_answer(...)`
- `format_generated_answer(answer)`

### 8.3 Pourquoi ce fichier est important

Il porte plusieurs choix de conception:

- controle de langue
- structuration des reponses
- nettoyage des reponses
- fallback si OpenAI n'est pas disponible
- web search via l'API OpenAI

---

## 9. Pipeline hybride local + web

Le cerveau du chatbot est [chatbot/hybrid_pipeline.py](../chatbot/hybrid_pipeline.py).

### 9.1 Objectif

Choisir intelligemment entre:

- contexte local
- recherche web OpenAI
- fallback web classique
- fallback local

### 9.2 Gestion des follow-up

Le fichier contient une logique de memoire conversationnelle:

- `is_ambiguous_follow_up(question, history)`
- `get_last_substantive_user_question(...)`
- `build_effective_question(question, history)`

Cette logique permet de comprendre que:

- `What causes diabetes?`
- `And how can it be prevented?`

parlent du meme sujet.

### 9.3 Niveau de confiance

Le fichier calcule aussi un niveau de confiance avec:

- `infer_confidence(...)`

et construit des diagnostics via:

- `build_diagnostics(...)`

Ces informations sont utiles pour:

- expliquer le chemin de decision
- renforcer la demo
- tracer la qualite du systeme

### 9.4 Fonction principale

- `ask_hybrid_question(question, history=None)`

Elle:

1. reconstruit la question effective
2. tente un local RAG si possible
3. bascule vers web search si necessaire
4. choisit le bon fallback
5. retourne reponse + sources + confiance + diagnostics

---

## 10. API FastAPI

[chatbot/app.py](../chatbot/app.py) expose l'application.

### 10.1 Endpoints

- `GET /`
  sert l'interface HTML
- `GET /health`
  expose l'etat du service et du modele
- `POST /ask`
  endpoint principal du chatbot

### 10.2 Ce que fait `/ask`

- recupere la question
- recupere l'historique
- appelle `ask_hybrid_question(...)`
- renvoie:
  - `mode`
  - `answer`
  - `sources`
  - `model`
  - `used_openai`
  - `context_length`
  - `confidence`
  - `diagnostics`

Le backend logue aussi:

- la question entrante
- le mode choisi
- le niveau de confiance
- le nombre de sources

---

## 11. Interface utilisateur

Le frontend est entierement integre dans [chatbot/index.html](../chatbot/index.html).

### 11.1 Ce qu'il propose

- interface moderne en une seule page
- multi-chat
- memoire locale navigateur
- selection du chat actif
- rendu structure des reponses
- affichage separe des sources
- badge d'etat API
- questions rapides

### 11.2 Fonctions importantes cote JavaScript

- `createChat(...)`
- `getActiveChat()`
- `saveHistory()`
- `loadHistory()`
- `renderChatList()`
- `renderMessages()`
- `createAnswerNode(...)`
- `askQuestion(...)`
- `startNewChat()`

### 11.3 Rendu des reponses

Les reponses du modele ne sont pas affichees comme un bloc brut:

- detection de sections
- listes numerotees
- listes a puces
- note finale de prudence

Cette partie donne une vraie valeur UX au projet.

---

## 12. Orchestration

Le dossier `airflow/` contient [airflow/dags/pipeline_medical.py](../airflow/dags/pipeline_medical.py).

La DAG orchestre maintenant le pipeline batch suivant:

1. scraping des articles
2. transformation Bronze vers Silver
3. transformation Silver vers Gold
4. creation des tables PostgreSQL
5. chargement des resultats Gold dans le warehouse

Le point important a expliquer a l'oral est le suivant:
- Airflow pilote ici le batch horaire
- Kafka couvre de son cote le besoin streaming

Autrement dit, vous pouvez maintenant presenter une separation propre:
- `Airflow` pour l'orchestration planifiee
- `Kafka` pour l'ingestion evenementielle continue

---

## 13. Ce que le jury peut retenir techniquement

Le projet montre une chaine complete:

1. collecte
2. stockage brut
3. nettoyage
4. enrichissement
5. analytique
6. indexation vectorielle
7. recuperation d'information
8. generation par LLM
9. interface utilisateur

Autrement dit, ce n'est pas seulement un chatbot: c'est une mini-plateforme data + IA.

---

## 14. Forces du projet

- architecture complete
- separation des couches de donnees
- integration RAG local + web search
- memoire conversationnelle
- multi-chat
- interface propre
- sources explicites
- adaptation a la langue de l'utilisateur

---

## 15. Limites actuelles

- la qualite du RAG local depend de la qualite de ChromaDB
- la couverture documentaire locale reste limitee
- le web search depend de l'acces internet
- l'orchestration Airflow n'est pas encore finalisee
- le systeme est informationnel, pas diagnostique

---

## 16. Comment presenter ce document a l'oral

Je vous conseille de suivre cet ordre:

1. infrastructure
2. collecte
3. pipeline Bronze / Silver / Gold
4. ingestion ChromaDB
5. RAG local
6. generation OpenAI
7. pipeline hybride
8. API
9. interface
10. limites et perspectives

De cette maniere, vous racontez un vrai flux d'ingenierie de bout en bout.
