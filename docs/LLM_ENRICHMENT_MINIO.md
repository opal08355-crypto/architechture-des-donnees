# LLM Enrichment Into MinIO Data Lake

This step enriches `silver` medical records with structured medical fields and stores them in `gold`.
It can also pull supplementary context from trusted medical websites before generating the final JSON enrichment.

## Pipeline Position

Current orchestration:

1. `scraping/scraper.py` -> Bronze bucket
2. `spark/bronze_to_silver.py` -> Silver bucket
3. `spark/llm_enrich_silver.py` -> Gold `llm_enriched/`
4. `spark/silver_to_gold.py` -> Gold analytics
5. `spark/load_gold_to_postgres.py` -> PostgreSQL warehouse

## Output Schema

Each enriched object contains:

- source fields: `title`, `content`, `source`, `url`, `language`, `category`, `content_length`
- LLM fields under `llm_enrichment`:
  - `disease`
  - `summary`
  - `key_symptoms`
  - `causes`
  - `treatments`
  - `medications`
  - `red_flags`
  - `contraindications`
  - `preventive_tips`
  - `confidence`
  - `language`
- metadata: `llm_method`, `llm_model`
- optional web metadata:
  - `web_context_query`
  - `web_context_used`
  - `web_context_method`
  - `web_sources`

## Environment Variables

- `LLM_ENRICH_MODEL` (default `gpt-4o`)
- `LLM_GOLD_PREFIX` (default `llm_enriched/`)
- `LLM_ENRICH_MAX_RECORDS` (`0` means all)
- `LLM_ENRICH_SKIP_EXISTING` (`true` to avoid rewriting)
- `LLM_ENRICH_INPUT_CHAR_LIMIT` (default `4500`)
- `LLM_ENRICH_USE_WEB_CONTEXT` (default `true`)
- `LLM_ENRICH_WEB_CHAR_LIMIT` (default `2500`)

## Run Manually

```powershell
venv\Scripts\activate
python spark\llm_enrich_silver.py
```

## Notes

- If no LLM client is configured, the script still runs with a heuristic fallback.
- For Azure OpenAI, the script reuses `USE_AZURE_OPENAI`, `AZURE_OPENAI_API_KEY`, and `AZURE_OPENAI_ENDPOINT`.
- When web context is enabled, the script supplements each article with trusted external medical context from the existing filtered web search layer.
- The article remains the primary source; web context is used only to complete missing fields or strengthen the enrichment.
