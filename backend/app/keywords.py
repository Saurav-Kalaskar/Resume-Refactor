import re
from typing import List, Set

TECH_KEYWORDS = {
    # Languages
    "python", "java", "javascript", "typescript", "c", "c++", "c#", "go", "rust", "kotlin",
    "swift", "scala", "r", "matlab", "dart", "julia", "vba",
    # Frontend
    "react", "reactjs", "next.js", "vue", "angular", "svelte", "html", "css", "sass", "scss",
    "tailwind", "bootstrap", "material-ui", "mui", "chakra-ui", "figma",
    # Backend
    "fastapi", "flask", "django", "spring", "spring boot", "nodejs", "node.js", "express",
    "nestjs", "asp.net", "graphql", "rest", "api", "grpc", "kafka", "rabbitmq",
    # Cloud & DevOps
    "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s", "terraform",
    "pulumi", "helm", "jenkins", "github actions", "gitlab ci", "circleci", "travisci",
    "prometheus", "grafana", "datadog", "splunk", "elk", "opentelemetry",
    # Databases
    "postgresql", "postgres", "mysql", "mongodb", "redis", "elasticsearch", "cassandra",
    "dynamodb", "neo4j", "sqlite", "oracle", "sql server", "snowflake", "bigquery",
    # ML/Data
    "tensorflow", "pytorch", "keras", "scikit-learn", "sklearn", "pandas", "numpy",
    "matplotlib", "seaborn", "plotly", "d3.js", "tableau", "powerbi", "mlflow",
    "huggingface", "openai", "langchain", "llamaindex", "rag", "vector db", "pinecone",
    "weaviate", "chroma",
    # Mobile
    "react native", "flutter", "ionic", "cordova", "capacitor",
    # Other
    "microservices", "serverless", "lambda", "event-driven", "ci/cd", "cicd",
    "agile", "scrum", "kanban", "jira", "confluence", "git", "github", "gitlab",
    "oauth", "jwt", "sso", "auth0", "okta", "encryption", "cryptography",
}


def extract_keywords(jd_text: str) -> List[str]:
    """Extract technical keywords from job description."""
    keywords: Set[str] = set()

    # Normalize
    text_lower = jd_text.lower()

    # Direct matching against tech keywords
    for keyword in TECH_KEYWORDS:
        if keyword in text_lower or keyword.replace(" ", "") in text_lower.replace(" ", ""):
            keywords.add(keyword)

    # Extract with regex patterns
    patterns = [
        r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\s*(?:\([^)]*\))?\s*(?:framework|library|platform|tool|service|api|sdk)\b',
        r'\b[A-Z][a-z]*\.js\b',
        r'\b[A-Z]{2,}(?:\.[A-Z]{2,})?\b',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, jd_text, re.IGNORECASE)
        keywords.update(m.lower() for m in matches)

    # Extra: split compounds and add parts
    result = set()
    for kw in keywords:
        result.add(kw)
        if " " in kw:
            for part in kw.split():
                if len(part) > 2:
                    result.add(part)

    return sorted([k for k in result if len(k) > 2])


def bold_keywords_in_text(text: str, keywords: List[str]) -> str:
    """Wrap JD-matching keywords in \textbf{}."""
    result = text
    # Sort by length descending to avoid partial replacements
    sorted_kws = sorted(set(keywords), key=len, reverse=True)

    for kw in sorted_kws:
        # Escape regex special chars
        escaped = re.escape(kw)
        # Match whole words, case-insensitive
        pattern = rf'\b({escaped})\b'
        result = re.sub(pattern, r'\\textbf{\1}', result, flags=re.IGNORECASE)

    return result
