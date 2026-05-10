SELECT source_name, article_count
FROM articles_by_source
ORDER BY article_count DESC, source_name ASC;

SELECT category_name, article_count
FROM articles_by_category
ORDER BY article_count DESC, category_name ASC;

SELECT keyword, frequency
FROM top_keywords
ORDER BY frequency DESC, keyword ASC
LIMIT 20;

SELECT total_articles, avg_content_length
FROM global_stats;
