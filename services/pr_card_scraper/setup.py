from setuptools import setup, find_packages

setup(
    name="pr-card-scraper",
    version="1.0.0",
    description="Mahabhumi Bhulekh PR Card Scraper Service",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.115.0",
        "uvicorn[standard]>=0.30.0",
        "playwright>=1.40.0",
        "pytesseract>=0.3.10",
        "Pillow>=10.0.0",
        "pydantic>=2.9.0",
        "pydantic-settings>=2.7.0",
        "httpx>=0.27.0",
        "psycopg2-binary>=2.9.0",
        "easyocr>=1.7.0",
        "selenium>=4.0.0",
        "webdriver-manager>=4.0.0",
        "unidecode>=1.3.0",
    ],
)
