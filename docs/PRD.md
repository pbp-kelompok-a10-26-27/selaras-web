# SELARAS — Repository & Development PRD

> **Document Type:** Repository Development Specification
> **Project:** SELARAS — Platform Membangun Kebiasaan Hidup Berkelanjutan
> **Architecture:** Django Monolith + Django Templates + Tailwind CSS
> **Status:** Development Specification
> **Primary Language:** Bahasa Indonesia
> **Repository:** SELARAS Backend/Web Application

---

# 1. Purpose

This document defines the technical and development standards that must be followed when developing the SELARAS repository.

This document focuses specifically on:

* Repository architecture
* Django application boundaries
* Shared/core architecture
* Module responsibilities
* Database/model ownership
* URL and API conventions
* External API integration
* Authentication and authorization
* HTML/template conventions
* Tailwind CSS conventions
* Branching strategy
* Commit conventions
* Pull Request rules
* Push rules
* CI/CD requirements
* Testing requirements
* Environment configuration
* Code quality standards
* Documentation requirements
* Definition of Done

This document is intended to keep development consistent across all contributors and modules.

---

# 2. Technology Stack

| Layer                      | Technology                                             |
| -------------------------- | ------------------------------------------------------ |
| Backend                    | Django                                                 |
| Backend API                | Django REST Framework, when API endpoints are required |
| Frontend                   | Django Templates                                       |
| Styling                    | Tailwind CSS                                           |
| Database                   | PostgreSQL                                             |
| Authentication             | Django Authentication                                  |
| Authorization              | Django Groups + Permissions                            |
| External Food API          | Open Food Facts                                        |
| External Weather API       | Open-Meteo                                             |
| Static Asset Build         | Tailwind CSS                                           |
| Testing                    | Django Test Framework / pytest if adopted              |
| Production Server          | Gunicorn                                               |
| Web Server / Reverse Proxy | Deployment-dependent                                   |
| Environment Configuration  | `.env`                                                 |
| Version Control            | Git + GitHub                                           |

---

# 3. Architecture

SELARAS uses a **modular Django monolith**.

The application is deployed as one Django project, but its business domains are separated into independent Django applications.

```text
                    SELARAS
                       │
             ┌─────────┴─────────┐
             │       config      │
             │ Django project    │
             │ settings / URLs   │
             └─────────┬─────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
      core          accounts       business apps
        │              │              │
        │              │       ┌──────┼─────────────┐
        │              │       │      │      │       │
        │              │   articles challenge feed donations helpdesk
        │              │
        └──────────────┴──────────────────────────────┘
```

## 3.1 Architectural Principles

1. Each Django app represents a **business domain**, not a page.
2. Each app owns its own:

   * Models
   * Forms
   * Views
   * URLs
   * Admin configuration
   * Tests
   * Domain-specific permissions
   * Domain-specific services
3. Shared infrastructure belongs in `core`.
4. Authentication and user identity belong in `accounts`.
5. Business logic must not be unnecessarily placed inside templates.
6. Views should orchestrate requests rather than contain large amounts of business logic.
7. External API communication must be isolated from models and templates.
8. Cross-module dependencies must be minimized.
9. Database models must represent actual business entities rather than UI screens.
10. Reusable code should only be moved to `core` when it is genuinely shared.

---

# 4. Repository Structure

The repository MUST follow this structure unless there is an explicit architectural decision documented in the repository.

```text
selaras/
│
├── apps/
│   │
│   ├── core/
│   │   ├── migrations/
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── mixins.py
│   │   ├── decorators.py
│   │   ├── constants.py
│   │   ├── validators.py
│   │   ├── utils.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── accounts/
│   │   ├── migrations/
│   │   ├── templates/accounts/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── forms.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── articles/
│   │   ├── migrations/
│   │   ├── templates/articles/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── forms.py
│   │   ├── permissions.py
│   │   ├── services.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── challenges/
│   │   ├── migrations/
│   │   ├── templates/challenges/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── forms.py
│   │   ├── permissions.py
│   │   ├── services.py
│   │   ├── weather.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── feed/
│   │   ├── migrations/
│   │   ├── templates/feed/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── forms.py
│   │   ├── permissions.py
│   │   ├── services.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   ├── donations/
│   │   ├── migrations/
│   │   ├── templates/donations/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── forms.py
│   │   ├── permissions.py
│   │   ├── services.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   │
│   └── helpdesk/
│       ├── migrations/
│       ├── templates/helpdesk/
│       ├── tests/
│       ├── models.py
│       ├── forms.py
│       ├── permissions.py
│       ├── services.py
│       ├── views.py
│       ├── urls.py
│       ├── admin.py
│       └── apps.py
│
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── templates/
│   ├── base.html
│   ├── partials/
│   │   ├── navbar.html
│   │   ├── footer.html
│   │   ├── messages.html
│   │   ├── pagination.html
│   │   └── modal.html
│   └── errors/
│       ├── 400.html
│       ├── 403.html
│       ├── 404.html
│       └── 500.html
│
├── static/
│   ├── src/
│   │   ├── input.css
│   │   └── app.js
│   ├── css/
│   │   └── output.css
│   ├── js/
│   │   ├── main.js
│   │   ├── modal.js
│   │   └── toast.js
│   └── images/
│
├── media/
│   ├── articles/
│   ├── posts/
│   ├── donations/
│   └── avatars/
│
├── fixtures/
│
├── docs/
│   ├── ERD.md
│   ├── API.md
│   └── architecture.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── cd.yml
│
├── manage.py
├── package.json
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
├── README.md
└── PRD.md
```

---

# 5. Directory Responsibilities

## 5.1 `apps/`

Contains all Django applications.

No business logic should be implemented directly under `apps/` outside a specific Django application.

---

# 6. `core/`

`core` contains functionality shared across multiple applications.

## 6.1 Responsibilities

`core` MAY contain:

* Abstract base models
* Shared permissions
* Shared decorators
* Shared mixins
* Global constants
* Shared validators
* Generic utility functions
* Cross-cutting infrastructure

Example:

```python
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

## 6.2 `core/models.py`

Only models that are genuinely shared across multiple domains belong here.

Examples:

* `TimeStampedModel`
* `AuditLog`, if implemented globally

Business models such as `Article`, `Post`, `Challenge`, or `Donation` MUST NOT be placed here.

## 6.3 `core/permissions.py`

Contains global authorization helpers.

Examples:

```python
is_admin(user)
is_authenticated_user(user)
```

Domain-specific permissions MUST remain inside their respective applications.

Example:

```text
core/permissions.py
    admin_required

feed/permissions.py
    can_edit_post

donations/permissions.py
    can_verify_donation
```

## 6.4 `core/constants.py`

Contains shared constants that have meaning across the application.

Examples:

```python
ROLE_ADMIN = "ADMIN"
ROLE_USER = "USER"
```

Status values that belong only to a specific domain should remain in that domain.

For example:

```text
donations/constants.py
challenges/constants.py
helpdesk/constants.py
```

if the constants become sufficiently large.

---

# 7. `accounts/`

Responsible for user identity and authentication.

## Responsibilities

* Custom User model
* Registration
* Login/logout
* Password management
* Profile
* User-related forms
* Authentication-related views
* User administration

The project MUST define its custom user model at the beginning of development if customization is expected.

Example:

```python
class User(AbstractUser):
    ...
```

Set:

```python
AUTH_USER_MODEL = "accounts.User"
```

before creating production data.

## Role Management

Roles should use Django's authorization system.

Recommended roles:

```text
Admin
User
```

Django Groups should be preferred over hard-coded role checks throughout business modules.

---

# 8. `articles/`

Responsible for Artikel & Edukasi.

## Core functionality

### User

* Browse articles
* Search articles
* Filter articles
* View article details
* View article categories

### Admin

* Create article
* Edit article
* Delete article
* Publish/unpublish article
* Manage categories

## External integration

Open Food Facts is used for relevant food/consumption content.

External API logic MUST NOT be placed directly inside:

```text
models.py
views.py
templates/
```

Use:

```text
articles/services.py
```

or a dedicated integration module if the integration grows.

---

# 9. `challenges/`

Responsible for Challenge functionality.

## Core functionality

* Browse challenges
* View challenge details
* Join challenge
* Track progress
* Record daily progress
* Calculate completion
* Track streaks
* Award badges
* View user's challenge history
* Admin CRUD for challenges

## External integration

Open-Meteo is used for outdoor/weather-related challenge suggestions.

The integration should be isolated in:

```text
challenges/weather.py
```

Business orchestration should remain in:

```text
challenges/services.py
```

The application should not call Open-Meteo directly from templates.

---

# 10. `feed/`

Responsible for user-generated posts.

## Core functionality

* Create post
* View posts
* Edit own post
* Delete own post
* Like/unlike
* Comment
* View post details
* Moderation

## Ownership rule

A normal user may only modify or delete their own post unless the user has moderation/admin permissions.

Example:

```python
def can_edit_post(user, post):
    return (
        post.author == user
        or user.is_staff
    )
```

The exact implementation should use the project's authorization conventions.

---

# 11. `donations/`

Responsible for environmental campaigns and donations.

## Core functionality

### Campaign

* Create campaign
* Edit campaign
* Publish campaign
* Track campaign target
* Track campaign progress
* Close campaign

### Donation

* Submit donation
* View donation
* View donation history
* Upload proof if required
* Verification
* Approval/rejection

## Donation lifecycle

```text
PENDING
   │
   ├── APPROVED
   │
   └── REJECTED
```

Only `APPROVED` donations should contribute to campaign progress unless another explicit business rule is documented.

## Payment gateway

No payment gateway should be implemented unless explicitly added to the project requirements.

The initial implementation may use a manual donation-record and verification workflow.

---

# 12. `helpdesk/`

Responsible for Help Desk / Customer Service.

## Core functionality

* Create ticket
* View own tickets
* View ticket details
* Add ticket response
* Admin/support response
* Update status
* Close ticket

## Ticket lifecycle

Recommended:

```text
OPEN
  │
  ▼
IN_PROGRESS
  │
  ▼
RESOLVED
  │
  ▼
CLOSED
```

Transitions must be enforced by backend logic.

---

# 13. Model Ownership Rules

Every persistent model MUST have one clear owning application.

Example:

| Model                  | Owner        |
| ---------------------- | ------------ |
| User                   | `accounts`   |
| Profile                | `accounts`   |
| Article                | `articles`   |
| ArticleCategory        | `articles`   |
| Challenge              | `challenges` |
| ChallengeParticipation | `challenges` |
| ChallengeProgress      | `challenges` |
| Badge                  | `challenges` |
| Post                   | `feed`       |
| Comment                | `feed`       |
| Like                   | `feed`       |
| Campaign               | `donations`  |
| Donation               | `donations`  |
| Ticket                 | `helpdesk`   |
| TicketMessage          | `helpdesk`   |

Do not duplicate the same business entity in multiple applications.

---

# 14. Cross-App Dependency Rules

Applications may depend on:

```text
core
accounts
```

when necessary.

Business applications should avoid unnecessary circular dependencies.

Preferred:

```text
articles ──────► accounts
articles ──────► core

feed ──────────► accounts
feed ──────────► core

donations ─────► accounts
donations ─────► core
```

Avoid:

```text
articles ─────► feed
feed ─────────► articles
```

unless there is a documented architectural reason.

When two modules need to communicate, prefer:

* Foreign keys
* Service functions
* Explicit domain interfaces
* Signals only when appropriate

Avoid hidden cross-app coupling.

---

# 15. Service Layer Rules

Complex business logic MUST NOT be placed entirely inside views.

Use:

```text
services.py
```

for operations involving multiple business steps.

Example:

```python
def complete_challenge(participation, date):
    ...
    update_progress(...)
    calculate_streak(...)
    check_badges(...)
```

Views should primarily:

```text
Request
   ↓
Validate input
   ↓
Call service
   ↓
Return response/template
```

Do not create a `services.py` function merely to wrap a single model query without providing meaningful domain behavior.

---

# 16. Forms

Django Forms / ModelForms should be used for server-side form validation.

Rules:

1. User input MUST be validated server-side.
2. HTML validation is supplementary only.
3. Forms should handle input validation.
4. Business state transitions should be handled by services/domain logic.
5. Views should not manually duplicate validation logic.

Example:

```text
forms.py
    field validation

services.py
    business rules

models.py
    database constraints
```

---

# 17. URL Conventions

## 17.1 General rules

URLs should use lowercase kebab-case or lowercase nouns consistently.

Recommended:

```text
/articles/
/articles/<slug>/
/articles/create/
/articles/<slug>/edit/

/challenges/
/challenges/<slug>/
/challenges/<id>/join/

/feed/
/feed/create/
/feed/<id>/

/donations/
/donations/campaigns/
/donations/campaigns/<id>/
/donations/history/

/helpdesk/
/helpdesk/tickets/
/helpdesk/tickets/<id>/
```

Avoid:

```text
/GetArticles/
/articlePage/
/doCreateArticle/
```

## 17.2 URL Naming

Django URL names should use:

```text
<app>:<action>
```

Example:

```python
app_name = "articles"

path("", views.article_list, name="list")
path("<slug:slug>/", views.article_detail, name="detail")
path("create/", views.article_create, name="create")
```

Usage:

```django
{% url 'articles:detail' article.slug %}
```

---

# 18. API Contract

SELARAS is primarily a Django Template application.

APIs should therefore be introduced only where they provide a clear architectural benefit, such as:

* AJAX/HTMX interactions
* Asynchronous UI updates
* External integration endpoints
* Future mobile/frontend clients
* Structured machine-to-machine communication

---

# 19. API Naming Convention

When REST APIs are required:

```text
/api/v1/<resource>/
```

Examples:

```text
/api/v1/articles/
/api/v1/articles/<id>/
/api/v1/challenges/
/api/v1/challenges/<id>/progress/
/api/v1/feed/posts/
/api/v1/donations/
/api/v1/helpdesk/tickets/
```

Use plural resource names.

Preferred:

```text
/articles/
/posts/
/challenges/
/donations/
/tickets/
```

Avoid verb-based URLs such as:

```text
/getArticles/
/createPost/
/deleteDonation/
```

---

# 20. HTTP Methods

| Method | Purpose                                   |
| ------ | ----------------------------------------- |
| GET    | Retrieve resource(s)                      |
| POST   | Create resource / execute explicit action |
| PUT    | Full replacement                          |
| PATCH  | Partial update                            |
| DELETE | Delete resource                           |

Use the method semantics consistently.

---

# 21. API Response Convention

Successful collection:

```json
{
  "data": [
    {}
  ]
}
```

Successful single resource:

```json
{
  "data": {}
}
```

Successful action:

```json
{
  "message": "Operation successful.",
  "data": {}
}
```

Error:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request.",
    "details": {}
  }
}
```

The exact response structure must remain consistent throughout the API.

---

# 22. API Status Codes

Use standard HTTP status codes.

| Status | Usage                            |
| ------ | -------------------------------- |
| `200`  | Successful retrieval/update      |
| `201`  | Resource created                 |
| `204`  | Successful deletion/no content   |
| `400`  | Invalid request                  |
| `401`  | Unauthenticated                  |
| `403`  | Unauthorized                     |
| `404`  | Resource not found               |
| `409`  | Resource/state conflict          |
| `422`  | Validation error when applicable |
| `429`  | Rate limited                     |
| `500`  | Unexpected server error          |

Do not return `200` for an operation that actually failed.

---

# 23. API Pagination

Collection endpoints should use pagination when the result can grow significantly.

Example:

```text
/api/v1/articles/?page=2&page_size=20
```

Response:

```json
{
  "data": [],
  "pagination": {
    "page": 2,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

Maximum page size must be enforced server-side.

---

# 24. API Filtering and Searching

Use query parameters.

Example:

```text
/api/v1/articles/?category=food
/api/v1/articles/?search=plastic
/api/v1/articles/?category=food&search=plastic
```

Do not encode filters into custom path segments unless the resource hierarchy requires it.

---

# 25. API Authentication

Authenticated API endpoints MUST verify the current Django user.

Unauthenticated endpoints must be explicitly documented.

Never trust:

```json
{
  "user_id": 123
}
```

as the sole source of identity for authenticated operations.

The authenticated request context must determine the acting user.

---

# 26. Authorization Rules

Authorization must be enforced server-side.

Frontend hiding is not authorization.

For example:

```text
UI hides "Delete"
        ↓
NOT sufficient
        ↓
Backend checks ownership/permission
        ↓
Delete allowed/rejected
```

## Global

Use Django authentication and Groups/Permissions.

## Domain-specific

Use:

```text
articles/permissions.py
challenges/permissions.py
feed/permissions.py
donations/permissions.py
helpdesk/permissions.py
```

Examples:

```text
User
    Can edit own post

Admin
    Can moderate any post

User
    Can view own ticket

Admin
    Can view/manage support tickets

Admin
    Can verify donations
```

---

# 27. External API Contract

External APIs must be isolated behind service/integration functions.

Never call external APIs directly from:

```text
templates/
models.py
```

Recommended structure:

```text
articles/
└── services.py

challenges/
├── weather.py
└── services.py
```

If integrations grow:

```text
apps/
└── integrations/
    ├── open_food_facts.py
    └── open_meteo.py
```

This should only be introduced if the integrations become shared or sufficiently complex.

---

# 28. Open Food Facts Integration

Endpoint/documentation:

```text
https://openfoodfacts.github.io/openfoodfacts-server/api/
```

Usage:

* Fetch product information when required by article/product recommendation functionality.
* Do not persist third-party product data unless explicitly required.
* Handle unavailable products gracefully.
* Handle API timeouts.
* Handle malformed responses.
* Do not make the article page completely dependent on the external API unless explicitly required.

External API failures should not expose raw exceptions to users.

---

# 29. Open-Meteo Integration

Documentation:

```text
https://open-meteo.com/en/docs
```

Usage:

* Used for outdoor challenge/weather suggestions.
* Weather data must be requested server-side.
* Location input must be converted into coordinates when necessary.
* Do not expose API credentials because the service does not require one under the current project assumptions.
* Handle unavailable location/weather data gracefully.
* External API failures must not crash the challenge module.

---

# 30. Database Rules

## 30.1 Migrations

Every model change MUST generate a migration.

Never manually modify an already-applied migration unless the team explicitly agrees to do so.

Before pushing:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check
```

The migration files MUST be committed.

## 30.2 Data integrity

Use database constraints where appropriate.

Examples:

* Unique fields
* Unique combinations
* Non-null requirements
* Valid relationships
* Check constraints

Business logic should not rely solely on frontend validation.

---

# 31. Templates

Global templates:

```text
templates/
```

Module-specific templates:

```text
apps/<module>/templates/<module>/
```

Example:

```text
apps/feed/templates/feed/post_detail.html
```

Use:

```django
{% extends "base.html" %}
```

for pages.

Reusable global UI components belong in:

```text
templates/partials/
```

Module-specific partials should remain in the module.

---

# 32. HTML Component Rules

Reusable components should be extracted when they are repeated or have meaningful independent behavior.

Examples:

```text
templates/partials/navbar.html
templates/partials/footer.html
templates/partials/messages.html
templates/partials/modal.html
templates/partials/pagination.html
```

Avoid creating partials for tiny fragments that are used only once.

Use semantic HTML:

```html
<header>
<nav>
<main>
<section>
<article>
<footer>
```

Forms must use proper:

```html
<label>
<input>
<select>
<textarea>
<button>
```

---

# 33. Tailwind CSS Rules

Tailwind source:

```text
static/src/input.css
```

Compiled CSS:

```text
static/css/output.css
```

Rules:

1. Use Tailwind utility classes for styling.
2. Avoid unnecessary custom CSS.
3. Do not duplicate long utility combinations unnecessarily.
4. Use reusable template components for repeated UI patterns.
5. Keep responsive behavior explicit.
6. Do not modify Tailwind configuration solely to solve a one-off styling problem.
7. Keep design tokens centralized where practical.

---

# 34. JavaScript Rules

JavaScript belongs in:

```text
static/js/
```

Example:

```text
static/js/main.js
static/js/modal.js
static/js/toast.js
```

JavaScript should enhance server-rendered functionality rather than duplicating the Django application logic.

Never rely exclusively on JavaScript for:

* Authorization
* Validation
* Data integrity
* Security
* Business state transitions

---

# 35. Security Requirements

The application MUST:

* Keep secrets in environment variables.
* Never commit `.env`.
* Keep `.env.example` updated.
* Enable CSRF protection.
* Escape template output appropriately.
* Validate file uploads.
* Validate user-provided URLs and external input.
* Enforce authorization server-side.
* Avoid exposing sensitive information in errors.
* Use secure cookie settings in production.
* Disable Django debug mode in production.

---

# 36. Environment Configuration

Required files:

```text
.env
.env.example
```

`.env` MUST NOT be committed.

Example:

```env
DJANGO_SETTINGS_MODULE=config.settings.development

SECRET_KEY=
DEBUG=True

DATABASE_URL=

OPEN_FOOD_FACTS_BASE_URL=
OPEN_METEO_BASE_URL=
```

Production secrets MUST be provided through the deployment environment.

---

# 37. Git Branching Strategy

The repository uses a lightweight Git Flow-style strategy.

## Permanent branches

```text
main
dev
```

### `main`

Contains production-ready code.

Rules:

* No direct development commits.
* Changes must come through Pull Requests.
* Must pass CI.
* Must represent stable code.

### `dev`

Integration branch for completed features.

Rules:

* Feature branches merge into `dev`.
* CI must pass before merging.
* `dev` should remain runnable.

---

# 38. Feature Branch Naming

Format:

```text
feat/<module>-<short-description>
```

Examples:

```text
feat/articles-crud
feat/challenges-progress
feat/feed-comments
feat/donations-verification
feat/helpdesk-ticket
```

Bug fixes:

```text
fix/<module>-<short-description>
```

Examples:

```text
fix/feed-like-counter
fix/articles-search
fix/helpdesk-status
```

Refactoring:

```text
refactor/<scope>-<description>
```

Documentation:

```text
docs/<description>
```

Chores:

```text
chore/<description>
```

---

# 39. Commit Convention

Use Conventional Commits.

Format:

```text
<type>(<scope>): <description>
```

Allowed types:

```text
feat
fix
refactor
docs
style
test
chore
perf
build
ci
```

Examples:

```text
feat(articles): add article CRUD
feat(challenges): implement daily progress
fix(feed): prevent duplicate likes
fix(donations): validate donation amount
refactor(core): extract admin permission helper
test(helpdesk): add ticket lifecycle tests
docs(api): document article endpoints
style(feed): improve post card spacing
chore(deps): update django version
ci: add automated test workflow
```

Commit messages should:

* Be concise.
* Describe the actual change.
* Avoid vague messages.

Avoid:

```text
update
fix stuff
final
changes
done
```

---

# 40. Commit Scope

Recommended scopes:

```text
core
accounts
articles
challenges
feed
donations
helpdesk
templates
tailwind
ci
deps
docs
```

Example:

```text
feat(helpdesk): add ticket response workflow
```

---

# 41. Push Rules

Developers MUST NOT push directly to:

```text
main
```

Developers SHOULD NOT push directly to:

```text
dev
```

Feature work should be pushed to its feature branch.

Before pushing:

```bash
python manage.py check
python manage.py test
```

and, where applicable:

```bash
npm run build
```

Do not push:

```text
.env
```

or generated secrets.

---

# 42. Pull Request Rules

Every PR must have:

* Clear title
* Description
* Related issue/task
* Summary of changes
* Testing performed
* Screenshots for UI changes
* Migration information if models changed
* External API impact if applicable

PR title format:

```text
<type>(<scope>): <description>
```

Example:

```text
feat(challenges): implement challenge progress tracking
```

---

# 43. Pull Request Template

Recommended structure:

```markdown
## Summary

Describe what was implemented.

## Related Issue

Closes #123

## Changes

- Added ...
- Updated ...
- Removed ...

## Database Changes

- [ ] No database changes
- [ ] New migration
- [ ] Existing migration modified

## API Changes

- [ ] No API changes
- [ ] Added endpoint
- [ ] Modified endpoint
- [ ] Removed endpoint

## External API Changes

- [ ] None
- [ ] Open Food Facts
- [ ] Open-Meteo

## Testing

- [ ] `python manage.py check`
- [ ] `python manage.py test`
- [ ] Frontend/Tailwind build
- [ ] Manual testing

## UI Changes

Attach screenshots if applicable.

## Checklist

- [ ] No secrets committed
- [ ] Authorization checked
- [ ] Validation implemented
- [ ] Tests updated
- [ ] Documentation updated
- [ ] Migration committed
```

---

# 44. Pull Request Review Rules

A PR should not be merged if:

* CI fails.
* Required tests fail.
* It introduces obvious security issues.
* Database migrations are missing.
* Authorization is missing for protected functionality.
* Secrets are committed.
* The implementation violates module ownership without justification.
* The PR introduces unnecessary unrelated changes.

At least one reviewer should approve the PR before merging.

For sensitive functionality such as:

* Authentication
* Authorization
* Donations
* User data
* File uploads

additional review is recommended.

---

# 45. CI Requirements

CI should execute on:

```text
push
pull_request
```

At minimum:

```text
1. Install dependencies
2. Run Django system checks
3. Run migrations/check migration consistency
4. Run tests
5. Build Tailwind assets
```

Example pipeline:

```text
Git Push
   ↓
GitHub Actions
   ↓
Install Python dependencies
   ↓
Install Node dependencies
   ↓
Django check
   ↓
Migration check
   ↓
Django tests
   ↓
Tailwind build
   ↓
PASS / FAIL
```

---

# 46. CD Requirements

Deployment should occur only from the designated stable branch.

Recommended:

```text
dev
  ↓
PR
  ↓
main
  ↓
Production Deployment
```

Production deployment MUST:

1. Install dependencies.
2. Load production environment variables.
3. Run deployment checks.
4. Apply migrations.
5. Collect static files.
6. Restart/reload application services.
7. Verify application health.

Production secrets MUST never be stored in GitHub source files.

---

# 47. Testing Structure

Each module should have:

```text
tests/
├── __init__.py
├── test_models.py
├── test_forms.py
├── test_views.py
├── test_services.py
└── test_permissions.py
```

Not every file is mandatory if the module does not require it.

Example:

```text
feed/tests/
├── test_models.py
├── test_views.py
├── test_permissions.py
└── test_services.py
```

---

# 48. Testing Requirements by Layer

## Models

Test:

* Constraints
* Relationships
* Default values
* Model methods

## Forms

Test:

* Valid input
* Invalid input
* Required fields
* Boundary cases

## Views

Test:

* Authentication
* Authorization
* Successful responses
* Invalid requests
* Redirects
* Template rendering

## Services

Test:

* Business rules
* State transitions
* Multi-step operations
* External API failure behavior

## Permissions

Test:

* Admin access
* User access
* Ownership
* Unauthorized access

---

# 49. Definition of Done

A feature is considered complete only when:

* [ ] Requirement is implemented.
* [ ] Correct Django app owns the implementation.
* [ ] Database changes have migrations.
* [ ] Forms validate input.
* [ ] Authorization is enforced.
* [ ] Business logic is placed appropriately.
* [ ] Templates follow project conventions.
* [ ] Tailwind styling follows project conventions.
* [ ] Tests are implemented where applicable.
* [ ] External integrations handle failure cases.
* [ ] No secrets are committed.
* [ ] Documentation is updated when necessary.
* [ ] `python manage.py check` passes.
* [ ] Tests pass.
* [ ] Tailwind build passes.
* [ ] PR has been reviewed and approved.

---

# 50. Documentation Rules

The repository should maintain:

```text
README.md
PRD.md
docs/ERD.md
docs/API.md
docs/architecture.md
```

## `README.md`

Contains:

* Project overview
* Installation
* Environment setup
* Development commands
* Database setup
* Tailwind setup
* Running tests
* Running development server

## `PRD.md`

Contains:

* Development architecture
* Module responsibilities
* Repository rules
* Git workflow
* API conventions
* Development standards

## `docs/ERD.md`

Contains:

* Entity relationships
* Model ownership
* Important constraints

## `docs/API.md`

Contains:

* Available endpoints
* Request format
* Response format
* Authentication
* Error format
* External integrations

## `docs/architecture.md`

Contains:

* Architectural decisions
* Cross-app dependencies
* Service-layer decisions
* Integration architecture

---

# 51. Architecture Decision Rules

Before introducing a new dependency, library, Django app, abstraction, or architectural pattern, determine:

1. Does the project actually need it?
2. Does an existing project convention already solve it?
3. Does it create additional maintenance cost?
4. Does it introduce unnecessary coupling?
5. Does it make the code easier for the entire team to understand?

Prefer the simplest architecture that satisfies the requirement.

---

# 52. New Module Rules

A new Django app should only be created when a new **business domain** exists.

Good:

```text
articles
challenges
feed
donations
helpdesk
```

Potentially unnecessary:

```text
buttons
pages
forms
components
crud
helpers
```

Do not create a Django app merely to organize files.

---

# 53. Shared Code Rules

Move code into `core` only when:

* It is used by multiple applications.
* Its responsibility is genuinely cross-cutting.
* Its abstraction is stable enough to be reused.

Do not move code into `core` simply because:

> "It doesn't belong anywhere else."

`core` must not become a miscellaneous dumping ground.

---

# 54. Dependency Direction

Preferred dependency direction:

```text
                 core
                  ▲
                  │
              accounts
                  ▲
                  │
       ┌──────────┼───────────┐
       │          │           │
   articles   challenges    feed
       │          │           │
       └────── donations ─────┘
                    │
                 helpdesk
```

The actual dependency graph should remain as simple as possible.

Business modules should not directly depend on implementation details of unrelated modules.

---

# 55. Final Development Principle

The SELARAS repository should follow this rule:

> **Every business concern has one clear owner, every shared concern has one clear abstraction, and every cross-module interaction has an explicit contract.**

In practical terms:

```text
core
  → shared infrastructure

accounts
  → identity + authentication

articles
  → education content + food integration

challenges
  → challenges + progress + streak + badges + weather

feed
  → posts + comments + likes + moderation

donations
  → campaigns + donations + verification

helpdesk
  → tickets + responses + status

config
  → Django project configuration

templates
  → global presentation

static
  → frontend assets

docs
  → technical documentation
```

This structure should be treated as the baseline repository contract. Any intentional deviation should be discussed in a Pull Request and documented as an architectural decision.
