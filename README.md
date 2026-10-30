# SELARAS — Platform Kebiasaan Hidup Berkelanjutan

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.x-092E20?logo=django&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4.x-06B6D4?logo=tailwindcss&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-production-4169E1?logo=postgresql&logoColor=white)
![CI](https://github.com/pbp-kelompok-a10-26-27/selaras-web/actions/workflows/ci.yml/badge.svg)

**SELARAS** adalah platform web yang membantu pengguna membangun kebiasaan hidup ramah lingkungan secara konsisten. Platform ini menggabungkan edukasi, tantangan terstruktur, ruang berbagi komunitas, aksi donasi, dan layanan bantuan dalam satu ekosistem yang saling terhubung.

Proyek ini dikembangkan sebagai **proyek kelompok setengah semester** pada mata kuliah Pemrograman Berbasis Platform (PBP) Gasal 2026/2027, Fakultas Ilmu Komputer, Universitas Indonesia.

> [Link Deployment](https://steven-dyanizha-selaras-web.pws.cs.ui.ac.id) | 
> [Link Figma](https://www.figma.com/design/ehFwOVTAobEXuoefdRIzAf/SELARAS?m=auto&t=sxvETIX5yQbqtG7z-6)

---

## Daftar Isi

1. [Latar Belakang](#latar-belakang)
2. [Anggota Kelompok](#anggota-kelompok)
3. [Modul dan Penanggung Jawab](#modul-dan-penanggung-jawab)
4. [Penjelasan Setiap Modul](#penjelasan-setiap-modul)
5. [Peran Pengguna](#peran-pengguna)
6. [Integrasi Antarmodul](#integrasi-antarmodul)
7. [API Publik Eksternal](#api-publik-eksternal)
8. [Teknologi yang Digunakan](#teknologi-yang-digunakan)
9. [Arsitektur dan Struktur Repositori](#arsitektur-dan-struktur-repositori)
10. [Menjalankan Proyek Secara Lokal](#menjalankan-proyek-secara-lokal)
11. [Pengujian dan Penjaminan Kualitas](#pengujian-dan-penjaminan-kualitas)
12. [Deployment](#deployment)
13. [Alur Kerja Pengembangan](#alur-kerja-pengembangan)
14. [Design System](#design-system)
15. [Dokumentasi Tambahan](#dokumentasi-tambahan)
16. [Riwayat Progres](#riwayat-progres)
17. [AI Disclosure](#ai-disclosure)

---

## Latar Belakang

Banyak orang sebenarnya peduli terhadap lingkungan, tetapi kesulitan mengubah kepedulian itu menjadi kebiasaan. Dari hasil analisis kebutuhan, kelompok kami mengidentifikasi empat masalah utama:

1. **Niat baik sulit dipertahankan** tanpa struktur, target, dan umpan balik yang jelas.
2. **Edukasi lingkungan sering terlalu umum** sehingga sulit diterapkan pada kehidupan sehari-hari.
3. **Ruang untuk berbagi progres masih terbatas**, padahal dukungan komunitas membantu menjaga motivasi.
4. **Kepedulian sulit diwujudkan menjadi aksi kolektif** yang nyata dan terukur.

SELARAS menjawab masalah tersebut melalui:

- **Challenge terstruktur** dengan progres harian, *streak*, lencana (*badge*), *leaderboard*, dan target komunitas.
- **Artikel edukatif kontekstual** yang dilengkapi rekomendasi produk berbasis Eco-Score.
- **Saran cuaca** untuk challenge yang dilakukan di luar ruangan.
- **Feed komunitas** untuk berbagi cerita, foto, dan progres.
- **Kampanye donasi lingkungan** dengan verifikasi bukti transfer.
- **Help Desk** sebagai kanal resmi untuk pertanyaan dan kendala pengguna.
- **Notifikasi** agar pengguna langsung mengetahui respons dan hasil dari setiap aktivitasnya.

---

## Anggota Kelompok

| Nama                       | NPM        | Panggilan |
| -------------------------- | ---------- | --------- |
| Callista Putri Anjola      | 2506603740 | Caca      |
| Joel Sheldy Sucipto        | 2506622494 | Joel      |
| Asfara Quaneisha Syafaziel | 2506603532 | Neisha    |
| Fayyad Mohammad Madani     | 2506622720 | Fayyad    |
| Steven Dyanizha Ananda     | 2506616112 | Steven    |

---

## Modul dan Penanggung Jawab

| Modul                              | App Django            | Ringkasan Fungsi                                                                                    | Penanggung Jawab |
| ---------------------------------- | --------------------- | --------------------------------------------------------------------------------------------------- | ---------------- |
| **Artikel & Edukasi**              | `apps.articles`       | Artikel edukatif, kategori, tag, alur review admin, pelacakan bacaan, rekomendasi Eco-Score          | Caca             |
| **Challenge**                      | `apps.challenges`     | Challenge, partisipasi, progres harian, lencana, target komunitas, *leaderboard*, saran cuaca        | Fayyad           |
| **Feed**                           | `apps.feeds`          | Postingan bergambar, suka, komentar, balasan, daftar penyuka, moderasi                              | Joel             |
| **Donasi & Aksi Lingkungan**       | `apps.donations`      | Kampanye donasi, pencatatan donasi, verifikasi bukti, *donor wall*                                  | Neisha           |
| **Help Desk**                      | `apps.helpdesk`       | Tiket bantuan, prioritas, status, percakapan, lampiran tangkapan layar                              | Steven           |
| **Dashboard Admin**                | `apps.dashboard`      | Panel admin terpusat: ringkasan, manajemen pengguna, tiket, dan moderasi seluruh modul              | Steven           |
| **Akun & Autentikasi**             | `apps.accounts`       | Registrasi, login, profil, avatar, lencana unggulan, ganti dan atur ulang kata sandi                | Steven           |
| **Notifikasi**                     | `apps.notifications`  | Notifikasi lintas modul di lonceng navbar, halaman kotak masuk, status baca                         | Steven           |
| **Core** *(bersama)*               | `apps.core`           | Infrastruktur bersama: model dasar, izin akses, validator, komponen UI, *landing page*, data demo   | Bersama          |

---

## Penjelasan Setiap Modul

### 1. Artikel & Edukasi (`apps/articles`)

Modul ini menyediakan bacaan edukatif dan reflektif seputar gaya hidup berkelanjutan.

- **Penulisan oleh pengguna dengan review admin.** Pengguna dapat menulis artikel, lalu mengirimkannya untuk ditinjau. Admin dapat menyetujui atau menolak dengan catatan revisi (`review_note`). Status artikel tercatat beserta waktu pengiriman, waktu review, dan peninjau.
- **Kategori dan tag** untuk mengelompokkan artikel. Admin dapat mengelola kategori.
- **Pencarian, filter, dan halaman detail** artikel.
- **Pelacakan bacaan** melalui model `ArticleRead`. Data ini dipakai oleh modul Challenge untuk tipe target "Artikel dibaca".
- **Rekomendasi produk Eco-Score** dari Open Food Facts untuk artikel yang relevan dengan konsumsi atau makanan.
- **Halaman "Artikel Saya"** untuk memantau status tulisan sendiri.

Model utama: `ArticleCategory`, `Tag`, `Article`, `ArticleRead`.

### 2. Challenge (`apps/challenges`)

Modul ini merupakan pusat gamifikasi SELARAS.

- **Challenge dengan periode** (tanggal mulai dan selesai) yang dapat diikuti dan ditinggalkan oleh pengguna.
- **Enam tipe target** (`GoalType`). Selain check-in harian, progres dihitung otomatis dari aktivitas di modul lain (`metrics.py`):

  | Tipe Target          | Sumber Data             |
  | -------------------- | ----------------------- |
  | Check-in harian      | Input manual pengguna   |
  | Artikel dibaca       | Modul Artikel           |
  | Jumlah donasi (Rp)   | Modul Donasi            |
  | Cerita dibagikan     | Modul Feed (postingan)  |
  | Suka diterima        | Modul Feed (suka)       |
  | Komentar ditulis     | Modul Feed (komentar)   |

- **Lencana (*badge*) sebagai hadiah.** Admin dapat memasang lencana saat membuat challenge. Lencana otomatis diberikan ketika challenge selesai.
- **Target komunitas** (`CommunityGoal`), yaitu target kolektif yang dicapai bersama seluruh pengguna.
- ***Leaderboard*** per challenge dan **riwayat** partisipasi.
- **Saran cuaca** dari Open-Meteo untuk challenge luar ruangan.

Model utama: `Badge`, `Challenge`, `ChallengeParticipation`, `ChallengeProgress`, `UserBadge`, `CommunityGoal`.

### 3. Feed (`apps/feeds`)

Modul ini adalah ruang komunitas untuk berbagi cerita dan progres.

- **Postingan dengan foto**, maksimal 10 foto untuk pengguna dan 20 foto untuk admin. Postingan dapat dikaitkan dengan challenge tertentu.
- **Suka** pada postingan dan komentar, beserta **daftar penyuka**.
- **Komentar dan balasan bertingkat** dengan gaya seperti Instagram.
- **Moderasi** oleh admin. Penulis akan menerima notifikasi jika kontennya dihapus.
- **REST API sederhana** di `/api/v1/` (`posts`, `posts/<id>`, `posts/<id>/like`, `posts/<id>/likes`, `admin/posts`).

Model utama: `Post`, `PostImage`, `Comment`, `Like`, `CommentLike`.

### 4. Donasi & Aksi Lingkungan (`apps/donations`)

Modul ini menghubungkan kepedulian pengguna dengan aksi nyata.

- **Kampanye donasi** dengan target dana, gambar, periode, dan progres pengumpulan.
- **Pencatatan donasi** dengan unggahan bukti transfer, pesan dukungan, dan opsi anonim.
- **Antrean verifikasi** untuk admin. Donasi dapat disetujui atau ditolak dengan alasan penolakan.
- **Bukti transfer bersifat privat** dan hanya dapat diakses oleh pemilik donasi dan admin.
- **Donor wall** dan **riwayat donasi** pengguna.

Model utama: `Campaign`, `Donation`.

### 5. Help Desk (`apps/helpdesk`) — *Steven*

Modul ini menjadi kanal resmi bagi pengguna untuk menyampaikan pertanyaan atau kendala.

- **Pembuatan tiket** dengan subjek, deskripsi, dan prioritas (Rendah, Sedang, Tinggi).
- **Siklus status tiket:** `Terbuka → Diproses → Selesai → Ditutup`. Waktu penutupan tercatat pada `closed_at`.
- **Percakapan dua arah** antara pengguna dan admin, termasuk fitur **membalas pesan tertentu** (`reply_to`) yang menampilkan kutipan pesan asal.
- **Lampiran tangkapan layar**, maksimal 5 per tiket, berupa unggahan berkas (maksimal 5 MB) atau tautan gambar. *Constraint* basis data memastikan setiap lampiran hanya berisi salah satu dari keduanya.
- **Kontrol akses yang ketat:**
  - Tiket hanya dapat dilihat oleh pembuatnya dan admin.
  - Hanya pembuat tiket dan **admin yang ditugaskan** yang dapat mengirim pesan, sehingga setiap tiket memiliki satu penanggung jawab yang jelas.
  - Tiket berstatus *Ditutup* bersifat hanya-baca.
  - Lampiran diunduh melalui *view* yang memeriksa izin, bukan melalui URL media publik.
- **Statistik, pencarian, filter, pengurutan, dan paginasi.** Parameter *query string* divalidasi dengan *allowlist*, sehingga nilai yang tidak valid diabaikan dan tidak menimbulkan *error*.
- **Antarmuka dinamis** berbasis JSON API (`/helpdesk/api/tickets/...`) dengan *skeleton loading*.

Model utama: `Ticket`, `TicketMessage`, `TicketAttachment`.

### 6. Dashboard Admin (`apps/dashboard`) — *Steven*

Modul ini adalah panel kontrol terpusat untuk admin di `/dashboard/`. Setiap modul tetap memiliki logika bisnisnya sendiri, sedangkan dashboard menyatukan tampilan pengelolaannya.

- **Halaman ringkasan** yang menampilkan sapaan sesuai waktu, daftar hal yang perlu ditindaklanjuti (artikel menunggu review, donasi menunggu verifikasi, tiket yang belum ditugaskan, tiket milik admin), serta aktivitas 7 hari terakhir.
- **Navigasi sidebar** yang didefinisikan secara deklaratif di `navigation.py`. Bagian yang URL-nya belum tersedia otomatis tampil sebagai "Segera" alih-alih menjadi tautan rusak. Menu juga menampilkan *badge* jumlah item yang menunggu tindakan.
- **Manajemen pengguna:** daftar, detail, ubah peran (admin/pengguna), serta aktivasi atau penonaktifan akun. Terdapat pengaman (*guard*) agar admin tidak mengubah akunnya sendiri secara tidak sengaja.
- **Manajemen tiket Help Desk:** penugasan (*assign*), pembaruan status dan prioritas, balasan, dan penghapusan.
- **Manajemen Challenge:** CRUD challenge, lencana, dan target komunitas.
- **Moderasi Artikel, Donasi, dan Feed**, termasuk penghapusan postingan atau komentar dengan notifikasi ke penulisnya.
- **Komponen bersama** seperti filter *chip*, kartu metrik, dan modal konfirmasi agar tampilan setiap halaman tetap konsisten.

### 7. Akun & Autentikasi (`apps/accounts`) — *Steven*

Modul ini menangani identitas dan profil pengguna.

- **Custom User model** dengan primary key UUID, email unik, bio, avatar, dan peran (`admin` atau `user`). Seluruh modul lain merujuk ke model ini melalui `settings.AUTH_USER_MODEL`.
- **Registrasi, login, dan logout.**
- **Pembatasan percobaan login:** setelah 5 kali gagal untuk kombinasi IP dan *username* yang sama, login dikunci selama 15 menit (HTTP 429). Setiap kegagalan dicatat ke *log*.
- **Halaman profil** yang menampilkan data diri, koleksi lencana, dan ringkasan dampak (*impact summary*) dari aktivitas di seluruh modul.
- **Unggah dan hapus avatar** dengan validasi berkas gambar.
- **Lencana unggulan (*featured badge*)**, yaitu satu lencana pilihan yang ditampilkan di samping nama pengguna pada postingan, komentar, dan daftar penyuka.
- **Ganti kata sandi** dan **alur atur ulang kata sandi** melalui email (bawaan Django dengan tampilan khusus SELARAS).

Model utama: `User`.

### 8. Notifikasi (`apps/notifications`) — *Steven*

Modul ini memberi tahu pengguna tentang hal-hal yang terjadi pada aktivitas mereka di seluruh platform. Notifikasi menjadi umpan balik (*feedback*) langsung yang membuat interaksi terasa hidup, misalnya saat postingan disukai atau donasi disetujui.

- **Satu layanan untuk semua modul.** Modul lain cukup memanggil `notify()` atau `notify_admins()` dari `services.py`, sehingga aturan pembuatan notifikasi hanya ditulis di satu tempat. Modul yang memakai layanan ini adalah Artikel, Challenge, Donasi, Feed, dan Dashboard.
- **13 jenis notifikasi**, masing-masing dengan ikon dan warna sendiri:

  | Sumber    | Jenis Notifikasi                                                       |
  | --------- | ---------------------------------------------------------------------- |
  | Feed      | Postingan disukai, komentar baru, balasan baru, komentar disukai        |
  | Challenge | Lencana baru, challenge selesai                                        |
  | Donasi    | Donasi perlu diverifikasi (untuk admin), donasi disetujui, donasi ditolak |
  | Artikel   | Artikel perlu ditinjau (untuk admin), artikel terbit, artikel perlu revisi |
  | Dashboard | Konten dihapus oleh admin                                              |

- **Aturan agar notifikasi tidak mengganggu:**
  - Pengguna **tidak menerima notifikasi atas tindakannya sendiri**, misalnya menyukai postingan sendiri.
  - **Deduplikasi** dengan `dedupe_key`, sehingga aksi berulang seperti suka, batal suka, lalu suka lagi tidak menghasilkan notifikasi ganda.
  - Akun yang dinonaktifkan tidak menerima notifikasi.
- **Lonceng di navbar** (`bell.js`) yang membuka *popover* berisi notifikasi terbaru beserta jumlah yang belum dibaca. Jumlah ini diperbarui setiap 60 detik selama tab browser aktif, dan notifikasi lencana baru ditampilkan sebagai *toast*. Tanpa JavaScript, lonceng tetap berfungsi sebagai tautan ke halaman notifikasi (*progressive enhancement*).
- **Halaman kotak masuk** di `/notifications/` dengan filter semua atau belum dibaca, serta paginasi 20 item per halaman.
- **Buka dan tandai dibaca.** Membuka notifikasi akan menandainya sebagai sudah dibaca, lalu mengarahkan pengguna ke halaman terkait. URL tujuan divalidasi dengan `url_has_allowed_host_and_scheme` untuk mencegah *open redirect*. Pengguna juga dapat menandai semua notifikasi sebagai sudah dibaca dengan request POST.
- **Keamanan dan performa:** primary key UUID, notifikasi hanya dapat dibuka oleh penerimanya, *index* gabungan (`recipient`, `read_at`, `-created_at`) untuk mempercepat *query* kotak masuk, serta `bulk_create` saat mengirim notifikasi ke seluruh admin.

Model utama: `Notification`.

### 9. Core (`apps/core`)

Modul ini berisi infrastruktur bersama yang **tidak mengandung logika bisnis modul lain**:

- Model abstrak `TimeStamp` (`created_at`, `updated_at`).
- Izin akses (`permissions.py`), *decorator* `admin_required`, dan *mixin* (`AuthenticatedRequiredMixin`, `AdminRequiredMixin`, `OwnerRequiredMixin`).
- Validator unggahan gambar dan URL gambar, serta penyimpanan berkas privat.
- Komponen UI berbasis `django-components` (lihat [Design System](#design-system)).
- *Landing page* dengan angka *live* dari setiap modul. Setiap blok dilindungi agar kegagalan satu modul tidak menjatuhkan seluruh halaman.
- Halaman *error* khusus (403, 404) dan perintah `seed_demo` untuk mengisi data demo.

---

## Peran Pengguna

| Kemampuan                                      | Tamu | Pengguna | Admin |
| ---------------------------------------------- | :--: | :------: | :---: |
| Melihat *landing page* dan artikel terbit      |  ✓   |    ✓     |   ✓   |
| Menulis artikel (melalui review)               |      |    ✓     |   ✓   |
| Meninjau dan menerbitkan artikel               |      |          |   ✓   |
| Mengikuti challenge dan mencatat progres       |      |    ✓     |   ✓   |
| Membuat challenge, lencana, dan target komunitas |    |          |   ✓   |
| Membuat postingan, menyukai, dan berkomentar   |      |    ✓     |   ✓   |
| Memoderasi postingan dan komentar              |      |          |   ✓   |
| Berdonasi ke kampanye                          |      |    ✓     |   ✓   |
| Mengelola kampanye dan memverifikasi donasi    |      |          |   ✓   |
| Membuat dan memantau tiket Help Desk           |      |    ✓     |   ✓   |
| Menangani, menugaskan, dan menutup tiket       |      |          |   ✓   |
| Menerima notifikasi aktivitas                  |      |    ✓     |   ✓   |
| Menerima notifikasi antrean review dan verifikasi |   |          |   ✓   |
| Mengakses Dashboard Admin dan mengelola pengguna |    |          |   ✓   |

---

## Integrasi Antarmodul

Salah satu fokus rancangan SELARAS adalah agar setiap modul tidak berdiri sendiri. Aktivitas di satu modul memberi nilai pada modul lain:

```text
              ┌──────────────┐   dibaca    ┌──────────────────────────┐
              │   Artikel    │────────────▶│                          │
              └──────────────┘             │        Challenge         │
              ┌──────────────┐  disetujui  │  (metrics.py menghitung  │──▶ Lencana ──▶ Profil &
              │    Donasi    │────────────▶│   progres secara         │                featured badge
              └──────────────┘             │   otomatis)              │                di samping nama
              ┌──────────────┐ post/suka/  │                          │
              │     Feed     │────────────▶│                          │
              └──────────────┘  komentar   └──────────────────────────┘
                     │                                   │
                     └──────────────┬────────────────────┘
                                    ▼
                             ┌──────────────┐
                             │  Notifikasi  │  (lonceng navbar)
                             └──────────────┘

        Help Desk, Artikel, Donasi, Feed, Challenge, Pengguna
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │    Dashboard Admin     │  (satu pintu pengelolaan)
                        └────────────────────────┘
```

Aturan yang dijaga: **setiap modul memiliki logika bisnisnya sendiri**. Modul lain hanya membaca data melalui *service* atau *query* yang disediakan pemilik modul, bukan dengan menduplikasi logika tersebut.

---

## API Publik Eksternal

| API                 | Kegunaan                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Open Food Facts** | Informasi produk dan rekomendasi Eco-Score pada artikel yang relevan. Data diambil saat dibutuhkan dan tidak disimpan sebagai model. |
| **Open-Meteo**      | Informasi cuaca untuk challenge luar ruangan berdasarkan lokasi atau koordinat dari pengguna.                                  |

- Open Food Facts: https://openfoodfacts.github.io/openfoodfacts-server/api/
- Open-Meteo: https://open-meteo.com/en/docs

---

## Teknologi yang Digunakan

| Lapisan           | Teknologi                                                                       |
| ----------------- | ------------------------------------------------------------------------------- |
| Backend           | Python 3.11+, Django 5.x                                                        |
| Basis data        | SQLite (pengembangan), PostgreSQL (produksi, melalui `psycopg`)                 |
| Frontend          | Django Templates, Tailwind CSS 4, JavaScript (tanpa *framework*)                |
| Komponen UI       | `django-components`, ikon `lucide`                                              |
| Berkas statis     | WhiteNoise                                                                      |
| Server aplikasi   | Gunicorn                                                                        |
| Kualitas kode     | Ruff (lint dan format), `pip-audit`, Husky + lint-staged (*pre-commit hook*)    |
| CI                | GitHub Actions                                                                  |
| Hosting           | PWS (Pacil Web Service) Fasilkom UI                                             |

---

## Arsitektur dan Struktur Repositori

SELARAS menggunakan arsitektur **monolit modular**: satu proyek Django yang dipecah menjadi beberapa *app* berdasarkan domain bisnis. Setiap *app* mengikuti pembagian lapisan yang konsisten:

```text
models.py       → struktur data, constraint, dan custom QuerySet
forms.py        → validasi input
services.py     → logika bisnis dan query yang dipakai ulang
permissions.py  → aturan hak akses khusus modul
views.py        → penanganan request/response (HTML dan JSON)
urls.py         → routing modul
tests/          → pengujian modul
```

### Struktur Direktori

```text
selaras-web/
├── apps/
│   ├── core/            # infrastruktur bersama, komponen UI, landing page, seed_demo
│   ├── accounts/        # custom user, autentikasi, profil
│   ├── articles/        # artikel & edukasi
│   ├── challenges/      # challenge, lencana, target komunitas, cuaca
│   ├── feeds/           # postingan, suka, komentar
│   ├── donations/       # kampanye dan donasi
│   ├── helpdesk/        # tiket bantuan
│   ├── notifications/   # notifikasi lintas modul
│   └── dashboard/       # panel admin terpusat
│
├── config/
│   ├── settings/
│   │   ├── base.py          # pengaturan bersama
│   │   ├── development.py   # DEBUG, SQLite
│   │   └── production.py    # PostgreSQL, WhiteNoise, HTTPS, keamanan
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── templates/           # template global (base, partials, errors, landing, dashboard, dll.)
├── static/
│   ├── src/             # sumber Tailwind CSS
│   ├── css/             # hasil build CSS
│   ├── js/              # JavaScript per modul dan per komponen
│   └── assets/          # gambar dan aset statis
├── media/               # unggahan publik saat runtime (tidak di-commit)
├── private_media/       # unggahan privat, misalnya bukti donasi dan lampiran tiket (tidak di-commit)
├── fixtures/            # data awal
├── docs/                # dokumentasi teknis
├── .github/workflows/   # pipeline CI
├── .husky/              # pre-commit hook
├── manage.py
├── requirements.txt
├── package.json
└── pyproject.toml       # konfigurasi Ruff
```

### Peta URL Utama

| Prefix              | Modul                                       |
| ------------------- | ------------------------------------------- |
| `/`                 | *Landing page*                              |
| `/accounts/`        | Registrasi, login, profil, kata sandi       |
| `/articles/`        | Artikel & Edukasi                           |
| `/challenges/`      | Challenge                                   |
| `/feed/`            | Feed                                        |
| `/donations/`       | Donasi                                      |
| `/helpdesk/`        | Help Desk                                   |
| `/notifications/`   | Notifikasi                                  |
| `/dashboard/`       | Dashboard Admin                             |
| `/api/`, `/api/v1/` | API artikel dan feed                        |
| `/design-system/`   | Galeri token dan komponen design system     |
| `/admin/`           | Django admin bawaan                         |

---

## Menjalankan Proyek Secara Lokal

### Prasyarat

- Python 3.11 atau lebih baru
- Node.js 20 atau lebih baru (untuk Tailwind CSS dan *git hook*)
- Git

### Langkah Instalasi

```bash
# 1. Clone repositori
git clone https://github.com/pbp-kelompok-a10-26-27/selaras-web.git
cd selaras-web

# 2. Buat dan aktifkan virtual environment (gunakan nama venv atau .venv)
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # macOS/Linux

# 3. Pasang dependensi
pip install -r requirements.txt
npm install                      # sekaligus mengaktifkan Husky

# 4. Siapkan environment
cp .env.example .env             # lalu isi SECRET_KEY

# 5. Migrasi basis data
python manage.py migrate

# 6. (Opsional) Isi data demo dan buat akun admin
python manage.py seed_demo
python manage.py createsuperuser

# 7. Build CSS dan jalankan server
npm run build                    # atau `npm run dev` untuk mode watch
python manage.py runserver
```

Aplikasi dapat diakses di http://127.0.0.1:8000.

### Variabel Environment

| Variabel                 | Keterangan                                                                      |
| ------------------------ | ------------------------------------------------------------------------------- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` (lokal) atau `config.settings.production`         |
| `SECRET_KEY`             | Kunci rahasia Django. Di produksi wajib minimal 50 karakter.                    |
| `ALLOWED_HOSTS`          | Daftar host dipisahkan koma (produksi)                                          |
| `DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT`, `SCHEMA` | Koneksi PostgreSQL (produksi) |
| `SERVE_MEDIA`            | Django melayani `/media/` (bawaan `true` di PWS)                                 |
| `SECURE_SSL_REDIRECT`    | Atur `false` jika terjadi *redirect loop* di balik proxy                         |

### Data Demo

```bash
python manage.py seed_demo           # isi data demo
python manage.py seed_demo --reset   # hapus data demo lama, lalu isi ulang
python manage.py seed_demo --clear   # hanya hapus data demo
```

---

## Pengujian dan Penjaminan Kualitas

Setiap modul memiliki pengujian otomatis di folder `tests/` masing-masing, mencakup model, *service*, *view*, API, dan aturan hak akses.

```bash
python manage.py test                                  # seluruh pengujian
python manage.py test apps.helpdesk                    # satu modul
python manage.py test apps.notifications.tests         # satu paket test
```

### Continuous Integration

Setiap *push* dan *pull request* menjalankan pipeline GitHub Actions (`.github/workflows/ci.yml`):

| Tahap                     | Perintah                                           |
| ------------------------- | -------------------------------------------------- |
| Lint                      | `ruff check .`                                     |
| Format                    | `ruff format --check .`                            |
| Pemeriksaan sistem Django | `python manage.py check`                           |
| Migrasi lengkap           | `python manage.py makemigrations --check --dry-run`|
| Pengujian                 | `python manage.py test`                            |
| Audit dependensi          | `pip-audit -r requirements.txt` (hanya laporan)    |
| Build CSS                 | `npm ci && npm run build`                          |

### Praktik Keamanan yang Diterapkan

- Primary key **UUID** untuk data sensitif (pengguna, tiket, postingan, komentar, donasi, notifikasi) agar ID tidak dapat ditebak secara berurutan.
- **Pembatasan percobaan login** untuk mencegah *brute force*.
- **Berkas privat** (bukti donasi, lampiran tiket) disimpan di luar folder media publik dan hanya diunduh melalui *view* yang memeriksa izin.
- **Validasi unggahan gambar** (tipe dan ukuran) serta validasi URL gambar.
- **Allowlist** untuk parameter *query string* (filter, pengurutan, pencarian).
- **Constraint basis data** untuk aturan yang tidak boleh dilanggar, bukan hanya validasi di form.
- Pengaturan produksi: HTTPS *redirect*, HSTS, *secure cookie*, CSRF *trusted origins*, dan penolakan menjalankan aplikasi dengan `SECRET_KEY` bawaan.

---

## Deployment

Aplikasi di-deploy ke **PWS (Pacil Web Service)** dengan pengaturan `config.settings.production`:

- **Gunicorn** sebagai server aplikasi dan **WhiteNoise** untuk berkas statis.
- **PostgreSQL** dari PWS. Jika `DB_HOST` tidak diatur, aplikasi kembali menggunakan SQLite yang akan hilang setiap kali *redeploy*.
- Django melayani `/media/` karena PWS tidak menyediakan web server terpisah.
- *Error* 500 dicatat lengkap beserta *traceback* ke *log* PWS untuk mempermudah *debugging*.

```bash
git push pws main:master
```

Setelah *deploy*, periksa *log* PWS untuk memastikan seluruh migrasi berhasil diterapkan.

---

## Alur Kerja Pengembangan

### Branch

```text
main
└── develop
    ├── feat/<modul>-<deskripsi>
    ├── fix/<modul>-<deskripsi>
    ├── refactor/<modul>-<deskripsi>
    ├── docs/<deskripsi>
    └── chore/<deskripsi>
```

- `main` berisi kode stabil yang siap produksi.
- `develop` adalah branch integrasi tim.
- Branch fitur atau perbaikan digunakan untuk pengembangan individu.
- Dilarang *push* langsung ke `main`, dan sebaiknya hindari *push* langsung ke `develop`. Gunakan *Pull Request*.

### Konvensi Commit

Proyek ini menggunakan [Conventional Commits](https://www.conventionalcommits.org/), sebaiknya disertai *scope* modul:

```text
feat(articles): add article CRUD
fix(challenges): fix daily progress validation
refactor(feeds): simplify feed service
docs(helpdesk): document ticket workflow
test(donations): add donation model tests
chore: update dependencies
```

### Git Hooks

*Pre-commit hook* dikelola oleh [Husky](https://typicode.github.io/husky/) dan [lint-staged](https://github.com/lint-staged/lint-staged). Konfigurasinya ada di `.husky/pre-commit` dan `lint-staged.config.js`. *Hook* aktif otomatis setelah `npm install` dan akan menemukan `venv/` atau `.venv/` tanpa perlu mengaktifkannya terlebih dahulu.

Hanya berkas yang di-*stage* yang diperiksa:

| Berkas yang di-*stage* | Perintah                                            | Hasil                                                      |
| ---------------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| `*.py`                 | `ruff check --fix`, lalu `ruff format`              | Perbaikan di-*stage* ulang; *error* yang tidak dapat diperbaiki memblokir commit |
| `apps/**/models.py`    | `python manage.py makemigrations --check --dry-run` | Memblokir commit jika ada migrasi yang belum dibuat         |

**Aturan:**

- Jangan melewati *hook* dengan `git commit --no-verify`, karena CI menjalankan pemeriksaan yang sama.
- Commit berkas migrasi bersamaan dengan perubahan model yang membutuhkannya.
- Jangan mengubah berkas di `*/migrations/` secara manual hanya untuk menghindari peringatan Ruff, karena folder migrasi sudah dikecualikan dari *linting*.

**Pemecahan masalah:**

- `ruff: command not found`: jalankan `pip install -r requirements.txt` di dalam `venv/` atau `.venv/`.
- *Hook* tidak berjalan: jalankan ulang `npm install` (atau `npm run prepare`). Perintah `git config core.hooksPath` seharusnya menampilkan `.husky/_`.

### Pull Request

Sebelum membuka PR, jalankan pemeriksaan yang sama dengan CI:

```bash
ruff check .
ruff format --check .
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
npm run build
```

Isi PR sebaiknya memuat deskripsi perubahan, modul terkait, pengujian yang dilakukan, tangkapan layar untuk perubahan UI, informasi migrasi jika ada perubahan model, dan dampak terhadap API jika ada. Usahakan PR tetap fokus dan tidak mencampur modul atau fitur yang tidak berkaitan.

### Aturan Kepemilikan Kode

```text
Baik:
apps/articles/services.py
apps/feeds/services.py

Hindari:
apps/core/article_helpers.py
apps/core/feed_logic.py
```

Gunakan `core` hanya untuk fungsionalitas yang benar-benar dipakai bersama oleh beberapa modul.

---

## Design System

Seluruh antarmuka mengikuti satu design system (warna, tipografi, ikon, *spacing*) yang dapat dilihat langsung di `/design-system/` dan didokumentasikan di [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md).

Komponen UI dibangun dengan [`django-components`](https://django-components.github.io/django-components/) dan ditempatkan di `apps/core/components/`:

```text
apps/core/components/
└── <nama-komponen>/
    ├── <nama-komponen>.html
    └── <nama-komponen>.py
```

Komponen yang tersedia: `avatar`, `badge`, `badge_chip`, `button`, `chips`, `dropdown`, `empty_state`, `file_drop`, `footer`, `input`, `modal`, `navbar`, `pagination`, `photo_picker`, `progress`, `sidebar`, `skeleton`, `textarea`, `toast`, `tooltip`, `user_name`.

---

## Dokumentasi Tambahan

| Dokumen                                        | Isi                                                        |
| ---------------------------------------------- | ---------------------------------------------------------- |
| [docs/PRD.md](docs/PRD.md)                     | Kebutuhan produk dan pengembangan                          |
| [docs/ERD.md](docs/ERD.md)                     | Relasi basis data dan struktur model                       |
| [docs/API.md](docs/API.md)                     | Kontrak API dan aturan integrasi                           |
| [docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) | Token desain dan panduan komponen                          |
| [docs/CICD.md](docs/CICD.md)                   | Pipeline CI/CD                                             |


Sebelum mengimplementasikan atau mengubah suatu modul, baca dokumentasi yang relevan terlebih dahulu.

---

## Riwayat Progres

- [x] Inisialisasi repositori, struktur modul, dan design system (warna, tipografi, ikon)
- [x] Sistem autentikasi, halaman login, dan halaman registrasi
- [x] Model, *view*, dan URL awal untuk setiap modul
- [x] Dashboard untuk admin dan pengguna
- [x] Komponen UI yang dapat dipakai ulang dengan `django-components` serta halaman `/design-system/`
- [x] *Pre-commit hook* (Husky + lint-staged) dan pemeriksaan `ruff format` di CI
- [x] Modul Help Desk dengan sistem manajemen tiket
- [x] Penyempurnaan halaman profil dan sistem autentikasi
- [x] Halaman *error* 403 dan 404
- [x] Rekonstruksi *landing page*
- [x] Desain ulang Feed, Donasi, dan Artikel mengikuti design system
- [x] Pembaruan besar:
  - Primary key UUID untuk postingan, komentar, donasi, dan notifikasi
  - Progres challenge dilacak otomatis dari artikel, donasi, dan feed, dengan hadiah lencana
  - Lencana unggulan di samping nama pengguna
  - Notifikasi di lonceng navbar
  - Hingga 10 foto per postingan (20 untuk admin)
  - Daftar penyuka, suka pada komentar, dan balasan bergaya Instagram
  - Artikel ditulis pengguna dan ditinjau admin, dengan pelacakan bacaan dan manajemen kategori
  - *Donor wall* dan alasan penolakan donasi
- [x] Gamifikasi: target komunitas, *leaderboard* per challenge, dan ringkasan dampak di profil
- [x] *Seeder* data demo (`python manage.py seed_demo`)
- [x] Konfigurasi deployment ke PWS (PostgreSQL, WhiteNoise, Gunicorn)

---

## AI Disclosure

Bagian ini berisi pernyataan penggunaan *Artificial Intelligence* (AI) dalam pengembangan SELARAS. Setiap pernyataan ditulis oleh penanggung jawab modul masing-masing dengan format yang sama, yaitu alat yang digunakan, bentuk penggunaan, serta tanggung jawab dan verifikasi.

### Artikel & Edukasi — Callista Putri Anjola

Pernyataan ini berlaku untuk modul **Artikel & Edukasi** (`apps/articles`, branch `feat/articles`).

#### Alat yang Digunakan

- **Asisten berbasis AI (*AI Agent*)**, digunakan sebagai teman diskusi teknis dan asisten pembelajaran (*discussion partner & learning assistant*).

#### Bentuk Penggunaan

AI digunakan sebagai **alat bantu** untuk memahami implementasi kode, mendiskusikan konsep teknis, dan mengevaluasi kemungkinan solusi atas permasalahan yang ditemukan selama pengembangan. Secara garis besar, AI dimanfaatkan untuk:

1. **Pemahaman model data dan Django ORM**, misalnya struktur dan relasi antara `Article`, `ArticleCategory`, dan `Tag`, penggunaan `ForeignKey` (kategori dan *author*) serta `ManyToManyField` (tag), penggunaan `SlugField`, `UniqueConstraint`, metode `save()` dan `__str__()`, serta akses *field* antarmodel melalui *double underscore* (`__`) pada *query*.
2. **Logika *view*, pencarian, dan filter artikel**, termasuk pencarian dengan `Q`, `icontains`, dan operator OR, kemungkinan pencarian berdasarkan nama kategori dan *username author*, filter berdasarkan kategori, tag, dan status publikasi, paginasi, serta alasan pemisahan HTML *view* dan API *view*.
3. **Pengelolaan artikel dan hak akses**, yaitu alur CRUD artikel, perbedaan hak akses admin dan pengguna biasa, pengelolaan status `DRAFT` dan `PUBLISHED` beserta waktu publikasi (`published_at`), validasi form (kategori, tag, dan gambar), serta pembatasan akses artikel yang belum terbit agar hanya dapat dilihat admin.
4. **Integrasi *frontend* dan template Django**, misalnya penggunaan Django Template Language (`{% extends %}`, `{% block %}`, `{% include %}`, `{% if %}`, `{% for %}`), hubungan *view*, *context*, dan template, penyesuaian halaman daftar, detail, dan form artikel, konsistensi komponen dan *class* CSS dengan desain SELARAS, serta penelaahan masalah pemanggilan template, *static files*, dan aset seperti logo.
5. **Pengujian, kolaborasi, dan *version control***, termasuk pemeriksaan perubahan kode sebelum dikirim ke repositori, penggunaan Git (*add*, *commit*, *push*) pada branch `feat/articles`, pembuatan *Pull Request* ke `develop` beserta pemeriksaan *commit*, perubahan berkas, dan hasil *automated checks*, serta cara membaca status PR dan proses *merge*.

#### Tanggung Jawab dan Verifikasi

- **Inisiatif dan kontrol** berada di tangan saya. Saya menentukan kebutuhan fitur, mengidentifikasi permasalahan, mengajukan pertanyaan, dan mengarahkan diskusi sesuai kebutuhan modul.
- AI digunakan sebagai **sarana pembelajaran** untuk mendiskusikan konsep, memahami alur kode yang sudah ada, memperoleh penjelasan alternatif implementasi, dan membantu mengevaluasi kemungkinan penyebab suatu masalah.
- Proses pengembangan, penyesuaian kode, pengujian pada aplikasi lokal, dan pemeriksaan hasil implementasi **dilakukan sendiri**. Saran dan penjelasan dari AI dipelajari dan disesuaikan kembali dengan struktur serta kebutuhan proyek.
- **Keputusan akhir** terkait implementasi fitur, penyesuaian kode, dan penyelesaian masalah tetap berada di tangan saya berdasarkan pemahaman terhadap sistem dan hasil pengujian.

### Challenge — Fayyad Mohammad Madani

Pernyataan ini berlaku untuk modul **Challenge** (`apps/challenges`, branch `feat/challenges`).

#### Alat yang Digunakan

- **Asisten berbasis AI (*AI Agent*)**, digunakan sebagai rekan diskusi teknis (*pair-programming & learning assistant*).

#### Bentuk Penggunaan

AI digunakan sebagai **alat bantu** untuk mempercepat pemahaman, menelaah kode yang sudah ada, dan menyusun evaluasi teknis. Secara garis besar, AI dimanfaatkan untuk:

1. **Pemahaman arsitektur dan model data (ORM)**, misalnya relasi antara `Challenge`, `ChallengeParticipation`, `ChallengeProgress`, `Badge`, dan `UserBadge`, alasan desain seperti pemilihan `BigAutoField` atau `UUID`, peran kolom `slug` untuk *index query* dan integritas *permalink*, `UniqueConstraint` di tingkat basis data, serta metode model seperti `save()` dengan `*args` dan `**kwargs`, `@property status`, dan `auto_now_add`.
2. **Validasi dan penanganan form**, yaitu validasi lintas *field* (*cross-field validation*) pada metode `clean()` di `ChallengeForm`, misalnya validasi tanggal mulai dan tanggal berakhir.
3. **Logika *view*, otorisasi, dan *best practice***, termasuk verifikasi autentikasi (`@login_required`) dan otoritas admin (`@admin_required`), pengambilan data yang aman dengan `get_object_or_404`, pencegahan duplikasi data dengan `get_or_create()`, *type hinting* pada *reverse relation* ORM, serta penulisan *query* yang aman dari *error* (misalnya pembagian dengan nol dan penggunaan `.exclude(completed_at=None)`).
4. **Integrasi *frontend*, AJAX, dan Weather API**, misalnya alur *partial HTML swap* dengan `render_to_string` dan `XMLHttpRequest`, serta alur Browser Geolocation API (`navigator.geolocation`) yang terhubung ke integrasi Open-Meteo di *backend*.

#### Tanggung Jawab dan Verifikasi

- **Inisiatif dan kontrol** berada di tangan saya. Seluruh arahan, alur pertanyaan, skenario implementasi, dan kriteria fitur saya tentukan sendiri.
- Penulisan kode, pengujian langsung pada aplikasi lokal, dan pengujian logika bisnis **dilakukan, dipahami, dan diverifikasi penuh** oleh saya.
- **Keputusan akhir** terkait arsitektur dan implementasi tetap berada di tangan saya sebagai penanggung jawab modul.

### Feed — Joel Sheldy Sucipto

Pernyataan ini berlaku untuk modul **Feed** (`apps/feeds`, branch `feat/feeds`), serta dukungan teknis lintas modul.

#### Alat yang Digunakan

- **Asisten berbasis AI (*AI Agent*)**, digunakan sebagai rekan diskusi teknis (*pair-programming & learning assistant*).

#### Bentuk Penggunaan

AI digunakan sebagai **alat bantu** untuk memahami arsitektur yang sudah ada, mengimplementasikan fitur, menelaah masalah, dan menyusun pengujian. Secara garis besar, AI dimanfaatkan untuk:

1. **Pemahaman arsitektur dan model data**, misalnya relasi model `Post`, `Comment`, dan `Like` serta keterkaitannya dengan pengguna, challenge, dan peserta challenge, juga pembahasan *constraint*, *index*, kepemilikan konten, dan penggunaan ORM dalam pengambilan data Feed.
2. **Pengembangan fitur Feed**, termasuk pembuatan postingan progres dengan challenge opsional, validasi foto, halaman detail postingan, komentar, balasan satu tingkat, dan *like/unlike*, penghapusan postingan oleh pemiliknya dan moderasi oleh admin dengan pemeriksaan izin di *server*, serta akses Feed bagi admin untuk menghapus konten milik pengguna lain.
3. **Antarmuka dan aksesibilitas**, yaitu form postingan dan komentar, navigasi dari kartu Feed ke detail postingan, tombol interaksi, dialog konfirmasi penghapusan di tengah layar, perbaikan tampilan tombol agar teks terlihat dan posisinya terpusat, serta penggunaan label, fokus *keyboard*, dan atribut aksesibilitas pada elemen interaktif.
4. **API, media, dan otorisasi**, misalnya penelaahan *endpoint* Feed, format respons JSON, interaksi antara *handler* web dan API, pemeriksaan penyimpanan dan penyajian foto postingan di *environment development*, serta pembatasan akses berdasarkan autentikasi, peran, dan kepemilikan konten.
5. ***Troubleshooting* dan verifikasi**, termasuk analisis masalah login akibat kondisi basis data lokal, pemeriksaan konfigurasi migrasi, penyusunan dan pelaksanaan pengujian untuk fitur Feed, unggahan media, serta perilaku akses pengguna dan admin, dan penggunaan pemeriksaan format, *lint*, dan *diff* untuk mengevaluasi perubahan kode.
6. **Dukungan alur kerja Git**, yaitu pembagian perubahan menjadi beberapa *commit*, pemilihan berkas atau bagian yang akan di-*stage*, penulisan pesan *commit* dan deskripsi *merge*, serta pemeriksaan status branch dan perbandingannya dengan branch *remote* sebelum melakukan *pull*.
7. **Pembelajaran teknis modul lain**, misalnya konsep model dan ORM, validasi form, autentikasi dan otorisasi, serta integrasi AJAX dan layanan cuaca pada modul Challenge.

#### Tanggung Jawab dan Verifikasi

- **Inisiatif dan kontrol** berada di tangan saya. Kebutuhan fitur, urutan pengerjaan, pertanyaan, dan kriteria penerimaan saya tentukan sendiri.
- AI membantu menghasilkan atau mengubah kode dan pengujian. Saya **meninjau setiap perubahan** tersebut dan menentukan apakah perubahan sesuai dengan kebutuhan proyek.
- Pengujian dan pemeriksaan teknis **dijalankan untuk bagian yang diubah**. Hasilnya membantu proses verifikasi, tetapi tidak menjamin semua kondisi penggunaan, *deployment*, atau *environment* produksi telah teruji.
- **Keputusan akhir** terkait arsitektur, pemilihan perubahan yang dipertahankan, serta tindakan *commit*, *push*, *pull*, dan *merge* tetap berada di tangan saya.
- Saya **bertanggung jawab penuh** atas pemahaman, kualitas, keamanan, dan keputusan penggunaan hasil kerja, karena saran atau perubahan dari AI tetap perlu diperiksa kembali.

### Donasi & Aksi Lingkungan — Asfara Quaneisha Syafaziel

Pernyataan ini berlaku untuk modul **Donasi & Aksi Lingkungan** (`apps/donations`, branch `feat/donations`).

#### Alat yang Digunakan

- **ChatGPT** (OpenAI), digunakan sebagai pendamping pengembangan (*pair-programming & learning assistant*).

#### Bentuk Penggunaan

AI digunakan sebagai **alat bantu** untuk memahami struktur proyek, mengeksplorasi implementasi fitur, menyusun kode, dan menangani kendala teknis selama pengembangan. Secara garis besar, AI dimanfaatkan untuk:

1. **Eksplorasi arsitektur dan model data**, misalnya hubungan antara model `Campaign` dan `Donation`, penggunaan *field* dan relasi antarmodel, pilihan status donasi, serta alur perubahan status (`PENDING`, `APPROVED`, `REJECTED`) dan pengaruhnya terhadap perhitungan progres kampanye.
2. **Implementasi fitur dan logika *backend***, termasuk referensi dan bantuan penyusunan kode pada `views.py`, `forms.py`, URL *routing*, dan template untuk daftar, pencarian, dan detail kampanye, pengajuan donasi dengan unggahan bukti pembayaran, riwayat dan detail donasi (pengguna hanya dapat melihat donasinya sendiri), pengeditan donasi berstatus `PENDING`, serta fitur admin untuk mengelola kampanye dan memverifikasi donasi (*approve* atau *reject*).
3. **Validasi, otorisasi, dan penanganan data**, yaitu validasi input form donasi dan kampanye, pembatasan akses berdasarkan autentikasi dan peran admin, penanganan kondisi khusus seperti kampanye yang tidak lagi menerima donasi dan donasi yang sudah diverifikasi, serta memastikan perubahan status dan total donasi tetap mengikuti aturan bisnis.
4. **Penyusunan dan evaluasi pengujian otomatis**, termasuk pemahaman struktur Django `TestCase`, eksplorasi skenario pengujian (pembuatan donasi, riwayat dan detail, verifikasi admin, pengelolaan kampanye), pengujian validasi, pembatasan akses, perubahan status, dan progres kampanye, serta analisis penyebab kegagalan *test*.
5. ***Debugging* dan *troubleshooting***, misalnya menganalisis pesan *error*, potongan kode, dan *output* terminal, meminta alternatif perbaikan untuk kendala kode maupun konfigurasi proyek, serta memahami kegagalan pemeriksaan format Ruff di GitHub Actions dan memperbaikinya dengan `ruff format`.
6. ***Version control* dan kolaborasi**, termasuk panduan Git dan GitHub (*clone*, perpindahan dan pengecekan branch, *commit*, *push*, dan *Pull Request*), pemahaman kegagalan Git *hook* (Husky) akibat masalah akses Node.js dan `npx` di *environment* lokal, serta bantuan penyusunan deskripsi PR dan dokumentasi AI Disclosure modul Donasi.

#### Tanggung Jawab dan Verifikasi

- **Inisiatif dan eksplorasi** berada di tangan saya. Saya menentukan fitur yang perlu dibuat, menyampaikan kebutuhan implementasi, dan memberikan konteks (struktur proyek, potongan kode, dan pesan *error*) agar bantuan AI relevan.
- Saran, contoh implementasi, dan potongan kode dari AI digunakan sebagai **referensi dan dasar pengerjaan**, lalu dipelajari, diperiksa, dan disesuaikan kembali dengan struktur serta kebutuhan modul Donasi.
- Setiap perubahan **diverifikasi** dengan menjalankan kode di *environment* lokal, mencoba fitur secara langsung, serta menjalankan migrasi dan pengujian otomatis.
- **Keputusan akhir** terkait penggunaan, penyesuaian, dan penerapan solusi tetap berada di tangan saya berdasarkan kebutuhan proyek dan hasil pengujian. Penggunaan AI tidak menggantikan proses peninjauan, penyesuaian, dan pengujian yang saya lakukan.

### Help Desk, Dashboard Admin, Akun & Autentikasi, dan Notifikasi — Steven Dyanizha Ananda

Pernyataan ini berlaku untuk modul **Help Desk** (`apps/helpdesk`), **Dashboard Admin** (`apps/dashboard`), **Akun & Autentikasi** (`apps/accounts`), dan **Notifikasi** (`apps/notifications`).

#### Alat yang Digunakan

- **Claude Code** (Anthropic), digunakan sebagai asisten pemrograman di terminal dan *code editor*.

#### Bentuk Penggunaan

AI digunakan sebagai **alat bantu**, bukan pengganti proses berpikir dan pengambilan keputusan. Saya handle 90% dari bagian backend dan logika bisnis aplikasi, arsitektur sistem, dan kerangka tampilan. Secara garis besar, AI dimanfaatkan untuk:

1. **Diskusi rancangan dan arsitektur**, misalnya pembagian logika antara `views.py` dan `services.py`, rancangan alur status tiket, aturan hak akses (siapa yang boleh melihat, membalas, dan mengelola tiket), serta aturan pengiriman notifikasi lintas modul.
2. **Peninjauan kode (*code review*)** untuk menemukan *bug*, celah keamanan (misalnya kontrol akses dan validasi unggahan), serta masalah performa seperti *query* N+1.
3. ***Debugging*** saat terjadi *error*, termasuk penelusuran masalah migrasi dan *error* 500 ketika *deployment* ke PWS.
4. ***Refactoring*** dan penyelarasan gaya kode agar konsisten dengan modul lain dan design system.
5. **Penulisan dan perluasan pengujian otomatis**, terutama untuk kasus batas (*edge case*) dan aturan hak akses.
6. **Penyusunan dokumentasi**, termasuk README ini, *docstring*, dan komentar kode.

#### Tanggung Jawab dan Verifikasi

- Seluruh keluaran AI **dibaca, dipahami, dan disesuaikan** sebelum digunakan. Kode yang tidak saya pahami tidak saya masukkan ke dalam proyek.
- Setiap perubahan **diverifikasi** melalui pengujian otomatis (`python manage.py test`), *linting* Ruff, pipeline CI, dan pengujian manual di browser.
- **Keputusan akhir** terkait fitur, rancangan basis data, alur pengguna, dan tampilan tetap berada di tangan saya sebagai penanggung jawab modul.
- Saya **bertanggung jawab penuh** atas kebenaran, keamanan, dan kualitas seluruh kode pada modul-modul tersebut, serta siap menjelaskan setiap bagiannya saat evaluasi.

### Tujuan Pernyataan

Pernyataan-pernyataan di atas dibuat sebagai bentuk **transparansi dan integritas akademik**. Pemanfaatan AI dalam proyek ini dilakukan dengan tujuan mempercepat iterasi dan meningkatkan kualitas perangkat lunak, sekaligus tetap menjadikan proses ini sebagai sarana belajar rekayasa perangkat lunak secara utuh.