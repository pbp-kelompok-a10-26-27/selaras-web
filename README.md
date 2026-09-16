# SELARAS: Platform Membangun Kebiasaan Hidup Berkelanjutan

## Deskripsi Aplikasi
SELARAS adalah platform digital yang membantu penggunanya membangun kebiasaan hidup ramah lingkungan secara konsisten lewat lima layanan: **Artikel & Edukasi** (bacaan reflektif seputar eco-mindfulness), **Challenge** (tantangan terstruktur harian/mingguan dengan pelacakan progres), **Feed** (ruang berbagi progres dan momen sadar lingkungan antarpengguna), **Donasi & Aksi Lingkungan** (penggalangan dana untuk isu lingkungan lokal), serta **Help Desk** (dukungan seputar layanan dan akun).

Aplikasi ini menjawab kesulitan yang umum dialami orang yang ingin hidup lebih berkelanjutan: niat baik yang mudah luntur karena tidak ada struktur atau pengingat, konten edukasi lingkungan yang sering generik dan menggurui tanpa konteks nyata, minimnya ruang untuk berbagi progres dengan sesama yang punya nilai serupa, serta kebingungan menyalurkan kepedulian terhadap isu lingkungan sekitar menjadi aksi kolektif yang nyata.

SELARAS menjawab hal tersebut lewat challenge terarah dengan pelacakan progres harian dan apresiasi berupa badge/streak, artikel yang dilengkapi rekomendasi produk ramah lingkungan sesuai konteks bacaan, saran aktivitas berbasis kondisi cuaca untuk challenge luar ruangan, feed komunitas untuk saling mendukung, serta kanal donasi khusus untuk isu lingkungan lokal yang progresnya transparan.

**Manfaat bagi masyarakat:**
* **Kebiasaan berkelanjutan yang terstruktur** — challenge terjadwal dengan pelacakan progres harian, badge & streak sebagai bentuk apresiasi konsistensi
* **Edukasi kontekstual** — artikel reflektif yang terhubung langsung dengan rekomendasi produk nyata ber-Eco-Score, bukan sekadar teori
* **Aksi kolektif nyata** — kanal donasi untuk isu lingkungan lokal yang bisa dipantau progresnya, bukan sekadar wacana
* **Dukungan komunitas** — feed untuk berbagi progres dan saling menyemangati, didukung layanan bantuan yang responsif

## Anggota Kelompok
| Nama | NPM |
|---|---|
| Callista Putri Anjola | 2506603740 |
| Joel Sheldy Sucipto | 250662494 |
| Asfara Quaneisha Syafaziel | 2506603532 |
| Fayyad Mohammad Madani | 2506622720 |
| Steven Dyanizha Ananda | 2506616112 |

## Daftar Modul & Pembagian Kerja
| Modul | Deskripsi | Penanggung Jawab |
|---|---|---|
| Artikel & Edukasi | CRUD artikel edukatif-reflektif seputar eco-mindfulness, dikategorikan per topik; artikel bertema makanan/konsumsi menampilkan rekomendasi produk dari Open Food Facts | Caca |
| Challenge | CRUD challenge terstruktur beserta pelacakan partisipasi & progres harian user, dengan badge/streak sebagai apresiasi; challenge outdoor menampilkan saran cuaca dari Open-Meteo | Fayyad |
| Feed / Postingan | CRUD post berbagi progres/momen sadar lingkungan antaruser beserta like dan komentar | Joel |
| Donasi & Aksi Lingkungan | CRUD kampanye penggalangan dana untuk isu lingkungan lokal beserta pencatatan & verifikasi donasi komunitas | Neisha |
| Help Desk / Customer Service | CRUD tiket keluhan/pertanyaan seputar layanan, akun, atau kendala teknis pengguna | Steven |

## Sumber Public API

**1. Open Food Facts** — digunakan di Modul Artikel & Edukasi untuk menampilkan rekomendasi produk ramah lingkungan (nama, brand, kategori, Eco-Score) yang relevan pada artikel bertema makanan/konsumsi. Data diambil langsung saat halaman diakses (fetch-on-request, tidak disimpan sebagai model tersendiri) dan difilter berdasarkan grade Eco-Score. Tidak memerlukan API key.

- Dokumentasi: https://openfoodfacts.github.io/openfoodfacts-server/api/

**2. Open-Meteo** — digunakan di Modul Challenge untuk menampilkan saran aktivitas berdasarkan kondisi cuaca, khusus untuk challenge bertipe aktivitas luar ruangan. Data diambil berdasarkan lokasi (kota/koordinat) yang diinput pengguna secara teks, tanpa peta interaktif. Tidak memerlukan API key.

- Dokumentasi: https://open-meteo.com/en/docs

## Jenis/Peran Pengguna
1. **Admin** — mengelola dan mempublikasikan artikel, membuat dan mengatur challenge, memverifikasi donasi serta mengelola campaign, menjawab dan menutup tiket Help Desk, serta memoderasi konten yang melanggar di seluruh modul.
2. **Pengguna (User)** — membaca artikel, mengikuti challenge dan mencatat progres harian, memposting momen di feed serta berinteraksi dengan pengguna lain, memberikan donasi ke campaign lingkungan, dan mengajukan tiket bantuan ke Help Desk.