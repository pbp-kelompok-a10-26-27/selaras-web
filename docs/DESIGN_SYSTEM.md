# SELARAS — Design System

> **Document Type:** Design System Specification
> **Project:** SELARAS — Platform Membangun Kebiasaan Hidup Berkelanjutan
> **Architecture:** Django Templates + Tailwind CSS v4
> **Status:** Development Specification
> **Design Source:** Figma — page "Design System dan Landing Page"
> **Related:** `docs/PRD.md` (sections 31–33)

---

# 1. Purpose

This document defines the SELARAS design system as implemented in the repository.

This document focuses specifically on:

* Design tokens (colors, typography)
* Fonts and icons
* Reusable UI components and their parameters
* Component states and specifications
* Pending design decisions

Component templates do not contain explanatory comments. This document is the single place that explains how each component works.

---

# 2. Source of Truth

| Item                    | Location                              |
| ----------------------- | ------------------------------------- |
| Visual design           | Figma                                 |
| Design tokens           | `static/src/input.css` (`@theme`)     |
| Base element styles     | `static/src/input.css` (`@layer base`) |
| Font loading            | `templates/base.html`                 |
| Components              | `templates/components/`               |
| Compiled CSS            | `static/css/output.css`               |
| Icon library dependency | `requirements.txt`                    |

Design system components live in `templates/components/`. Page-level partials remain in `templates/partials/` as described in `docs/PRD.md`.

Values that come from Figma must be implemented as tokens or component classes, not hardcoded in pages.

---

# 3. Setup

## 3.1 Tailwind CSS

```bash
npm install
npm run dev     # watch mode during development
npm run build   # minified build
```

Tailwind v4 only emits theme variables and utilities that are used in templates. A token defined in `@theme` will not appear in `output.css` until a template uses it.

## 3.2 Fonts

Fonts are loaded from CDNs in `templates/base.html`, before `output.css`:

```html
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600&display=swap"
  rel="stylesheet"
/>
<link href="https://fonts.cdnfonts.com/css/transcity" rel="stylesheet" />
```

| Font              | Source        | Weights |
| ----------------- | ------------- | ------- |
| Transcity         | CDNFonts      | 400     |
| Plus Jakarta Sans | Google Fonts  | 400, 600 |

Fonts require an internet connection. Without it, text falls back to system fonts.

## 3.3 Icons

Icons use the community package `lucide[django]` (Lucide icon set, MIT).

```bash
pip install -r requirements.txt
```

`lucide` is registered in `INSTALLED_APPS` (`config/settings/base.py`). Every template that renders an icon must load the tag library itself:

```django
{% load lucide %}
{% lucide "search" size=16 class="text-primary-600" %}
```

`{% load %}` is not inherited through `extends` or `include`, so each component file that uses icons loads it.

See section 6 for full icon usage.

---

# 4. Color Tokens

Colors are defined in `@theme` and generate utilities such as `bg-primary-300`, `text-secondary-600`, and `border-primary-500`. Tailwind's default palette is kept.

## 4.1 Scales

| Scale       | Hue         |
| ----------- | ----------- |
| `primary`   | Light green |
| `secondary` | Dark green  |
| `tertiary`  | Pink        |
| `neutral`   | Warm gray   |

| Step | `primary` | `secondary` | `tertiary` | `neutral` |
| ---- | --------- | ----------- | ---------- | --------- |
| 50 | `#F7F9F0` | `#EFF2ED` | `#FEF9FA` | `#FFFFFE` |
| 100 | `#F2F6E9` | `#E7EBE5` | `#FDF6F8` | `#FFFFFE` |
| 200 | `#E5EDD2` | `#CDD6C8` | `#FBEDF0` | `#FFFEFD` |
| 300 | `#AAC46D` | `#5F7A4F` | `#F3C5CF` | `#FFFDF8` |
| 400 | `#99B062` | `#566E47` | `#DBB1BA` | `#E6E4DF` |
| 500 | `#889D57` | `#4C623F` | `#C29EA6` | `#CCCAC6` |
| 600 | `#809352` | `#475C3B` | `#B6949B` | `#BFBEBA` |
| 700 | `#667641` | `#39492F` | `#92767C` | `#999895` |
| 800 | `#4C5831` | `#2B3724` | `#6D595D` | `#737270` |
| 900 | `#3B4526` | `#212B1C` | `#554548` | `#595957` |

## 4.2 Semantic Tokens

| Token                | Value     | Usage                                  |
| -------------------- | --------- | -------------------------------------- |
| `--color-foreground` | `#252710` | Default text color, applied to `body` |

## 4.3 Rules

1. Use tokens instead of hex values in templates.
2. The `neutral` scale overrides Tailwind's default `neutral` for steps 50–900. `neutral-950` is still Tailwind's default and is not part of the design.
3. Steps 50–300 of `neutral` are nearly identical in value, as defined in Figma.

## 4.4 Usage

```django
<div class="bg-primary-50">...</div>
<p class="text-secondary-600">...</p>
<div class="border border-primary-500">...</div>
<a class="bg-primary-300 hover:bg-primary-400">...</a>
```

---

# 5. Typography

## 5.1 Font Families

| Token            | Utility        | Font                                    |
| ---------------- | -------------- | --------------------------------------- |
| `--font-display` | `font-display` | `"Transcity", sans-serif`               |
| `--font-sans`    | `font-sans`    | `"Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif` |

`--font-sans` replaces Tailwind's default, so all text uses Plus Jakarta Sans unless stated otherwise.

## 5.2 Type Scale

All text uses color `#252710` unless a component specifies otherwise.

| Style | Utility   | Font                       | Size | Line Height | Weight |
| ----- | --------- | -------------------------- | ---- | ----------- | ------ |
| H1    | `text-h1` | Transcity                  | 64px | 120%        | 400    |
| H2    | `text-h2` | Transcity                  | 48px | 120%        | 400    |
| H3    | `text-h3` | Transcity                  | 32px | 120%        | 400    |
| H4    | `text-h4` | Transcity                  | 24px | 120%        | 400    |
| H5    | `text-h5` | Transcity                  | 20px | 120%        | 400    |
| H6    | `text-h6` | Transcity                  | 16px | 120%        | 400    |
| H7    | `text-h7` | Transcity                  | 12px | 120%        | 400    |
| S1    | `text-s1` | Plus Jakarta Sans SemiBold | 48px | 200%        | 600    |
| S2    | `text-s2` | Plus Jakarta Sans SemiBold | 32px | 200%        | 600    |
| S3    | `text-s3` | Plus Jakarta Sans SemiBold | 24px | 200%        | 600    |
| S4    | `text-s4` | Plus Jakarta Sans SemiBold | 20px | 200%        | 600    |
| S5    | `text-s5` | Plus Jakarta Sans SemiBold | 16px | 200%        | 600    |
| S6    | `text-s6` | Plus Jakarta Sans SemiBold | 12px | 200%        | 600    |
| B1    | `text-b1` | Plus Jakarta Sans Regular  | 24px | 150%        | 400    |
| B2    | `text-b2` | Plus Jakarta Sans Regular  | 20px | 150%        | 400    |
| B3    | `text-b3` | Plus Jakarta Sans Regular  | 16px | 150%        | 400    |
| B4    | `text-b4` | Plus Jakarta Sans Regular  | 12px | 150%        | 400    |
| B5    | `text-b5` | Plus Jakarta Sans Regular  | 8px  | 150%        | 400    |

Letter spacing is 0% for all styles.

## 5.3 Heading Elements

Tailwind resets `h1`–`h6`. The base layer maps them back to the type scale:

| Element | Style |
| ------- | ----- |
| `h1`    | H1    |
| `h2`    | H2    |
| `h3`    | H3    |
| `h4`    | H4    |
| `h5`    | H5    |
| `h6`    | H6    |

## 5.4 Rules

1. Choose the heading element by page structure and the visual style by class, for example `<h2 class="text-h4">`.
2. H7 has no HTML element. Use `font-display text-h7`.
3. S and B styles have no element mapping. Use `text-s*` and `text-b*` on `<p>`, `<span>`, or similar.
4. Plain paragraphs already match B3, so no class is needed.
5. Do not use `font-bold` on Transcity text. The font has a single weight and browsers will synthesize a fake bold. For a bold appearance, use a text stroke as in the navbar link active state.

## 5.5 Usage

```django
<h1>Judul halaman</h1>
<h2 class="text-h4">Subjudul dengan tampilan H4</h2>
<div class="font-display text-h7">Teks gaya H7</div>
<p class="text-s3">Subtitle</p>
<p class="text-b2 text-secondary-600">Paragraf dengan gaya B2</p>
<p>Paragraf biasa (B3)</p>
```

---

# 6. Icons

Icons use Lucide through the `lucide[django]` package. Browse available names at https://lucide.dev/icons/. The installed version (1.1.4) bundles 1745 icons.

## 6.1 Usage

```django
{% load lucide %}

{% lucide "search" %}
{% lucide "arrow-right" size=16 class="text-secondary-300" aria_hidden="true" %}
{% lucide icon_name size=20 %}
```

`{% load lucide %}` must appear in every template that renders an icon. It is not inherited through `extends` or `include`.

## 6.2 Parameters

| Parameter      | Required | Values                                   | Default |
| -------------- | -------- | ---------------------------------------- | ------- |
| name           | Yes      | Lucide icon name, as a string or variable | —       |
| `size`         | No       | Number in px, or `None`                  | `24`    |
| `class`        | No       | Tailwind classes                         | —       |
| `stroke_width` | No       | Number                                   | `2`     |
| Any attribute  | No       | Written with underscores                 | —       |

* Underscores in attribute names become dashes: `aria_hidden` becomes `aria-hidden`, `data_action` becomes `data-action`.
* With `size=None`, the SVG keeps its built-in `width="24"` and `height="24"`, but Tailwind size classes on `class` take precedence.

## 6.3 Color

Icons use `currentColor`. They take the text color of their parent or of a `text-*` class:

```django
<span class="text-primary-800">{% lucide "search" size=20 %}</span>
{% lucide "info" class="text-neutral-50" %}
```

## 6.4 Sizes

| Size | Used in                                  |
| ---- | ---------------------------------------- |
| 16px | Card CTA arrow, button icons on mobile   |
| 20px | Search bar, button icons on desktop      |
| 24px | Figma default icon frame                 |

Responsive size:

```django
{% lucide "info" size=None class="size-4 md:size-5" %}
```

## 6.5 Accessibility

| Case                                     | Rule                                                            |
| ---------------------------------------- | --------------------------------------------------------------- |
| Icon next to visible text                | Add `aria_hidden="true"`                                        |
| Icon is the only content of a control    | Add `aria-label` to the parent control, and `aria_hidden="true"` to the icon |

```django
<button type="button" aria-label="Tutup">
  {% lucide "x" size=20 aria_hidden="true" %}
</button>
```

## 6.6 Icons in Components

| Component  | How to set icons                                        |
| ---------- | ------------------------------------------------------- |
| Button     | Parameters `icon_left`, `icon_right`, `icon_only`       |
| Search bar | Fixed: `search` (left), `menu` (right)                  |
| Card       | Fixed: `arrow-right` in the CTA                         |

Use the button parameters instead of placing `{% lucide %}` inside a button manually.

## 6.7 Common Errors

| Error                                           | Cause                                        |
| ----------------------------------------------- | -------------------------------------------- |
| `Invalid block tag ... 'lucide'`                | `{% load lucide %}` is missing in that template |
| `IconDoesNotExist: The icon '...' does not exist.` | The icon name is misspelled or not in the installed version |
| `ModuleNotFoundError: No module named 'lucide'` | `pip install -r requirements.txt` was not run |

Lucide resembles the Figma icon set but is not identical. Compare icons visually when adding new ones.

---

# 7. Component Conventions

## 7.1 Usage

Components are included with parameters:

```django
{% include "components/<name>.html" with param=value %}
```

## 7.2 Rules

1. Write every Tailwind class in full inside the template. Tailwind cannot detect classes built from variables such as `bg-{{ variant }}`.
2. States that the user triggers directly (hover, focus) are handled with CSS variants.
3. States that the page decides (selected, active, disabled) are handled with parameters.
4. Components render `<a>` when they receive `href`, otherwise a non-link element.
5. Accessibility attributes are set by the component (`aria-current`, `aria-pressed`, `aria-disabled`, `aria-label`).
6. Responsive sizes use the `md` breakpoint (768px): mobile below, desktop at or above.

## 7.3 Component List

| Component   | File                                   |
| ----------- | -------------------------------------- |
| Chips       | `templates/components/chips.html`      |
| Navbar Link | `templates/components/navbar_link.html` |
| Navbar      | `templates/components/navbar.html`     |
| Search Bar  | `templates/components/search_bar.html` |
| Card        | `templates/components/card.html`       |
| Button      | `templates/components/button.html`     |
| Footer      | `templates/components/footer.html`     |

---

# 8. Chips

## 8.1 Usage

```django
{% include "components/chips.html" with label="Eco" variant="primary" %}
{% include "components/chips.html" with label="Semua" href="?kategori=" selected=True %}
```

## 8.2 Parameters

| Parameter  | Required | Values                                         | Default     |
| ---------- | -------- | ---------------------------------------------- | ----------- |
| `label`    | Yes      | Text                                           | —           |
| `variant`  | No       | `primary`, `secondary`, `tertiary`             | `primary`   |
| `href`     | No       | URL. Renders a link with hover state           | —           |
| `selected` | No       | `True`                                         | —           |

## 8.3 States

| Variant     | Default         | Hover           | Selected        |
| ----------- | --------------- | --------------- | --------------- |
| `primary`   | `primary-300`   | `primary-400`   | `primary-500`   |
| `secondary` | `secondary-300` | `secondary-400` | `primary-800`   |
| `tertiary`  | `tertiary-300`  | `tertiary-400`  | `tertiary-500`  |

* Hover applies only when `href` is set.
* A selected chip does not change on hover.
* A selected link receives `aria-current="true"`.
* The secondary selected color is `primary-800` (`#4C5831`), as defined in Figma.

## 8.4 Specifications

| Property  | Value                          |
| --------- | ------------------------------ |
| Height    | 33px                           |
| Min width | 74px (grows with the label)    |
| Padding   | 10px horizontal                |
| Radius    | 10px                           |
| Text      | S5, `neutral-50`, centered     |

---

# 9. Navbar Link

## 9.1 Usage

```django
{% include "components/navbar_link.html" with label="Article" href="/article/" %}
{% include "components/navbar_link.html" with label="Challenge" href="/challenge/" active=True %}
```

## 9.2 Parameters

| Parameter | Required | Values | Default                         |
| --------- | -------- | ------ | ------------------------------- |
| `label`   | Yes      | Text   | —                               |
| `href`    | Yes      | URL    | —                               |
| `active`  | No       | `True` | Automatic when `request.path` equals `href` |

## 9.3 States

| State   | Behavior                                                        |
| ------- | --------------------------------------------------------------- |
| Default | H4 text                                                         |
| Hover   | A 3px underline grows from the left in 300ms                    |
| Active  | Bold appearance and static underline (`text-decoration: underline`), `aria-current="page"` |

* Clicking a link navigates to its page, where the link becomes active.
* The hover animation is disabled for users who prefer reduced motion.
* Transcity has only one weight (400). The active bold appearance uses a 0.6px text stroke (`-webkit-text-stroke`) instead of `font-bold`, so the text does not change width.

## 9.4 Specifications

| Property | Value                                    |
| -------- | ---------------------------------------- |
| Text     | H4 (Transcity, 24px, 120%), centered     |
| Color    | `secondary-500` (text, hover line, and active underline) |
| Size     | Hugs the label (29px tall for "Navbar") |

---

# 10. Navbar

## 10.1 Usage

Add once in `templates/base.html`, above `{% block content %}`:

```django
{% include "components/navbar.html" %}
```

## 10.2 Items

| Position | Items                                       |
| -------- | ------------------------------------------- |
| Left     | Home, Article, Challenge, Feeds, Donation   |
| Right    | Login, Register                             |

* Home links to `{% url 'home' %}`.
* Other items link to `#` until their routes exist.
* Login and Register are static links.
* Active state is matched by exact path only.

## 10.3 Specifications

| Property          | Value                              |
| ----------------- | ---------------------------------- |
| Layout            | Both groups centered as one row    |
| Gap between groups | 64px (placeholder)                |
| Gap between items | 32px (placeholder)                 |
| Padding           | 32px horizontal, 16px vertical (placeholder) |
| Background        | None (placeholder)                 |
| Mobile version    | Not implemented                    |

---

# 11. Search Bar

## 11.1 Usage

```django
{% include "components/search_bar.html" with placeholder="Cari Artikel" %}
{% include "components/search_bar.html" with placeholder="Cari Challenge" wide=True %}
```

Reading the query in a view:

```python
query = request.GET.get("q", "")
```

## 11.2 Parameters

| Parameter     | Required | Values                                      | Default            |
| ------------- | -------- | ------------------------------------------- | ------------------ |
| `placeholder` | No       | Text, also used as the input label          | `Cari`             |
| `action`      | No       | URL the form submits to                     | Current page       |
| `wide`        | No       | `True`. Width follows the container         | Max width 364px    |

## 11.3 States

| State   | Trigger                         | Background    | Border              |
| ------- | ------------------------------- | ------------- | ------------------- |
| Default | —                               | `primary-200` | 1px `primary-500`   |
| Focus   | Input is clicked or typed in    | `primary-300` | Transparent         |

## 11.4 Behavior

* Submits with `GET` as `?q=`.
* The current `q` value is shown in the input after submitting.
* The browser's built-in clear button is hidden.
* The right icon button is static and has no function yet.

## 11.5 Specifications

| Property         | Value                                   |
| ---------------- | --------------------------------------- |
| Height           | 42px                                    |
| Width            | Up to 364px                             |
| Radius           | 10px                                    |
| Padding          | 16px horizontal (measured)              |
| Gap              | 16px (measured)                         |
| Icons            | `search` (left), `menu` (right), 20px, `primary-800` |
| Placeholder text | S5, `primary-800`                       |
| Input text       | S5, `foreground`                        |

---

# 12. Card

## 12.1 Usage

```django
{% include "components/card.html" with title="Nama challenge" description="Deskripsi singkat" href="/challenge/1/" %}
{% include "components/card.html" with title=challenge.title description=challenge.summary image=challenge.image.url href=challenge.get_absolute_url %}
```

## 12.2 Parameters

| Parameter     | Required | Values                                     | Default           |
| ------------- | -------- | ------------------------------------------ | ----------------- |
| `title`       | Yes      | Text. One line, truncated with "..."       | —                 |
| `description` | No       | Text. Up to two lines                      | —                 |
| `href`        | No       | URL. Makes the whole card a link           | —                 |
| `image`       | No       | Image URL                                  | Pink placeholder  |
| `cta`         | No       | Text                                       | `Start challenge` |

## 12.3 Specifications

| Property    | Value                                               |
| ----------- | --------------------------------------------------- |
| Size        | 164px × 190px                                       |
| Radius      | 10px                                                |
| Background  | `primary-50`                                        |
| Image area  | 60px tall, `object-cover`; placeholder `tertiary-300` |
| Padding     | 12px horizontal, 4px top, 18px bottom (measured)    |
| Title       | S5, `secondary-600`                                 |
| Description | B5, `primary-300`                                   |
| CTA         | S6, `secondary-300`, `arrow-right` icon 16px, 2px gap, pinned to the bottom |

* The title uses `<p>` instead of a heading element, because the base layer would apply Transcity to `h3`.
* There is no hover state yet.

---

# 13. Button

## 13.1 Usage

```django
{% include "components/button.html" with label="Mulai" %}
{% include "components/button.html" with label="Kirim" type="submit" variant="secondary" icon_right="arrow-right" %}
{% include "components/button.html" with label="Lihat" href="/challenge/" selected=True %}
{% include "components/button.html" with label="Simpan" disabled=True %}
{% include "components/button.html" with icon_only="info" aria_label="Informasi" %}
```

## 13.2 Parameters

| Parameter    | Required | Values                                   | Default   |
| ------------ | -------- | ---------------------------------------- | --------- |
| `label`      | Yes, unless `icon_only` | Text                      | —         |
| `variant`    | No       | `primary`, `secondary`                   | `primary` |
| `href`       | No       | URL. Renders `<a>`                       | `<button>` |
| `type`       | No       | `button`, `submit`                       | `button`  |
| `icon_left`  | No       | Lucide icon name                         | —         |
| `icon_right` | No       | Lucide icon name                         | —         |
| `icon_only`  | No       | Lucide icon name                         | —         |
| `aria_label` | With `icon_only` | Text                             | `label`   |
| `selected`   | No       | `True`                                   | —         |
| `disabled`   | No       | `True`                                   | —         |

## 13.3 States

| Variant     | Default       | Hover          | Selected        |
| ----------- | ------------- | -------------- | --------------- |
| `primary`   | `primary-300` | `tertiary-300` | `secondary-300` |
| `secondary` | `primary-400` | `tertiary-400` | `secondary-400` |
| Disabled    | `neutral-800` | —              | —               |

* Selected sets `aria-pressed="true"` on `<button>` or `aria-current="page"` on `<a>`.
* Disabled sets `disabled` on `<button>`. On `<a>`, `href` is removed and `aria-disabled="true"` is set.
* Disabled takes priority over selected.
* The Figma disabled color is `#70706E`. The closest token, `neutral-800`, is used.

## 13.4 Specifications

| Property          | Mobile (< 768px) | Desktop (≥ 768px) |
| ----------------- | ---------------- | ----------------- |
| Height            | 40px             | 48px              |
| Text              | S6               | S5                |
| Gap               | 8px              | 12px              |
| Icon slot         | 20px             | 24px              |
| Icon-only size    | 40px × 40px      | 48px × 48px       |
| Padding           | 8px 24px         | 8px 24px          |
| Radius            | 10px             | 10px              |
| Text color        | `neutral-50`     | `neutral-50`      |

---

# 14. Footer

## 14.1 Usage

Add once in `templates/base.html`, below `{% block content %}`:

```django
{% include "components/footer.html" %}
```

## 14.2 Content

| Column     | Items                                                         |
| ---------- | ------------------------------------------------------------- |
| Socials    | LinkedIn, Instagram, Twitter, each labeled `selaras.id`       |
| Support    | FAQs, Terms & Conditions, Privacy Policy                      |
| Contact Us | `0878 7574 5182` (`tel:`), `contact@selaras.co.id` (`mailto:`), `www.selaras.co.id` |

* The copyright year is generated with `{% now "Y" %}`.
* Social and Support links point to `#` until their URLs exist.
* Each social link includes a screen-reader-only platform name, because all three visible labels are `selaras.id`.
* Social icons are image files in `static/assets/icons/` (`Linkedin.svg`, `Instagram.svg`, `Twitter.svg`) with a fixed `#F7F9F0` fill. File names are case-sensitive on Linux servers.

## 14.3 Specifications

All values are measured from the Figma frame (1440px wide).

| Property                 | Value                                         |
| ------------------------ | --------------------------------------------- |
| Width                    | Full width                                    |
| Background               | `tertiary-300`                                |
| Text color               | `secondary-300`                               |
| Top section padding      | 36px top, 126px right, 13px bottom, 40px left |
| Logo                     | `logo-w-jargon.svg`, 250px wide               |
| Column block offset      | 32px from the top section padding             |
| Column widths            | Socials 171px, Support 199px, Contact Us auto |
| Column heading           | S4                                            |
| Links                    | S6, 12px gap between items                    |
| Social icon              | 17px × 18px, 8px gap to the label             |
| Divider                  | 1px `neutral-50`, full width                  |
| Copyright                | S5, 8px top, 13px bottom, 40px left           |

* Column headings use `<h2>` with `font-sans text-s4`, overriding the base heading style.
* There are no hover states in the design.
* There is no mobile layout yet.

---

# 15. Pending Decisions

| Item                       | Detail                                                                 |
| -------------------------- | ---------------------------------------------------------------------- |
| Search bar right icon      | `menu` or a filter icon such as `sliders-horizontal`, and its label (currently "Filter") |
| Search bar right button    | No function yet                                                        |
| Color contrast             | White text on `primary-300` and `tertiary-300` (chips, button) and the card description are below WCAG AA (4.5:1) |
| B5 size                    | 8px is hard to read                                                    |
| Card hover                 | Not defined in Figma                                                   |
| Card padding               | Measured from Figma screenshots, not confirmed                         |
| Search bar padding and gap | Measured from Figma screenshots, not confirmed                         |
| Navbar layout              | Gap values, padding, and background are placeholders                   |
| Navbar links               | Only Home has a real route                                             |
| Navbar mobile              | Not implemented                                                        |
| Login and Register         | Static links; final form (link or button) not decided                  |
| Button breakpoint          | `md` (768px) assumed                                                   |
| Footer links               | Social and Support URLs are placeholders                               |
| Footer Twitter icon        | Design uses the old Twitter bird; the brand now uses X                 |
| Footer logo file           | `logo-w-jargon.svg` contains an embedded raster image, not vectors     |
| Footer mobile              | Not implemented                                                        |
| Transcity license          | Loaded from CDNFonts as `Transcity Demo.woff` (demo version); license not confirmed |

---

# 16. Change Rules

1. New colors or text styles must be added to `@theme` in `static/src/input.css` before use.
2. New components belong in `templates/components/` and must be documented in this file.
3. Changes to a component's parameters, states, or specifications must update its section in this file.
4. Resolved pending decisions must be removed from section 15.
5. Run `npm run build` after changing tokens or component classes.
