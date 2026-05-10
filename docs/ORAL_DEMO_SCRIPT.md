# Script De Demonstration Orale

Ce document vous donne une demonstration orale prete a presenter, minute par minute, pour une soutenance de 8 a 10 minutes.

## 0. Preparation Avant De Parler

Verifiez avant la demo:
- `docker compose up -d minio postgres zookeeper kafka airflow-init airflow-webserver airflow-scheduler`
- `uvicorn chatbot.app:app --reload`
- interface chatbot ouverte sur `http://127.0.0.1:8000`
- Airflow ouvert sur `http://127.0.0.1:8080`
- au moins un chat vide pret a l'emploi

## 1. Minute 0 a 1: Introduction

Phrase conseillee:

> Mon projet s'appelle `medical-bigdata-platform`. L'idee est de construire une plateforme complete qui collecte des donnees medicales depuis des sources fiables, les transforme dans une architecture Big Data, puis les exploite dans un assistant conversationnel intelligent.

Ce que vous montrez:
- le nom du projet
- la page du chatbot
- eventuellement le README si vous voulez commencer par l'architecture

## 2. Minute 1 a 2: Problematique

Phrase conseillee:

> Le probleme de depart est que les informations medicales sur le web sont nombreuses, heterogenes et parfois difficiles a exploiter rapidement. J'ai donc construit une chaine qui va du scraping jusqu'a la generation d'une reponse structuree avec sources.

Idees a verbaliser:
- donnees dispersees
- besoin de nettoyage
- besoin de fiabilite
- besoin d'une reponse claire pour l'utilisateur final

## 3. Minute 2 a 3: Architecture Globale

Phrase conseillee:

> Mon architecture suit un flux en plusieurs etapes: scraping, ingestion batch et streaming, stockage Data Lake, transformation Bronze/Silver/Gold, chargement analytique, puis exploitation dans un chatbot hybride.

Ce que vous pouvez montrer:
- [docs/PROJECT_STEP_BY_STEP.md](/c:/Users/user/medical-bigdata-platform/docs/PROJECT_STEP_BY_STEP.md:1)
- [docker-compose.yml](/c:/Users/user/medical-bigdata-platform/docker-compose.yml:1)

Points techniques a citer:
- `MinIO` pour le Data Lake
- `Kafka` pour le streaming
- `PostgreSQL` pour le warehouse
- `Airflow` pour l'orchestration batch
- `FastAPI` pour l'API
- `gpt-4o` pour la generation

## 4. Minute 3 a 4: Partie Data Engineering

Phrase conseillee:

> Le pipeline data commence par des scrapers Python qui extraient le titre, le contenu, la source et l'URL. Ensuite, les donnees brutes sont stockees en Bronze, nettoyees en Silver, puis agregees en Gold pour produire des indicateurs.

Fichiers a mentionner:
- [scraping/scraper.py](/c:/Users/user/medical-bigdata-platform/scraping/scraper.py:1)
- [kafka/producer.py](/c:/Users/user/medical-bigdata-platform/kafka/producer.py:1)
- [kafka/consumer.py](/c:/Users/user/medical-bigdata-platform/kafka/consumer.py:1)
- [spark/bronze_to_silver.py](/c:/Users/user/medical-bigdata-platform/spark/bronze_to_silver.py:1)
- [spark/silver_to_gold.py](/c:/Users/user/medical-bigdata-platform/spark/silver_to_gold.py:1)
- [spark/load_gold_to_postgres.py](/c:/Users/user/medical-bigdata-platform/spark/load_gold_to_postgres.py:1)

Ce qu'il faut dire:
- Bronze = brut
- Silver = nettoye, normalise, enrichi
- Gold = analytique

## 5. Minute 4 a 5: Orchestration Airflow

Phrase conseillee:

> Pour automatiser le pipeline batch, j'ai ajoute une DAG Airflow qui orchestre le scraping, les transformations Bronze vers Silver puis Silver vers Gold, et enfin le chargement dans PostgreSQL.

Montrez:
- [airflow/dags/pipeline_medical.py](/c:/Users/user/medical-bigdata-platform/airflow/dags/pipeline_medical.py:1)
- interface Airflow sur `http://127.0.0.1:8080`

Ce qu'il faut expliquer:
- Airflow pilote le batch horaire
- Kafka couvre la logique streaming
- cela respecte bien le besoin du sujet PDF

## 6. Minute 5 a 7: Demonstration Du Chatbot

### Cas 1: Local RAG

Question:

```text
What causes diabetes?
```

Phrase conseillee:

> Ici, la question trouve deja un bon contexte dans la base locale. Le systeme reste donc en mode `Local RAG`.

Attendu:
- mode `Local RAG`
- source MedlinePlus
- reponse structuree

### Cas 2: Web Search

Question:

```text
What are the causes of acne?
```

Phrase conseillee:

> Ici, comme le sujet n'est pas assez couvert localement, le systeme bascule automatiquement vers la recherche web avec des sources medicales filtrees.

Attendu:
- mode `Web search`
- sources fiables
- reponse structuree

### Cas 3: Memoire Conversationnelle

Question:

```text
ok share the guidance you talked about it
```

Phrase conseillee:

> Le systeme garde la memoire du sujet precedent. Il comprend donc qu'on parle encore de l'acne, au lieu de repartir sur un autre sujet.

Attendu:
- le sujet reste coherent
- pas de bascule vers une maladie non liee

### Cas 4: Multilingue

Question:

```text
Comment gerer l hypertension arterielle ?
```

Phrase conseillee:

> Ici, le systeme detecte la langue de la question et repond automatiquement en francais.

Attendu:
- reponse en francais
- structure claire

## 7. Minute 7 a 8: Valeur Du Projet

Phrase conseillee:

> La force du projet est qu'il ne s'agit pas seulement d'un chatbot. C'est une mini-plateforme complete qui combine data engineering, traitement analytique, orchestration et IA generative.

Points forts a citer:
- architecture de bout en bout
- combinaison local + web
- sources medicales fiables
- memoire conversationnelle
- interface multi-chat

## 8. Minute 8 a 9: Limites

Phrase conseillee:

> Comme tout projet realiste, il y a des limites. La qualite du RAG local depend de la qualite des donnees ingerees, et la recherche web depend d'un acces internet et d'une cle OpenAI valide.

Limites a citer:
- base locale encore enrichissable
- couverture documentaire incomplete
- chatbot informationnel, pas diagnostique
- dashboard analytique encore a etendre

## 9. Minute 9 a 10: Conclusion

Phrase conseillee:

> Pour conclure, ce projet montre comment construire une plateforme medicale intelligente allant du scraping jusqu'a la reponse utilisateur, avec une vraie logique d'architecture de donnees et une couche moderne d'IA.

Fin possible:

> Merci. Si vous voulez, je peux maintenant vous montrer soit l'orchestration Airflow, soit le fonctionnement du chatbot en temps reel.

## 10. Si Le Jury Pose Des Questions

### Pourquoi avoir choisi une architecture hybride local + web ?

Reponse courte:

> Le local garantit de la rapidite et de la maitrise sur les contenus, alors que le web permet de completer la couverture quand la base locale est insuffisante.

### Pourquoi Airflow et Kafka en meme temps ?

Reponse courte:

> Airflow est adapte a l'orchestration batch planifiee, alors que Kafka repond mieux au besoin d'ingestion streaming par evenements.

### Pourquoi ce n'est pas un simple chatbot ?

Reponse courte:

> Parce qu'il repose sur une vraie chaine de donnees: collecte, stockage, nettoyage, analytique, indexation, recuperation et generation.

### Pourquoi limiter les sources web ?

Reponse courte:

> Pour reduire le risque de reponses peu fiables et garder un niveau de confiance plus eleve sur les informations renvoyees.
