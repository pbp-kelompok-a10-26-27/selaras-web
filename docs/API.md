# Articles and Categories API

This document describes the endpoints currently wired in `config/urls.py` and `apps/articles/urls.py`. The API uses Django session authentication; send a valid session cookie for authenticated requests. Unsafe methods are protected by CSRF middleware. JSON requests should use `Content-Type: application/json`. Image uploads use `multipart/form-data` as described below.

## Permissions

| Endpoint/action | Anonymous visitor | Regular user | Admin |
|---|---|---|---|
| List articles and read a published article | Allowed | Allowed | Allowed |
| Read a draft article or filter list by status | Drafts are hidden | Drafts are hidden | Allowed |
| Create, update, delete articles | `401` | `403` | Allowed |
| List categories | `401` | Allowed | Allowed |
| Create, rename, delete categories | `401` | `403` | Allowed |

An inaccessible draft detail is returned as `404 ARTICLE_NOT_FOUND`, including for a regular user. The application defines an admin as an authenticated user whose role is `admin`.

## Articles

### Routes

| Method | Path | Access | Success |
|---|---|---|---|
| `GET` | `/api/articles/` | Public; non-admins see published articles only | `200` |
| `POST` | `/api/articles/` | Admin only | `201` |
| `GET` | `/api/articles/{slug}/` | Public; drafts are visible to admins only | `200` |
| `PUT` | `/api/articles/{slug}/` | Admin only; full replacement | `200` |
| `PATCH` | `/api/articles/{slug}/` | Admin only; partial update | `200` |
| `DELETE` | `/api/articles/{slug}/` | Admin only | `204` with empty body |

Slugs are generated from titles and made unique with a numeric suffix when needed. Renaming an article changes its slug if its slug was originally generated from the title. Clients should use the latest returned slug.

### List query parameters

All filters may be combined. The list is ordered by newest `published_at`, then descending article ID.

| Parameter | Behavior |
|---|---|
| `search` | Case-insensitive substring search across title, summary, and content. |
| `category` | Matches category slug or category name, case-insensitively. |
| `tag` | Matches one tag slug. An unknown slug returns `400 INVALID_QUERY_PARAMETER`. |
| `status` | Admin only: `DRAFT` or `PUBLISHED`. Defaults to `PUBLISHED`. Non-admins always receive published articles; this parameter is not applied to their results. An invalid value supplied by an admin returns `400 INVALID_QUERY_PARAMETER`. |
| `page` | Page number; defaults to `1`. Invalid values fall back to `1`; values below 1 are clamped to 1. Out-of-range pages use Django's last-page behavior. |
| `page_size` | Results per page; defaults to `20`, clamped to `1–100`. Invalid values fall back to `20`. |

Example: `GET /api/articles/?search=repair&category=lingkungan&tag=zero-waste&page=1&page_size=10`

Successful list response (`200`):

```json
{
  "results": [
    {
      "id": 42,
      "title": "Repair before replacing",
      "slug": "repair-before-replacing",
      "summary": "A short guide",
      "image": "http://localhost:8000/media/articles/cover.png",
      "tags": [{"name": "Zero Waste", "slug": "zero-waste"}],
      "category": {"name": "Lingkungan", "slug": "lingkungan"},
      "author": {"id": "a2b166ba-9990-4dda-a26f-cf9690c97a7f", "username": "admin"},
      "status": "PUBLISHED",
      "published_at": "2026-10-28T09:30:00+00:00"
    }
  ],
  "pagination": {"page": 1, "page_size": 10, "total_items": 1, "total_pages": 1}
}
```

The image value is an absolute media URL or `null`. Timestamps are ISO 8601 strings or `null`.

### Article detail

`GET /api/articles/{slug}/` returns the same article fields as the list item, plus `content`. A missing article, or a draft hidden from the requester, returns `404`:

```json
{"error": {"code": "ARTICLE_NOT_FOUND", "message": "Artikel tidak ditemukan."}}
```

### Create an article

Send JSON to `POST /api/articles/`. Required fields are `title`, `content`, and integer `category_id`. Optional fields are `summary` (defaults to an empty string), `status` (`DRAFT` by default, or `PUBLISHED`), `tags` (an array of existing tag slugs), and `new_tags` (an array of tag names to create or reuse). Only admins can create articles and new tags. There are no standalone Tag endpoints.

```json
{
  "title": "Repair before replacing",
  "content": "Full article text.",
  "summary": "A short guide",
  "category_id": 3,
  "status": "DRAFT",
  "tags": ["zero-waste"],
  "new_tags": ["Repair"]
}
```

Success is `201`:

```json
{
  "message": "Artikel berhasil dibuat.",
  "article": {
    "id": 42,
    "title": "Repair before replacing",
    "slug": "repair-before-replacing",
    "status": "DRAFT",
    "image": null,
    "tags": [
      {"name": "Repair", "slug": "repair"},
      {"name": "Zero Waste", "slug": "zero-waste"}
    ]
  }
}
```

### Update an article and publication time

`PATCH` accepts any subset of `title`, `summary`, `content`, `category_id`, `status`, `tags`, and `new_tags`. Omitting `tags` preserves associations; sending `"tags": []` clears existing tags. `new_tags` are added to the supplied existing tag slugs.

`PUT` requires `title`, `content`, `category_id`, and `status`; omitted `summary` becomes empty and omitted `tags` clears existing associations. Image is optional and is preserved if no new image file is sent.

When an article is created as published, `published_at` is set. Updating a published article without changing its status preserves its timestamp. Changing to draft clears it; publishing or republishing sets a new timestamp. The update response includes `published_at`, `image`, and `tags`.

### Upload or replace an image

To upload an image, send the article fields as `multipart/form-data` and include the binary `image` field. For multipart requests, `tags` and `new_tags` must be JSON-encoded array strings (for example, `tags=["zero-waste"]`, `new_tags=["Repair"]`). Do not send an `image` URL in JSON; the API expects an uploaded file.

Example with curl (authenticated admin session and CSRF token required):

```sh
curl -X POST http://localhost:8000/api/articles/ \
  -H 'Cookie: sessionid=SESSION; csrftoken=TOKEN' \
  -H 'X-CSRFToken: TOKEN' \
  -F 'title=Repair before replacing' \
  -F 'content=Full article text.' \
  -F 'category_id=3' \
  -F 'status=DRAFT' \
  -F 'tags=[]' \
  -F 'new_tags=["Repair"]' \
  -F 'image=@cover.png;type=image/png'
```

The same upload format can be sent with `PATCH` or `PUT` to an article detail path. Current validation accepts JPEG, PNG, WEBP, and GIF with a maximum size of 5 MiB and 20 megapixels. Files are stored under `MEDIA_ROOT/articles/` and served using `MEDIA_URL` in development when `DEBUG=True`; production media serving must be configured by the deployment. Sending no file leaves an existing image unchanged; there is no API field to explicitly clear an image.

### Delete an article

`DELETE /api/articles/{slug}/` returns an empty `204` response. Unknown slugs return `404 ARTICLE_NOT_FOUND`.

## Categories

### Routes

| Method | Path | Access | Success |
|---|---|---|---|
| `GET` | `/api/categories/` | Authenticated users | `200` |
| `POST` | `/api/categories/` | Admin only | `201` |
| `PATCH` | `/api/categories/{slug}/` | Admin only; renames the category | `200` |
| `DELETE` | `/api/categories/{slug}/` | Admin only | `204` with empty body |

Category create and update bodies are JSON. Create requires `name`; update accepts only `name`. Slugs are generated from category names and may change after a rename. Duplicate names are rejected case-insensitively with `400 VALIDATION_ERROR`.

Create request and response:

```http
POST /api/categories/
Content-Type: application/json
```

```json
{"name": "Lingkungan"}
```

```json
{"id": 3, "name": "Lingkungan", "slug": "lingkungan"}
```

List response:

```json
{"results": [{"id": 3, "name": "Lingkungan", "slug": "lingkungan"}]}
```

Rename uses `PATCH /api/categories/lingkungan/` with `{"name":"Bumi"}` and returns the category object in the same shape as create. Deleting a category referenced by an article returns `409 CATEGORY_IN_USE`; deleting an unused category returns empty `204`. A missing category returns `404 CATEGORY_NOT_FOUND`.

## Errors and method restrictions

JSON errors use this envelope; field validation may include `details`:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Nama kategori wajib diisi.",
    "details": {"name": ["Nama kategori wajib diisi."]}
  }
}
```

Common responses include:

| Status | Meaning / example code |
|---|---|
| `400` | Invalid JSON, validation, unknown tag filter, or invalid admin status (`INVALID_JSON`, `VALIDATION_ERROR`, `INVALID_QUERY_PARAMETER`) |
| `401` | Login required (`AUTHENTICATION_REQUIRED`) |
| `403` | Authenticated non-admin mutation or CSRF rejection (`PERMISSION_DENIED`) |
| `404` | Missing article/category or hidden draft (`ARTICLE_NOT_FOUND`, `CATEGORY_NOT_FOUND`) |
| `405` | Unsupported method (`METHOD_NOT_ALLOWED`); response includes `Allow` |
| `409` | Deleting an in-use category (`CATEGORY_IN_USE`) |
| `500` | Unexpected server failure (`INTERNAL_ERROR`); internal exception details are logged, not returned |

## Legacy article list route

`GET /articles/api/articles/` is a legacy read-only endpoint. It returns `{"results": [...]}` containing published articles, with title, slug, summary, image, tags, category name, author username, and publication time. It does not provide search, filters, or pagination. Other methods return `405 METHOD_NOT_ALLOWED`. Prefer `/api/articles/` for current integrations.
