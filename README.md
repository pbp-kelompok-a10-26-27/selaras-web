# SELARAS — Sustainable Living Habit Platform

SELARAS is a digital platform that helps users build sustainable habits consistently through five integrated services: **Articles & Education**, **Challenges**, **Feed**, **Donations & Environmental Action**, and **Help Desk**.

The platform addresses common difficulties in sustainable living: good intentions that are difficult to maintain without structure, generic environmental education, limited spaces for sharing progress, and difficulty turning environmental concerns into concrete collective action.

SELARAS provides structured challenges with daily progress tracking and badges/streaks, contextual educational articles with real-world product recommendations, weather-based suggestions for outdoor activities, a community feed, local environmental donation campaigns, and a dedicated support channel.

### Group Members

| Name                       | Student ID |
| -------------------------- | ---------- |
| Callista Putri Anjola      | 2506603740 |
| Joel Sheldy Sucipto        | 250662494  |
| Asfara Quaneisha Syafaziel | 2506603532 |
| Fayyad Mohammad Madani     | 2506622720 |
| Steven Dyanizha Ananda     | 2506616112 |

### Modules & Responsibilities

| Module                               | Main Functionality                                                                                                                                           | Owner  |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| **Articles & Education**             | CRUD educational/reflective articles, categories, article search/filter/detail, and Eco-Score product recommendations for relevant food/consumption articles | Caca   |
| **Challenges**                       | CRUD challenges, participation, daily progress tracking, badges/streaks, and weather suggestions for outdoor challenges                                      | Fayyad |
| **Feed / Posts**                     | CRUD posts, likes, comments, and community interaction                                                                                                       | Joel   |
| **Donations & Environmental Action** | CRUD environmental campaigns, donation records, verification, and campaign progress                                                                          | Neisha |
| **Help Desk / Customer Service**     | CRUD support tickets, responses, status tracking, and ticket closure                                                                                         | Steven |

### Public APIs

| API                 | Usage                                                                                                                                                                   |
| ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Open Food Facts** | Provides product information and Eco-Score recommendations for relevant Articles & Education content. Data is fetched on request and is not stored as a separate model. |
| **Open-Meteo**      | Provides weather information for outdoor Challenges based on user-provided location/coordinates. No interactive map is required.                                        |

* Open Food Facts: https://openfoodfacts.github.io/openfoodfacts-server/api/
* Open-Meteo: https://open-meteo.com/en/docs

### User Roles

**Admin**

* Manage and publish articles
* Create and manage challenges
* Manage campaigns and verify donations
* Respond to and close Help Desk tickets
* Moderate inappropriate content

**User**

* Read articles
* Join challenges and track progress
* Create and interact with posts
* Donate to environmental campaigns
* Submit and track Help Desk tickets

## Branching & Development Rules

### Branches

```text
main
└── dev
    ├── feat/<module>-<description>
    ├── fix/<module>-<description>
    ├── refactor/<module>-<description>
    ├── docs/<description>
    └── chore/<description>
```

* `main` → stable/production-ready code.
* `dev` → team integration branch.
* Feature/fix branches → individual development work.
* Do not push directly to `main`.
* Avoid direct pushes to `dev`; use Pull Requests.

### Commit Convention

Use Conventional Commits:

```text
feat: add article creation
fix: fix challenge progress calculation
refactor: simplify feed service
docs: update API documentation
test: add donation model tests
chore: update dependencies
```

Prefer module scopes when useful:

```text
feat(articles): add article CRUD
fix(challenges): fix daily progress validation
docs(helpdesk): document ticket workflow
```

### Pull Requests

Before opening a PR:

```bash
python manage.py check
python manage.py test
npm run build
```

A PR should contain:

* Clear description of the change
* Related module
* Testing performed
* Screenshots for UI changes
* Migration information if models changed
* API/external API impact if applicable

Target:

```text
feature branch → dev
dev → main
```

Keep PRs focused. Avoid mixing unrelated modules or features in one PR.

## Repository & Module Structure

```text
selaras-web/
├── apps/
│   ├── core/
│   ├── accounts/
│   ├── articles/
│   ├── challenges/
│   ├── feed/
│   ├── donations/
│   └── helpdesk/
│
├── config/
│   └── settings/
│       ├── base.py
│       ├── development.py
│       └── production.py
│
├── templates/
├── static/
├── media/
├── fixtures/
├── docs/
├── .github/
├── manage.py
├── package.json
├── requirements.txt
└── README.md
```

### Application Responsibilities

#### `apps/core/`

Shared project infrastructure.

Contains:

* Common abstract models such as `TimeStampedModel`
* Shared permissions
* Reusable decorators and mixins
* Generic validators
* Shared constants/utilities

**Rule:** `core` must not contain business logic from Articles, Challenges, Feed, Donations, or Help Desk.

#### `apps/accounts/`

Authentication and user management.

Contains:

* Custom User model
* Authentication
* User profile functionality
* Groups and role-related functionality

Other business modules should reference the User model through Django's configured `AUTH_USER_MODEL`.

#### `apps/articles/`

Owns everything related to Articles & Education.

```text
models.py       → article/category data
forms.py        → article forms
services.py     → article business logic + Open Food Facts integration
permissions.py  → article-specific permissions
views.py        → request/response handling
urls.py         → article routes
templates/      → article pages
tests/          → article tests
```

#### `apps/challenges/`

Owns challenges and user progress.

```text
models.py       → challenge, participation, progress, badge/streak data
forms.py        → challenge/progress forms
services.py     → challenge business logic
weather.py      → Open-Meteo integration
permissions.py  → challenge-specific permissions
views.py        → request/response handling
urls.py         → challenge routes
templates/      → challenge pages
tests/          → challenge tests
```

#### `apps/feed/`

Owns community posts and interactions.

```text
models.py       → posts, likes, comments
forms.py        → post/comment forms
services.py     → feed business logic
permissions.py  → post/moderation permissions
views.py        → request/response handling
urls.py         → feed routes
templates/      → feed pages
tests/          → feed tests
```

#### `apps/donations/`

Owns environmental campaigns and donations.

```text
models.py       → campaigns and donation records
forms.py        → campaign/donation forms
services.py     → donation and verification logic
permissions.py  → campaign/donation permissions
views.py        → request/response handling
urls.py         → donation routes
templates/      → donation pages
tests/          → donation tests
```

#### `apps/helpdesk/`

Owns customer support.

```text
models.py       → tickets and responses
forms.py        → ticket forms
services.py     → ticket workflow/business logic
permissions.py  → ticket permissions
views.py        → request/response handling
urls.py         → Help Desk routes
templates/      → Help Desk pages
tests/          → Help Desk tests
```

### Development Rule

Each module owns its own business logic.

```text
Good:
apps/articles/services.py
apps/feed/services.py
apps/donations/services.py

Avoid:
apps/core/article_helpers.py
apps/core/feed_logic.py
apps/core/donation_utils.py
```

Use `core` only when functionality is genuinely shared across multiple modules.

## Project Folders

| Folder                | Purpose                                                                          |
| --------------------- | -------------------------------------------------------------------------------- |
| `apps/`               | Contains all Django applications organized by business domain                    |
| `apps/core/`          | Shared Django infrastructure and reusable project-level functionality            |
| `apps/accounts/`      | Authentication, users, profiles, and roles                                       |
| `apps/*/templates/`   | Templates belonging to a specific application                                    |
| `apps/*/tests/`       | Tests belonging to a specific application                                        |
| `config/`             | Django project configuration                                                     |
| `config/settings/`    | Environment-specific Django settings                                             |
| `templates/`          | Global templates shared across applications                                      |
| `templates/partials/` | Reusable HTML components such as navbar, footer, messages, pagination, and modal |
| `templates/errors/`   | Global error pages such as 400, 403, 404, and 500                                |
| `static/src/`         | Tailwind CSS source files                                                        |
| `static/css/`         | Compiled CSS output                                                              |
| `static/js/`          | Shared JavaScript                                                                |
| `static/images/`      | Static project images/assets                                                     |
| `media/`              | Runtime user-uploaded files; do not commit uploaded content                      |
| `fixtures/`           | Development/test seed data and Django fixtures                                   |
| `docs/`               | Project documentation such as PRD, API contract, and ERD                         |
| `.github/`            | GitHub workflows and repository configuration                                    |
| `manage.py`           | Django project management entry point                                            |
| `requirements.txt`    | Python dependencies                                                              |
| `package.json`        | Node.js/Tailwind dependencies and scripts                                        |

### Documentation

The `docs/` directory contains the project's technical references:

```text
docs/
├── PRD.md
├── API.md
├── ERD.md
└── architecture.md
```

Before implementing or changing a module, check the relevant documentation first.

* `PRD.md` → product and development requirements
* `API.md` → API contracts and integration rules
* `ERD.md` → database relationships and model structure
* `architecture.md` → system architecture and design decisions
