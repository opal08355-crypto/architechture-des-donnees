# Test Scenarios

## Scenarios fonctionnels

1. `What causes diabetes?`
Attendu: `local_rag`

2. `And how can it be prevented?`
Apres le scenario 1.
Attendu: suivi sur diabetes

3. `What are the causes of acne?`
Attendu: `web_search`

4. `yes sure`
Apres le scenario 3.
Attendu: suivi sur acne

5. `Comment gerer l hypertension arterielle ?`
Attendu: reponse en francais

6. `Quels sont les symptomes de l'asthme ?`
Attendu: local ou web selon qualite de la base

7. `Que signifie obesity dans un contexte medical ?`
Attendu: definition ou contexte adequat

8. `What is the treatment for flu?`
Attendu: reponse structuree avec sources

## Scenarios de robustesse

1. Question vide
Attendu: non envoi cote front

2. Cle OpenAI absente
Attendu: badge degrade, fallback local

3. Web indisponible
Attendu: pas de crash, fallback propre

4. Sujet absent localement
Attendu: pas de confusion avec une autre maladie
