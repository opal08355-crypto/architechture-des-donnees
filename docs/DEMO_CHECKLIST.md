# Demo Checklist

## Avant la soutenance

- Verifier que la cle OpenAI fonctionne
- Lancer `uvicorn chatbot.app:app --reload`
- Ouvrir `http://127.0.0.1:8000`
- Faire `Ctrl+F5`
- Verifier que le badge API est en etat connecte
- Verifier qu'un nouveau chat peut etre cree
- Verifier que la langue suit la langue de la question

## Parcours de demo recommande

### 1. Montrer l'interface

- multi-chat
- memoire conversationnelle
- affichage des sources
- niveau de confiance

### 2. Montrer un cas local RAG

Question:

```text
What causes diabetes?
```

Attendu:

- mode `Local RAG`
- source locale MedlinePlus
- reponse structuree

### 3. Montrer un cas web

Question:

```text
What are the causes of acne?
```

Attendu:

- mode `Web search`
- sources web fiables
- reponse structuree

### 4. Montrer la memoire

Questions:

```text
What are the causes of acne?
ok share the guidance you talked about it
```

Attendu:

- le systeme reste sur `acne`
- il ne bascule pas vers une maladie locale non pertinente

### 5. Montrer la langue

Question:

```text
Comment gerer l hypertension arterielle ?
```

Attendu:

- reponse en francais

## Points a verbaliser

- pourquoi un pipeline hybride est utile
- pourquoi les sources medicales sont filtrees
- pourquoi la memoire conversationnelle est importante
- pourquoi le chatbot n'est pas un systeme de diagnostic
