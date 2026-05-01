# OCR Service

Service for document text extraction and service-specific registration parsing.

## Endpoints

- POST `/extract/text`
  - Multipart: `file`
  - Form fields:
    - `strategy`: `auto` | `pdf_text` | `ocr` (default: `auto`)
    - `lang`: Tesseract language code (default: `eng`)
  - Returns: `{ ok, text, usedOcr, pages, mime, strategyUsed }`

- POST `/ls/extract-registration`
  - Multipart: `file`
  - Form fields: `strategy` (default `auto`), `lang` (default `eng`)
  - Returns: `{ ok, registrationNumber, usedOcr }` or `{ ok:false, reason, message, sampleText }`

- POST `/architect/extract-registration`
  - Multipart: `file`
  - Form fields: `strategy` (default `auto`), `lang` (default `eng`)
  - Returns: `{ ok, registrationNumber, usedOcr }` or `{ ok:false, reason, message, sampleText }`

- POST `/extract/registration-number`
  - Multipart: `file`
  - Form fields:
    - `certificate_type`: `LS` or `CA`
    - `strategy` (default `auto`), `lang` (default `eng`)
  - Returns: `{ ok, registrationNumber, usedOcr }` or `{ ok:false, reason, message, sampleText }`

## Limits

- Allowed content types: `application/pdf`, `image/jpeg`, `image/jpg`, `image/png`, `image/webp`
- Max file size: 15 MB

## Local Dev

```bash
uv sync
uv run python -m services.ocr_service.main
# http://localhost:8009/health
```
