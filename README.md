# Medical Big Data Platform

Plateforme de donnees medicales avec pipeline de collecte, nettoyage, indexation vectorielle et chatbot conversationnel hybride `RAG local + web search + gpt-4o`.

## 1. Objectif

Ce projet a pour objectif de construire une chaine complete de valorisation de donnees medicales:

- collecte de contenus depuis des sources medicales fiables
- nettoyage et structuration des donnees
- indexation locale dans ChromaDB
- recherche hybride entre base locale et web
- generation de reponses conversationnelles avec `gpt-4o`
- interface web moderne avec memoire et multi-chat

Le chatbot ne remplace pas un avis medical. Il fournit une aide informationnelle basee sur des sources selectionnees.

## 2. Problematique

Les donnees medicales disponibles sur le web sont nombreuses mais souvent:

- dispersees
- heterogenes
- bruitées
- difficiles a transformer en reponses claires pour un utilisateur final

L'objectif du projet est donc de proposer une architecture capable de:

- centraliser des donnees de sante pertinentes
- les nettoyer et les indexer
- produire des reponses plus fiables qu'un simple chatbot generique
- combiner un socle local avec une extension web quand l'information manque

## 3. Architecture globale

```text
Web Sources
   |
   v
Scraping / Kafka / Stockage Bronze
   |
   v
Nettoyage / Silver / Preparation
   |
   v
Ingestion ChromaDB
   |
   v
RAG local  ---------
                   |
                   v
            Pipeline hybride
                   |
        Local RAG / Web Search / Fallback
                   |
                   v
          Generation avec gpt-4o
                   |
                   v
        Interface FastAPI + Frontend Chat
```

## 4. Technologies utilisees

- `Python`
- `FastAPI`
- `OpenAI Responses API`
- `ChromaDB`
- `SentenceTransformers`
- `MinIO`
- `Kafka`
- `Spark`
- `HTML / CSS / JavaScript`

## 5. Structure du projet

```text
airflow/        Orchestration pipeline
chatbot/        API, RAG, interface et generation LLM
dashboard/      Configuration visualisation
kafka/          Producteur / consommateur
scraping/       Collecte des donnees web
spark/          Transformations de donnees
warehouse/      SQL et modeles de stockage
```

Fichiers importants:

- [chatbot/app.py](chatbot/app.py)
- [chatbot/hybrid_pipeline.py](chatbot/hybrid_pipeline.py)
- [chatbot/llm_generator.py](chatbot/llm_generator.py)
- [chatbot/rag_pipeline.py](chatbot/rag_pipeline.py)
- [chatbot/ingest_documents.py](chatbot/ingest_documents.py)
- [chatbot/index.html](chatbot/index.html)

## 6. Fonctionnement du chatbot

### 6.1 Pipeline de reponse

1. L'utilisateur pose une question.
2. Le backend detecte si c'est une nouvelle question ou un suivi conversationnel.
3. Le systeme tente d'abord une recherche locale dans ChromaDB.
4. Si le contexte local est faible ou absent, il bascule vers une recherche web via OpenAI.
5. Si le web n'est pas disponible, il tente un fallback web classique.
6. La reponse finale est generee avec `gpt-4o` ou, a defaut, avec un fallback local.

### 6.2 Strategie hybride

- `local_rag`:
  le contexte local est suffisant
- `web_search`:
  la question est mieux servie par la recherche web
- `web_search_fallback`:
  fallback web classique
- `local_rag_fallback`:
  contexte local faible mais encore exploitable
- `no_context`:
  aucune information fiable suffisante

### 6.3 Memoire conversationnelle

Le chatbot:

- garde l'historique de la conversation
- gere plusieurs chats distincts
- reutilise le sujet precedent pour les questions de suivi courtes

Exemple:

- `What causes diabetes?`
- `And how can it be prevented?`

Le systeme conserve le sujet `diabetes` et n'interprete pas la deuxieme question comme un nouveau sujet.

## 7. Ameliorations deja integrees

- reponses structurees
- memoire conversationnelle
- multi-chat dans l'interface
- adaptation de la langue a la langue de la question
- recherche web via OpenAI
- affichage des sources separees
- niveau de confiance dans la reponse
- logs backend utiles pour la demonstration
- meilleure detection des suivis conversationnels
- filtrage local plus strict pour eviter les melanges de maladies

## 8. Lancement du projet

### 8.1 Prerequis

- Python
- environnement virtuel `venv`
- cle OpenAI valide

### 8.2 Configuration

Utiliser `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
CHATBOT_LOG_LEVEL=INFO
```

### 8.3 Lancer l'application

```powershell
venv\Scripts\activate
uvicorn chatbot.app:app --reload
```

Ouvrir ensuite:

```text
http://127.0.0.1:8000
```

### 8.4 Lancer l'orchestration Airflow

Le projet inclut maintenant une DAG batch dans [airflow/dags/pipeline_medical.py](airflow/dags/pipeline_medical.py).

Pour demarrer l'infrastructure et Airflow:

```powershell
docker compose up -d minio postgres zookeeper kafka airflow-init airflow-webserver airflow-scheduler
```

Puis ouvrir:

```text
http://127.0.0.1:8080
```

Identifiants par defaut:

- `admin`
- `admin`

La DAG `pipeline_medical` orchestre:
- le scraping batch
- `bronze -> silver`
- l'enrichissement LLM `silver -> gold/llm_enriched`
- `silver -> gold`
- la creation des tables PostgreSQL
- le chargement du Gold vers PostgreSQL

Note:
- Airflow utilise sa propre base metadata PostgreSQL
- le warehouse analytique du projet reste `medical_dw`

## 9. Reingestion des donnees locales

Si vous modifiez les donnees nettoyees ou les scrapers, il faut recharger ChromaDB:

```powershell
venv\Scripts\activate
python chatbot\ingest_documents.py
```

Note:
- l'ingestion du chatbot utilise d'abord `gold/llm_enriched/` si disponible
- sinon elle bascule automatiquement sur `silver/medical_articles_clean/`

## 10. Scenarios de demonstration

Voir:

- [docs/DEMO_CHECKLIST.md](docs/DEMO_CHECKLIST.md)
- [docs/TEST_SCENARIOS.md](docs/TEST_SCENARIOS.md)
- [docs/PRESENTATION_PLAN.md](docs/PRESENTATION_PLAN.md)
- [docs/LLM_ENRICHMENT_MINIO.md](docs/LLM_ENRICHMENT_MINIO.md)

## 11. Forces du projet pour un PFA

- architecture bout-en-bout
- combinaison data engineering + IA generative
- pipeline hybride local/web
- interface utilisateur exploitable
- logique de memoire conversationnelle
- focus sur la fiabilite et les sources

## 12. Limites actuelles

- la qualite du RAG local depend fortement de la qualite des documents ingeres
- certaines requetes tres larges restent mieux traitees par le web
- ce systeme n'est pas un outil de diagnostic medical
- la recherche web depend d'un acces internet et d'une cle OpenAI valide

## 13. Pistes d'amelioration

- base documentaire locale plus riche
- evaluation automatique des reponses
- historique persistant cote backend avec base de donnees
- authentification utilisateur
- tableau de bord d'analytics des questions
- citation plus fine par passage

## 14. Securite

- ne jamais versionner `.env`
- regenerer la cle OpenAI si elle a ete exposee
- limiter les sources web a des domaines de confiance

## 15. Conclusion

Ce projet illustre une approche pratique de construction d'un assistant medical informationnel, en s'appuyant sur:

- la collecte et la preparation de donnees
- le RAG local
- la recherche web
- la generation de reponses avec `gpt-4o`

Pour un PFA, la valeur du projet reside autant dans l'architecture complete que dans l'interface finale et la logique de fiabilite mise en place.
