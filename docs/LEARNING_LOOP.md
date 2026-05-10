3# Learning Loop (Engineering Student)

Ce projet peut maintenant s'ameliorer en continu via une boucle simple:

1. Interaction: chaque reponse du chatbot est enregistree dans `chatbot/learning_data/interactions.jsonl`.
2. Feedback: vous envoyez une note `1..5` (et optionnellement une reponse corrigee) vers `POST /feedback`.
3. Selection: seules les interactions avec note >= seuil sont retenues.
4. Export dataset: `POST /api/learning/export` ou script `chatbot/export_finetune_dataset.py`.
5. Fine-tuning externe: utilisez le JSONL exporte pour entrainer un modele compatible.

## Profil pedagogique

Le niveau cible est configurable avec:

`CHATBOT_LEARNER_PROFILE=Engineering Student`

Ce profil est injecte dans les prompts pour adapter le niveau d'explication.

## Endpoints utiles

- `GET /api/learning/summary`: resume des interactions/feedback
- `POST /feedback`: enregistrer la qualite d'une reponse
- `POST /api/learning/export`: exporter un dataset JSONL

Exemple feedback:

```json
{
  "turn_id": "turn-xxxxxxxxxxxxxxxx",
  "rating": 5,
  "note": "Bonne reponse, claire et utile",
  "preferred_answer": ""
}
```

Exemple export:

```json
{
  "output_path": "chatbot/learning_data/finetune_dataset.jsonl",
  "min_rating": 4
}
```

## Script CLI

```powershell
python chatbot\export_finetune_dataset.py --output chatbot\learning_data\finetune_dataset.jsonl --min-rating 4
```
