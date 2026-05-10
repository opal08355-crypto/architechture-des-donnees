# Presentation Plan

## 1. Introduction

- contexte: explosion des donnees medicales en ligne
- probleme: informations dispersees, bruit, manque de structure
- objectif: construire un assistant medical informationnel hybride

## 2. Architecture

- scraping / collecte
- nettoyage / transformation
- indexation ChromaDB
- pipeline RAG local
- recherche web
- generation avec gpt-4o
- interface conversationnelle

## 3. Choix techniques

- pourquoi FastAPI
- pourquoi ChromaDB
- pourquoi un pipeline hybride
- pourquoi des sources medicales filtrees

## 4. Demonstration

- cas local RAG
- cas web
- cas multilingue
- cas suivi conversationnel
- cas multi-chat

## 5. Valeur du projet

- data engineering + IA
- architecture complete
- application concretement exploitable
- souci de fiabilite et de transparence

## 6. Limites

- couverture partielle de la base locale
- dependance internet pour le web search
- systeme informationnel et non diagnostique

## 7. Perspectives

- enrichissement de la base documentaire
- evaluation automatique de la qualite des reponses
- persistance serveur des conversations
- tableau de bord analytique
