CREATE TABLE IF NOT EXISTS articles_by_source (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(255),
    article_count INT
);

CREATE TABLE IF NOT EXISTS articles_by_category (
    id SERIAL PRIMARY KEY,
    category_name VARCHAR(255),
    article_count INT
);

CREATE TABLE IF NOT EXISTS top_keywords (
    id SERIAL PRIMARY KEY,
    keyword VARCHAR(255),
    frequency INT
);

CREATE TABLE IF NOT EXISTS global_stats (
    id SERIAL PRIMARY KEY,
    total_articles INT,
    avg_content_length FLOAT
);