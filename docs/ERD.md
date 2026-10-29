# Articles module entity relationship diagram

This diagram and field list reflect the Django models in `apps/articles/models.py` and the custom user model in `apps/accounts/models.py`.

```mermaid
erDiagram
    ARTICLE_CATEGORY ||--o{ ARTICLE : categorizes
    USER ||--o{ ARTICLE : authors
    ARTICLE }o--o{ TAG : labeled_with

    ARTICLE_CATEGORY {
        bigint id PK
        varchar name UK
        varchar slug UK
        datetime created_at
        datetime updated_at
    }

    ARTICLE {
        bigint id PK
        varchar title
        varchar slug UK
        text summary
        text content
        varchar image
        bigint category_id FK
        uuid author_id FK
        varchar status
        datetime published_at "nullable"
        datetime created_at
        datetime updated_at
    }

    TAG {
        bigint id PK
        varchar name UK_CI
        varchar slug UK
        datetime created_at
        datetime updated_at
    }

    USER {
        uuid id PK
        varchar username
        varchar email UK_CI
        varchar role
        varchar bio "nullable"
        datetime created_at
        datetime updated_at
    }
```

`UK` means unique. `UK_CI` means case-insensitive uniqueness enforced by a database constraint. Django also supplies fields inherited from `AbstractUser`; only fields relevant to this module are shown for `USER`.

## Entities and fields

### Article

`Article` inherits `created_at` and `updated_at` from the abstract `TimeStamp` model. Its primary key is Django's default `BigAutoField` (`id`).

| Field | Model type / behavior |
|---|---|
| `title` | Required character field, max 200 characters. |
| `slug` | Unique slug, max 220 characters. Generated from the title and suffixed to avoid slug collisions; generated slugs are updated when the title is renamed. |
| `summary` | Optional text, blank allowed. |
| `content` | Required text. |
| `image` | Optional `ImageField`, stored below `MEDIA_ROOT/articles/`; database stores the relative file name. |
| `category` | Required foreign key to `ArticleCategory`, `on_delete=PROTECT`, reverse name `articles`. |
| `author` | Required foreign key to the configured user model, `on_delete=PROTECT`, reverse name `articles`. |
| `status` | Character field with `DRAFT` and `PUBLISHED` choices; defaults to `DRAFT`. |
| `published_at` | Nullable datetime, managed by API create/update publication behavior. |
| `tags` | Optional many-to-many relationship to `Tag`, reverse name `articles`. |

### ArticleCategory

`ArticleCategory` also inherits `created_at` and `updated_at`, and uses a `BigAutoField` primary key.

| Field | Model type / behavior |
|---|---|
| `name` | Required character field, max 100 characters, unique. |
| `slug` | Unique slug, max 120 characters, generated from the name and updated on rename when originally generated. |

One category may be referenced by many articles. Each article has exactly one category. `PROTECT` prevents deleting a category while related articles exist; the API reports this conflict as `409 CATEGORY_IN_USE`.

### Tag

`Tag` inherits the timestamps and uses a `BigAutoField` primary key.

| Field | Model type / behavior |
|---|---|
| `name` | Required character field, max 100 characters; a `Lower(name)` unique constraint prevents case-insensitive duplicate names. |
| `slug` | Unique slug, max 120 characters, generated from the name and updated on rename when originally generated. |

Tags and articles have a many-to-many relationship. Django maintains an implicit join table for `Article.tags`; the `Tag` model does not declare a separate association model. The API does not expose standalone Tag CRUD. Admins select existing tag slugs or create/reuse tag names as part of article creation and update.

### User

`Article.author` references `settings.AUTH_USER_MODEL`, which is `apps.accounts.User`. This custom user extends Django's `AbstractUser` and the `TimeStamp` model; its primary key is a UUID. The module uses the user's `username`, `id`, and `role` in API output and permissions. `role` has `admin` and `user` choices. `email` has case-insensitive uniqueness. A user may author many articles; an article has one author. `PROTECT` prevents deleting an author while their articles remain.

## Relationship summary

- **ArticleCategory 1 → many Article:** `Article.category_id` is a required foreign key.
- **User 1 → many Article:** `Article.author_id` is a required foreign key to the configured custom user.
- **Article many ↔ many Tag:** optional `Article.tags` relationship backed by Django's implicit join table.
- **Timestamp fields:** `Article`, `ArticleCategory`, and `Tag` inherit nullable `created_at` and `updated_at` datetime fields from `TimeStamp` (`auto_now_add` and `auto_now`, respectively).
