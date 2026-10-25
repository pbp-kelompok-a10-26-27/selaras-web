# SELARAS — Continuous Integration (CI) Documentation

> **Document Type:** CI/CD Technical Specification & Operational Guide  
> **Project:** SELARAS — Platform Membangun Kebiasaan Hidup Berkelanjutan  
> **Workflow File:** `.github/workflows/ci.yml`  
> **Status:** Active / Production Standard  
> **Primary Language:** Bahasa Indonesia  
> **Related Documents:** `docs/PRD.md` (Sections 41, 44, 45, 46)  

---

# 1. Purpose

Dokumen ini mendefinisikan standar dan panduan operasional alur kerja **Continuous Integration (CI)** yang berjalan di repositori SELARAS menggunakan **GitHub Actions**.

Dokumen ini mencakup:
* Pemicu (*triggers*) dan aturan konkurensi alur kerja.
* Rincian setiap tahapan (*pipeline steps*) dan perintah yang dijalankan.
* Panduan verifikasi lokal sebelum melakukan *push* (*pre-push checklist*).
* Panduan mengatasi kegagalan CI (*troubleshooting*).
* Catatan perencanaan untuk Continuous Deployment (CD).

---

# 2. Arsitektur & Pipeline Overview

Setiap kali kode di-*push* atau diajukan melalui *Pull Request* ke branch integrasi (`develop`) dan produksi (`main`), GitHub Actions akan menjalankan serangkaian pengujian otomatis pada runner cloud terisolasi (`ubuntu-latest`).

```text
                  Git Push / Pull Request
                   (develop / main)
                           │
                           ▼
               GitHub Actions: CI Job
              (Runner: ubuntu-latest)
                           │
         ┌─────────────────┴─────────────────┐
         ▼                                   ▼
   Python Layer                        Node.js Layer
 (Python 3.13)                          (Node.js 20)
         │                                   │
         ├── Install requirements.txt        ├── npm ci (with cache)
         ├── Ruff Linting                    └── Tailwind CSS Build
         ├── Django System Check
         ├── Migration Consistency Check
         ├── Unit Tests (manage.py test)
         └── Dependency Audit (pip-audit)
                           │
                           ▼
                 STATUS: PASS / FAIL
```

---

# 3. Pemicu (*Triggers*) & Hak Akses

Konfigurasi pemicu pada `.github/workflows/ci.yml`:

```yaml
on:
  push:
    branches: ["**"]
  pull_request:
    branches: [main, develop]

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

* **Pemicu `push: branches: ["**"]`**: Pipeline dieksekusi secara otomatis pada **setiap push ke semua branch** (termasuk branch fitur seperti `feat/*`, `fix/*`, `chore/*`, serta `develop` dan `main`). Hal ini memastikan setiap commit diuji secara instan sebelum diajukan ke tahap berikutnya.
* **Pemicu `pull_request: branches: [main, develop]`**: Pipeline dieksekusi secara khusus untuk setiap pengajuan *Pull Request* yang menargetkan branch utama (`main` dan `develop`). Pola ini mencegah terjadinya build ganda (*duplicate runs*) saat developer bekerja pada PR yang sedang terbuka.
* **Keamanan Hak Akses**: `permissions: contents: read` memastikan CI berjalan dalam mode *read-only* murni. CI **tidak dapat mengubah atau melakukan push balik** ke repositori.
* **Concurrency Control**: Jika developer melakukan push commit baru ke branch yang sama saat build sebelumnya masih berlangsung, build lama otomatis dibatalkan (`cancel-in-progress: true`) untuk menghemat antrean runner.

---

# 4. Rincian Tahapan Pipeline (*Pipeline Steps*)

Pipeline dijalankan dalam satu job terpadu bernama `ci` pada sistem operasi `ubuntu-latest`:

### 4.1 Checkout Repository
```yaml
- uses: actions/checkout@v4
```
Mengunduh salinan source code repositori ke dalam workspace virtual machine runner.

### 4.2 Setup Lingkungan Python
```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.13"
    cache: pip
    cache-dependency-path: requirements.txt
```
Menyiapkan runtime Python 3.13 dan mengaktifkan caching otomatis untuk paket `pip` berdasarkan hash `requirements.txt`.

### 4.3 Install Dependensi Python
```yaml
- name: Install Python dependencies
  run: pip install -r requirements.txt
```
Menginstal seluruh pustaka yang didefinisikan dalam `requirements.txt` (Django, django-environ, lucide, psycopg2, dll).

### 4.4 Linting Kode (Ruff)
```yaml
- name: Lint (ruff)
  run: ruff check .
```
Memverifikasi kepatuhan gaya penulisan kode, deteksi bug potensial, unused imports, dan sintaks Python yang tidak aman menggunakan linter super-cepat **Ruff**.

### 4.5 Django System Checks
```yaml
- name: Django system check
  run: python manage.py check
```
Memeriksa integritas konfigurasi Django, kompatibilitas model, URL patterns, settings, dan temuan peringatan sistemik sebelum aplikasi dijalankan.

### 4.6 Validasi Konsistensi Migrasi Database
```yaml
- name: Migrations up to date
  run: python manage.py makemigrations --check --dry-run
```
Memastikan tidak ada perubahan pada `models.py` yang lupa dibuatkan berkas migrasinya oleh developer. Jika terdeteksi ada perubahan model yang belum dimigrasi, pipeline akan **gagal**.

### 4.7 Menjalankan Pengujian Otomatis (*Unit Tests*)
```yaml
- name: Tests
  run: python manage.py test
```
Menjalankan seluruh pengujian unit dan integrasi pada direktori aplikasi (`apps/*/tests/`). Semua tes wajib lulus (*0 failures, 0 errors*).

### 4.8 Audit Keamanan Dependensi (*Reporting Only*)
```yaml
- name: Dependency audit (report only)
  run: pip-audit -r requirements.txt
  continue-on-error: true
```
Memindai database kerentanan keamanan (CVE) untuk seluruh dependensi terinstal. Menggunakan `continue-on-error: true` agar temuan celah keamanan dapat dipantau pada log laporan tanpa langsung menghentikan alur integrasi mendesak.

### 4.9 Setup Lingkungan Node.js
```yaml
- name: Setup Node.js
  uses: actions/setup-node@v4
  with:
    node-version: "20"
    cache: "npm"
```
Menyiapkan runtime Node.js v20 (LTS) beserta caching direktori npm berdasarkan `package-lock.json`.

### 4.10 Install Dependensi Node.js
```yaml
- name: Install Node dependencies
  run: npm ci
```
Menginstal dependensi Node.js secara deterministik menggunakan `npm ci` (Tailwind CSS v4 dan Tailwind CLI).

### 4.11 Kompilasi Tailwind CSS
```yaml
- name: Build Tailwind CSS
  run: npm run build
```
Memvalidasi bahwa `static/src/input.css` dan seluruh utility classes pada template dapat dikompilasi secara sempurna tanpa error sintaks Tailwind.

---

# 5. Checklist Verifikasi Lokal (*Pre-Push Checklist*)

Sebelum melakukan `git push` atau membuka *Pull Request*, setiap developer **wajib** menjalankan perintah berikut di komputer lokal masing-masing untuk memastikan pipeline CI akan berstatus hijau (PASS):

```bash
# 1. Periksa linting kode Python
ruff check .

# 2. Periksa integritas sistem Django
python manage.py check

# 3. Periksa kelengkapan migrasi database
python manage.py makemigrations --check --dry-run

# 4. Jalankan seluruh unit tests
python manage.py test

# 5. Uji build aset Tailwind CSS
npm run build
```

---

# 6. Panduan Mengatasi Kegagalan CI (*Troubleshooting*)

| Penyebab Kegagalan | Pesan Indikator di GitHub Actions | Solusi Perbaikan |
|---|---|---|
| **Lupa membuat migrasi** | `Migrations up to date: SystemCheckError / changes detected` | Jalankan `python manage.py makemigrations`, commit file migrasi baru yang terbentuk di folder `apps/<module>/migrations/`, lalu push kembali. |
| **Linting error (Ruff)** | `Found X errors. X fixable with the --fix option.` | Jalankan `ruff check --fix .` di lokal untuk memperbaiki formatting otomatis, atau perbaiki baris yang bermasalah secara manual. |
| **Unit test gagal** | `FAIL: test_... (apps.<module>.tests)` | Buka rincian error tes pada tab Actions GitHub, perbaiki kode atau *assertion* tes yang tidak sesuai di lokal hingga `python manage.py test` lulus 100%. |
| **Tailwind build gagal** | `Error: @theme / syntax error in input.css` | Periksa penulisan variabel token di `static/src/input.css`, pastikan tidak ada class yang bentrok atau tanda kurung yang belum ditutup. Jalankan `npm run build` di lokal. |
| **Dependensi hilang** | `ModuleNotFoundError: No module named '...'` | Pastikan package Python baru telah dicatat di `requirements.txt` atau package Node di `package.json`. |

---

# 7. Rencana Continuous Deployment (CD)

Alur **Continuous Deployment (CD)** ke server produksi saat ini **ditangguhkan sementara** menunggu finalisasi target lingkungan deployment (seperti Railway, Render, atau VPS) dan kesepakatan mekanisme build aset di lingkungan produksi. 

Dokumentasi dan alur kerja CD ([`.github/workflows/cd.yml`](file:///C:/Users/HP/Obsidian/academic-vault/05-PBP/selaras-web/.github/workflows/cd.yml)) akan ditambahkan pada rilis dokumentasi berikutnya sesuai spesifikasi yang tertera di `docs/PRD.md` Bagian 46.
