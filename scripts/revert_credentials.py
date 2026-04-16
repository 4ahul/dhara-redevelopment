import os

files_to_update = [
    "docker-compose.yml",
    ".env",
    "services/orchestrator/.env",
    "services/rag_service/.env",
    "services/orchestrator/core/config.py",
    "services/pr_card_scraper/core/__init__.py",
    "services/orchestrator/alembic.ini"
]

# Reverting ONLY credentials/db-names to redevelopment to match existing container data
# while keeping dhara_net and Dhara AI names elsewhere.
replacements = {
    "dhara:dhara": "redevelopment:redevelopment",
    "POSTGRES_USER=dhara": "POSTGRES_USER=redevelopment",
    "POSTGRES_PASSWORD=dhara": "POSTGRES_PASSWORD=redevelopment",
    "POSTGRES_DB=dhara": "POSTGRES_DB=redevelopment",
    "@postgres:5432/dhara": "@postgres:5432/redevelopment",
    "@localhost:5432/dhara": "@localhost:5432/redevelopment",
    "@127.0.0.1:5432/dhara": "@127.0.0.1:5432/redevelopment",
    "pg_isready -U dhara": "pg_isready -U redevelopment"
}

for file_path in files_to_update:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Reverted {file_path}")
        else:
            print(f"No changes for {file_path}")
    else:
        print(f"File not found: {file_path}")
