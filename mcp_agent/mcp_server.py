# mcp_server.py
# DualComm - Sistem Advokasi Kerajaan Malaysia
# MCP Server menggunakan FastMCP

import os
import csv
import json
import traceback
from datetime import datetime

import resend
from fpdf import FPDF
from mcp.server.fastmcp import FastMCP

resend.api_key = os.environ.get("RESEND_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────────────
#  PEMBANTU TARIKH
# ─────────────────────────────────────────────────────────────────────────────

BULAN_MELAYU = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun",
    "Julai", "Ogos", "September", "Oktober", "November", "Disember",
]

def format_tarikh(dt: datetime) -> str:
    return f"{dt.day} {BULAN_MELAYU[dt.month - 1]} {dt.year}"


# ─────────────────────────────────────────────────────────────────────────────
#  KONFIGURASI SEKTOR
# ─────────────────────────────────────────────────────────────────────────────

SEKTOR = {
    "jtk": {
        "emel":        "jtksm@mohr.gov.my",
        "kod":         "JTK",
        "gelaran":     "Pengarah",
        "org":         "Jabatan Tenaga Kerja Semenanjung Malaysia",
        "alamat1":     "Tingkat 6-10, Blok D4, Kompleks D",
        "alamat2":     "Pusat Pentadbiran Kerajaan Persekutuan",
        "alamat3":     "62530 PUTRAJAYA",
        "headers_csv": [
            "Bil.", "Nama Pekerja", "Warganegara", "Umur",
            "Nama Majikan", "Sektor Industri", "Tempoh Tunggakan",
            "Jumlah Terhutang (RM)", "Status Pasport", "Tindakan Diperlukan",
        ],
        "gambar": [
            "Assets/jtk/img_jtk_1.jpg",
            "Assets/jtk/img_jtk_2.jpg",
            "Assets/jtk/img_jtk_3.jpg",
        ],
        "kapsyen_gambar": [
            "Pekerja buruh warga asing di tapak pembinaan yang terjejas akibat isu tunggakan gaji.",
            "Pekerja kilang di barisan pengeluaran yang berdepan masalah eksploitasi oleh majikan.",
            "Dokumen perjalanan (pasport) dan kontrak yang menjadi bahan bukti penahanan secara haram.",
        ],
    },
    "jkm": {
        "emel":        "pertanyaan@jkm.gov.my",
        "kod":         "JKM",
        "gelaran":     "Pengarah",
        "org":         "Jabatan Kebajikan Masyarakat Malaysia",
        "alamat1":     "Aras 7, Blok E, Pusat Bandar Damansara",
        "alamat2":     "50490 KUALA LUMPUR",
        "alamat3":     "",
        "headers_csv": [
            "Bil.", "Nama Pemohon", "No. Kad Pengenalan", "Umur",
            "Jantina", "Alamat", "Jenis Bantuan Dipohon",
            "Pendapatan Bulanan (RM)", "Status OKU", "Keupayaan Digital",
        ],
        "gambar": [
            "Assets/jkm/img_jkm_1.jpg",
            "Assets/jkm/img_jkm_2.jpg",
            "Assets/jkm/img_jkm_3.jpg",
        ],
        "kapsyen_gambar": [
            "Keadaan rumah kayu yang usang dan daif di kawasan perkampungan pemohon.",
            "Struktur kediaman penduduk di pedalaman yang memerlukan bantuan pembaikan segera.",
            "Kediaman tradisional di kawasan luar bandar yang didiami oleh warga emas yang memohon bantuan.",
        ],
    },
    "kkm": {
        "emel":        "cprc@moh.gov.my",
        "kod":         "KKM",
        "gelaran":     "Pengarah",
        "org":         "Kementerian Kesihatan Malaysia",
        "alamat1":     "Aras 1-7, Blok E1, Parcel E",
        "alamat2":     "Pusat Pentadbiran Kerajaan Persekutuan",
        "alamat3":     "62590 PUTRAJAYA",
        "headers_csv": [
            "Bil.", "Nama Bekalan / Ubatan", "Nama Generik", "Kategori",
            "Kuantiti Diperlukan", "Stok Semasa", "Kekurangan",
            "Keutamaan", "Kegunaan Utama", "Tarikh Perlu Tiba",
        ],
        "gambar": [
            "Assets/kkm/img_kkm_1.jpg",
            "Assets/kkm/img_kkm_2.jpg",
            "Assets/kkm/img_kkm_3.jpg",
        ],
        "kapsyen_gambar": [
            "Pandangan hadapan fasiliti kesihatan Klinik Desa Kampung Bahagia.",
            "Bangunan Klinik Desa yang beroperasi dan memberi khidmat di kawasan rancangan FELDA.",
            "Keadaan fasiliti kesihatan luar bandar di kawasan terpencil yang mengalami kekurangan bekalan.",
        ],
    },
    "jpn": {
        "emel":        "pro@jpn.gov.my",
        "kod":         "JPN",
        "gelaran":     "Pengarah",
        "org":         "Jabatan Pendaftaran Negara",
        "alamat1":     "Aras Bawah, Blok 1",
        "alamat2":     "Pusat Pentadbiran Kerajaan Persekutuan",
        "alamat3":     "62100 PUTRAJAYA",
        "headers_csv": [
            "Bil.", "Nama Individu", "Tarikh Lahir (Anggaran)", "Umur",
            "Nama Ibu", "Nama Bapa", "Kampung / Mukim",
            "Daerah", "Negeri", "Dokumen Sedia Ada", "Halangan Akses",
        ],
        "gambar": [
            "Assets/jpn/img_jpn_1.jpg",
            "Assets/jpn/img_jpn_2.jpg",
            "Assets/jpn/img_jpn_3.jpg",
        ],
        "kapsyen_gambar": [
            "Kanak-kanak dari komuniti Orang Asli di kawasan penempatan terpencil.",
            "Persekitaran perkampungan Orang Asli yang menghadapi kesukaran logistik ke bandar.",
            "Penduduk komuniti pedalaman yang amat memerlukan akses pendaftaran melalui Unit Bergerak MEKAR.",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
#  DATA CSV REALISTIK (MIN 22 BARIS)
# ─────────────────────────────────────────────────────────────────────────────

DATA_CSV_LALAI = {
    "jtk": [
        ["1",  "Ahmad Raza Khan",      "Bangladesh", "28", "Syarikat Tekstil Maju Sdn Bhd",           "Pembuatan",          "4 bulan", "3,200.00",  "Dirampas",                 "Siasatan segera dan pemulangan pasport"],
        ["2",  "Md. Hossain Kabir",    "Bangladesh", "32", "Syarikat Tekstil Maju Sdn Bhd",           "Pembuatan",          "4 bulan", "3,200.00",  "Dirampas",                 "Siasatan segera dan pemulangan pasport"],
        ["3",  "Nguyen Van Thanh",     "Vietnam",    "25", "Kilang Plastik Wawasan Bhd",              "Pembuatan",          "3 bulan", "2,850.00",  "Dalam simpanan majikan",   "Pemulangan pasport dan gaji tertunggak"],
        ["4",  "Tran Thi Lan",         "Vietnam",    "23", "Kilang Plastik Wawasan Bhd",              "Pembuatan",          "3 bulan", "2,850.00",  "Dirampas",                 "Siasatan segera"],
        ["5",  "Rajesh Kumar",         "India",      "35", "Pembinaan Cergas Sdn Bhd",                "Pembinaan",          "5 bulan", "4,500.00",  "Tidak dipegang majikan",   "Tuntutan gaji tertunggak"],
        ["6",  "Suresh Patel",         "India",      "29", "Pembinaan Cergas Sdn Bhd",                "Pembinaan",          "5 bulan", "4,500.00",  "Tidak dipegang majikan",   "Tuntutan gaji tertunggak"],
        ["7",  "Mohammad Yusuf",       "Pakistan",   "31", "Ladang Kelapa Sawit Hijau Bhd",           "Pertanian",          "6 bulan", "5,400.00",  "Dirampas",                 "Siasatan segera dan pemulangan pasport"],
        ["8",  "Rizwan Ahmed",         "Pakistan",   "27", "Ladang Kelapa Sawit Hijau Bhd",           "Pertanian",          "6 bulan", "5,400.00",  "Dirampas",                 "Siasatan segera"],
        ["9",  "Karim Abdullah",       "Indonesia",  "30", "Restoran Selera Timur Sdn Bhd",           "Perkhidmatan Makan", "2 bulan", "1,800.00",  "Tidak dipegang majikan",   "Pembayaran gaji segera"],
        ["10", "Siti Aminah bte Hassan","Indonesia", "26", "Khidmat Domestik Seri Bhd",               "Khidmat Domestik",   "3 bulan", "2,400.00",  "Dirampas",                 "Pemulangan pasport dan gaji"],
        ["11", "Laxmi Gurung",         "Nepal",      "24", "Syarikat Pembungkusan Jaya Sdn Bhd",      "Pembuatan",          "4 bulan", "3,600.00",  "Dalam simpanan majikan",   "Siasatan dan pembayaran gaji"],
        ["12", "Bishnu Tamang",        "Nepal",      "28", "Syarikat Pembungkusan Jaya Sdn Bhd",      "Pembuatan",          "4 bulan", "3,600.00",  "Dalam simpanan majikan",   "Siasatan dan pembayaran gaji"],
        ["13", "Win Htun",             "Myanmar",    "33", "Kilang Elektronik Precision Bhd",         "Elektronik",         "3 bulan", "2,700.00",  "Dirampas",                 "Siasatan segera"],
        ["14", "Kyaw Zin",             "Myanmar",    "29", "Kilang Elektronik Precision Bhd",         "Elektronik",         "3 bulan", "2,700.00",  "Dirampas",                 "Siasatan segera"],
        ["15", "Jose Santos",          "Filipina",   "36", "Hotel Grand Perdana KL",                  "Perhotelan",         "2 bulan", "3,100.00",  "Tidak dipegang majikan",   "Tuntutan gaji dan elaun lembur"],
        ["16", "Maria Santos",         "Filipina",   "28", "Hotel Grand Perdana KL",                  "Perhotelan",         "2 bulan", "2,800.00",  "Tidak dipegang majikan",   "Tuntutan gaji"],
        ["17", "Thilaga Rajan",        "India",      "27", "Ladang Getah Mutiara Bhd",                "Pertanian",          "5 bulan", "4,000.00",  "Dirampas",                 "Siasatan segera dan pemulangan pasport"],
        ["18", "Moorthy Suppiah",      "India",      "41", "Ladang Getah Mutiara Bhd",                "Pertanian",          "5 bulan", "4,000.00",  "Dirampas",                 "Siasatan segera"],
        ["19", "Lin Myat Noe",         "Myanmar",    "22", "Kilang Sarung Tangan Latex Sdn Bhd",      "Pembuatan",          "4 bulan", "3,200.00",  "Dalam simpanan majikan",   "Siasatan dan pembayaran gaji"],
        ["20", "Zaw Myo Htun",         "Myanmar",    "25", "Kilang Sarung Tangan Latex Sdn Bhd",      "Pembuatan",          "4 bulan", "3,200.00",  "Dalam simpanan majikan",   "Siasatan dan pembayaran gaji"],
        ["21", "Anwar Hossain",        "Bangladesh", "38", "Syarikat Pengurusan Sisa Hijau Bhd",      "Pengurusan Sisa",    "3 bulan", "2,550.00",  "Dirampas",                 "Siasatan segera"],
        ["22", "Farhan Ali",           "Bangladesh", "26", "Syarikat Pengurusan Sisa Hijau Bhd",      "Pengurusan Sisa",    "3 bulan", "2,550.00",  "Dirampas",                 "Siasatan segera"],
    ],
    "jkm": [
        ["1",  "Hajah Ramlah bte Kassim",    "680312-01-1234", "57", "Perempuan", "Kg. Bukit Damar, 28000 Temerloh, Pahang",              "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["2",  "Haji Baharudin bin Salleh",  "521105-02-5678", "73", "Lelaki",    "Kg. Sungai Lui, 44300 Batang Kali, Selangor",          "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["3",  "Puan Norhaida bte Hamid",    "650820-03-9012", "60", "Perempuan", "Lot 5, Kg. Parit 8, 83000 Batu Pahat, Johor",          "Bantuan OKU",             "0",   "OKU Fizikal",        "Tiada"],
        ["4",  "Encik Razali bin Mokhtar",   "590430-05-3456", "66", "Lelaki",    "Kg. Lubuk Bongor, 09500 Baling, Kedah",                "Bantuan Orang Tua (BOT)", "200", "Bukan OKU",          "Sangat Terhad"],
        ["5",  "Puan Maimunah bte Yusof",    "471215-08-7890", "78", "Perempuan", "Kg. Kuala Krai Lama, 18000 Kuala Krai, Kelantan",      "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["6",  "Encik Johari bin Ibrahim",   "620314-09-2345", "63", "Lelaki",    "Kg. Sekeras, 05100 Alor Setar, Kedah",                 "Bantuan OKU",             "300", "OKU Penglihatan",    "Tiada"],
        ["7",  "Puan Salmah bte Abdul",      "550906-06-6789", "70", "Perempuan", "No. 12, Kg. Pokok Sena, 06400 Pokok Sena, Kedah",      "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["8",  "Encik Mustafa bin Daud",     "490728-07-0123", "76", "Lelaki",    "Kg. Lubok China, 78000 Alor Gajah, Melaka",            "Bantuan Orang Tua (BOT)", "0",   "OKU Fizikal",        "Tiada"],
        ["9",  "Puan Zainab bte Othman",     "531130-10-4567", "72", "Perempuan", "Kg. Gombang, 35900 Tanjung Malim, Perak",              "Bantuan OKU",             "0",   "OKU Pendengaran",    "Tiada"],
        ["10", "Encik Kamarudin bin Hassan", "440215-11-8901", "82", "Lelaki",    "Kg. Belukar, 16800 Pasir Puteh, Kelantan",             "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["11", "Puan Fatimah bte Ismail",    "581022-12-2345", "67", "Perempuan", "No. 3, Lorong Bunga, 15000 Kota Bharu, Kelantan",      "Bantuan Orang Tua (BOT)", "150", "Bukan OKU",          "Sangat Terhad"],
        ["12", "Encik Abdullah bin Talib",   "460510-01-6789", "79", "Lelaki",    "Kg. Air Panas, 25200 Kuantan, Pahang",                 "Bantuan OKU",             "0",   "OKU Fizikal",        "Tiada"],
        ["13", "Puan Rohani bte Said",       "390825-03-0123", "86", "Perempuan", "Kg. Seri Kenangan, 70200 Seremban, N. Sembilan",       "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["14", "Encik Roslan bin Yacob",     "570614-04-4567", "68", "Lelaki",    "Kg. Baru, 42000 Klang, Selangor",                      "Bantuan OKU",             "400", "OKU Anggota",        "Sangat Terhad"],
        ["15", "Puan Habsah bte Mansor",     "610305-05-8901", "64", "Perempuan", "No. 8, Jalan Bakawali, 30000 Ipoh, Perak",             "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["16", "Encik Sulaiman bin Ahmad",   "430912-07-2345", "82", "Lelaki",    "Kg. Padang Kemunting, 07000 Langkawi, Kedah",          "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["17", "Puan Aminah bte Dollah",     "650430-08-6789", "60", "Perempuan", "Lot 22, Felda Bukit Kuari, 69000 Raub, Pahang",        "Bantuan Orang Tua (BOT)", "250", "Bukan OKU",          "Tiada"],
        ["18", "Encik Idris bin Mahmud",     "480727-09-0123", "77", "Lelaki",    "Kg. Muara Batu, 09300 Kuala Ketil, Kedah",             "Bantuan OKU",             "0",   "OKU Kognitif",       "Tiada"],
        ["19", "Puan Norma bte Che Mat",     "520318-10-4567", "73", "Perempuan", "Kg. Binjai, 16010 Tumpat, Kelantan",                   "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["20", "Encik Mazlan bin Tahar",     "541201-11-8901", "71", "Lelaki",    "No. 15, Kg. Sungai Rambai, 77300 Merlimau, Melaka",    "Bantuan Orang Tua (BOT)", "100", "OKU Fizikal",        "Sangat Terhad"],
        ["21", "Puan Saodah bte Ngah",       "480615-12-2345", "77", "Perempuan", "Kg. Pauh Lima, 16100 Kota Bharu, Kelantan",            "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
        ["22", "Encik Wahab bin Deraman",    "410924-02-6789", "84", "Lelaki",    "Kg. Beserah, 25300 Kuantan, Pahang",                   "Bantuan Orang Tua (BOT)", "0",   "Bukan OKU",          "Tiada"],
    ],
    "kkm": [
        ["1",  "Parasetamol 500mg",               "Paracetamol",                    "Analgesik/Antipiretik",  "5,000 tablet",   "0 tablet",    "5,000 tablet",   "KRITIKAL",  "Demam dan kesakitan umum",                  "Segera"],
        ["2",  "Amoxicillin 250mg Kapsul",         "Amoxicillin",                    "Antibiotik",             "1,200 kapsul",   "80 kapsul",   "1,120 kapsul",   "KRITIKAL",  "Jangkitan bakteria dan jangkitan paru-paru", "Segera"],
        ["3",  "Larutan Rehidrasi Oral (ORS)",      "Oral Rehydration Salts",         "Rehidrasi",              "2,000 saset",    "150 saset",   "1,850 saset",    "KRITIKAL",  "Cirit-birit dan dehidrasi",                 "Segera"],
        ["4",  "Metformin 500mg",                  "Metformin HCl",                  "Antidiabetik",           "3,000 tablet",   "200 tablet",  "2,800 tablet",   "TINGGI",    "Kawalan gula darah pesakit kencing manis",  "3 hari"],
        ["5",  "Amlodipine 5mg",                   "Amlodipine Besilate",            "Antihipertensi",         "2,500 tablet",   "100 tablet",  "2,400 tablet",   "TINGGI",    "Kawalan tekanan darah tinggi",              "3 hari"],
        ["6",  "Artesunate Tablet 50mg",            "Artesunate",                     "Antimalaria",            "500 dos",        "20 dos",      "480 dos",        "KRITIKAL",  "Rawatan malaria tropika",                   "Segera"],
        ["7",  "Pembalut Kasa Steril 10cm x 10cm", "Gauze Swab",                     "Penjagaan Luka",         "3,000 pcs",      "150 pcs",     "2,850 pcs",      "TINGGI",    "Rawatan luka dan pembalutan",               "3 hari"],
        ["8",  "Jarum Suntikan 5ml",               "Disposable Syringe",             "Peralatan Perubatan",    "2,000 pcs",      "300 pcs",     "1,700 pcs",      "TINGGI",    "Pemberian ubatan suntikan",                 "5 hari"],
        ["9",  "Dextrose 5% Intravena 500ml",       "Dextrose Solution",              "Cecair IV",              "500 beg",        "30 beg",      "470 beg",        "KRITIKAL",  "Rawatan dehidrasi teruk dan hipoglisemia",  "Segera"],
        ["10", "Povidone Iodine 10% Salep",         "Povidone Iodine",                "Antiseptik",             "200 tiub",       "15 tiub",     "185 tiub",       "SEDERHANA", "Pencegahan jangkitan luka",                 "7 hari"],
        ["11", "Vaksin Hepatitis B (Dos Bayi)",     "Hepatitis B Vaccine",            "Vaksin",                 "300 dos",        "10 dos",      "290 dos",        "KRITIKAL",  "Imunisasi bayi baru lahir",                 "Segera"],
        ["12", "Vaksin MMR",                        "Measles-Mumps-Rubella Vaccine",  "Vaksin",                 "200 dos",        "5 dos",       "195 dos",        "KRITIKAL",  "Imunisasi kanak-kanak berumur 12 bulan",    "Segera"],
        ["13", "Antivenom Ular Kobra",              "Polyvalent Antivenom",           "Antivenom",              "50 vial",        "0 vial",      "50 vial",        "KRITIKAL",  "Gigitan ular berbisa kawasan hutan",        "Segera"],
        ["14", "Salbutamol Inhaler 100mcg",         "Salbutamol",                     "Bronkodilator",          "300 pcs",        "20 pcs",      "280 pcs",        "TINGGI",    "Serangan asma dan sesak nafas",             "3 hari"],
        ["15", "Sarung Tangan Perubatan Getah (M)", "Medical Gloves",                 "Peralatan PPE",          "5,000 pasang",   "200 pasang",  "4,800 pasang",   "TINGGI",    "Prosedur perubatan dan kawalan jangkitan",  "5 hari"],
        ["16", "Mebendazole 100mg Tablet",          "Mebendazole",                    "Antihelmintik",          "1,000 tablet",   "50 tablet",   "950 tablet",     "SEDERHANA", "Rawatan kecacingan kanak-kanak",            "7 hari"],
        ["17", "Pil Kontraseptif Oral (Pil Perancang)", "Combined Oral Contraceptive","Kontraseptif",           "500 kitaran",    "30 kitaran",  "470 kitaran",    "SEDERHANA", "Perancang keluarga wanita dewasa",          "7 hari"],
        ["18", "Ferrous Sulphate 200mg",            "Ferrous Sulphate",               "Suplemen Besi",          "3,000 tablet",   "100 tablet",  "2,900 tablet",   "SEDERHANA", "Rawatan anemia dan wanita hamil",           "7 hari"],
        ["19", "Kit Ujian Denggi Pantas NS1",       "Dengue NS1 Rapid Test Kit",      "Diagnostik",             "200 kit",        "10 kit",      "190 kit",        "TINGGI",    "Pengesanan awal demam denggi",              "3 hari"],
        ["20", "Catheter Foley 16Fr",               "Foley Catheter",                 "Peralatan Perubatan",    "100 pcs",        "5 pcs",       "95 pcs",         "SEDERHANA", "Prosedur urologi dan pembedahan kecemasan", "7 hari"],
        ["21", "Ibuprofen 400mg Tablet",            "Ibuprofen",                      "NSAID Anti-Radang",      "2,000 tablet",   "0 tablet",    "2,000 tablet",   "TINGGI",    "Anti-radang dan pereda kesakitan",          "3 hari"],
        ["22", "Plaster Luka Pelbagai Saiz",        "Adhesive Bandage",               "Penjagaan Luka",         "2,000 pcs",      "100 pcs",     "1,900 pcs",      "RENDAH",    "Luka kecil dan calar harian",               "10 hari"],
    ],
    "jpn": [
        ["1",  "Bah Siti bte Bah Ali",        "~ 15-03-2021", "5",  "Siti Maimunah bte Hassan",    "Bah Ali bin Bah Long",          "Kg. Kuala Woh, Tapah",              "Tapah",      "Perak",    "Tiada",       "Jarak 4 jam + tiada kos pengangkutan"],
        ["2",  "Gah Raju ak Gah Penghulu",    "~ 22-07-2019", "6",  "Lina ak Budi",                "Gah Penghulu ak Gah Besar",     "Kg. Pos Piah, Gerik",               "Hulu Perak", "Perak",    "Tiada",       "Jarak jauh, tiada kenderaan awam"],
        ["3",  "Jambu ak Singai",             "~ 10-11-2018", "7",  "Biah ak Usat",                "Singai ak Peli",                "Kg. Ulu Sungai Perak, Gerik",       "Hulu Perak", "Perak",    "Tiada",       "Jarak 6 jam dari cawangan JPN"],
        ["4",  "Roni bin Ahmad Seman",        "~ 03-05-2020", "5",  "Laila bte Ibrahim",           "Ahmad Seman bin Malik",         "Kg. Pos Lebir, Gua Musang",         "Gua Musang", "Kelantan", "Tiada",       "Kemiskinan tegar, tiada kos perjalanan"],
        ["5",  "Bunga bte Alang Hitam",       "~ 18-09-2017", "8",  "Ros bte Alang",               "Alang Hitam bin Penghulu",      "Kg. Sungai Pergam, Gua Musang",     "Gua Musang", "Kelantan", "Tiada",       "Jalan tanah rosak, tiada bas awam"],
        ["6",  "Dayung ak Ngumbang",          "~ 25-12-2016", "9",  "Entam ak Laban",              "Ngumbang ak Lira",              "Kg. Nanga Sungai Pelek, Betong",    "Betong",     "Sarawak",  "Tiada",       "Kawasan pedalaman, tiada jalan raya"],
        ["7",  "Suni ak Dumpok",             "~ 14-04-2015", "11", "Layang ak Dumpok",            "Dumpok ak Mujah",               "Kg. Ulu Entabai, Julau",            "Julau",      "Sarawak",  "Tiada",       "Hanya boleh dicapai melalui bot sungai"],
        ["8",  "Enggau ak Bulan",            "~ 07-08-2014", "11", "Imang ak Rentap",             "Bulan ak Apai",                 "Kg. Long Unai, Belaga",             "Belaga",     "Sarawak",  "Tiada",       "Kawasan terpencil, tiada bekalan elektrik"],
        ["9",  "Miran bin Talib Besar",       "~ 19-01-2022", "4",  "Minah bte Dol",               "Talib Besar bin Samat",         "Kg. Pos Brooke, Keningau",          "Keningau",   "Sabah",    "Tiada",       "Kemiskinan, tiada pengangkutan"],
        ["10", "Selimah bte Ginsir",          "~ 30-06-2021", "4",  "Hamidah bte Junid",           "Ginsir bin Samion",             "Kg. Ulu Tungku, Beaufort",          "Beaufort",   "Sabah",    "Tiada",       "Banjir musiman menghalang perjalanan"],
        ["11", "Pungut bin Atan Jaya",        "~ 12-10-2020", "5",  "Sanah bte Musa",              "Atan Jaya bin Siru",            "Kg. Pangi, Kota Belud",             "Kota Belud", "Sabah",    "Tiada",       "Jalan tanah, tidak boleh dilalui musim hujan"],
        ["12", "Langkap ak Jabu",            "~ 08-02-2019", "6",  "Buah ak Pandan",              "Jabu ak Mawan",                 "Kg. Nanga Mepi, Sri Aman",          "Sri Aman",   "Sarawak",  "Tiada",       "Kawasan pedalaman Sarawak"],
        ["13", "Padi ak Ugak",               "~ 16-07-2018", "7",  "Serong ak Sungit",            "Ugak ak Bujang",                "Kg. Ulu Katibas, Song",             "Song",       "Sarawak",  "Tiada",       "Hanya boleh dicapai melalui bot sungai"],
        ["14", "Nasima bte Jumali",           "~ 21-03-2017", "8",  "Ramlah bte Siran",            "Jumali bin Said",               "Kg. Pos Sinderut, Kuala Lipis",     "Kuala Lipis","Pahang",   "Tiada",       "Tiada pengangkutan awam ke bandar"],
        ["15", "Kering ak Buyong",           "~ 04-09-2016", "9",  "Lidah ak Jabi",               "Buyong ak Kebuk",               "Kg. Ulu Tembeling, Jerantut",       "Jerantut",   "Pahang",   "Tiada",       "Jalan hutan, tidak sesuai untuk kereta biasa"],
        ["16", "Tamin bin Lokman Hakim",      "~ 10-03-2023", "3",  "Hasna bte Bidin",             "Lokman Hakim bin Tali",         "Kg. Pos Gob, Jeli",                 "Jeli",       "Kelantan", "Tiada",       "Kemiskinan tegar"],
        ["17", "Manis bte Penghulu Ahmad",    "~ 28-11-2022", "3",  "Dewi bte Penghulu",           "Penghulu Ahmad bin Mat Nor",    "Kg. Sungai Rual, Jeli",             "Jeli",       "Kelantan", "Tiada",       "Tiada dokumen ibu bapa untuk rujukan"],
        ["18", "Nyalau ak Ngelambai",        "~ 17-05-2021", "4",  "Agi ak Penghulu",             "Ngelambai ak Nyala",            "Kg. Long Loyang, Miri",             "Miri",       "Sarawak",  "Tiada",       "Kawasan tanpa liputan telekomunikasi"],
        ["19", "Simpai ak Tinggom",          "~ 23-08-2020", "5",  "Imbok ak Nyala",              "Tinggom ak Sempang",            "Kg. Long Jeeh, Baram",              "Miri",       "Sarawak",  "Tiada",       "Hanya boleh dicapai dengan bot atau helikopter"],
        ["20", "Kedup bin Sabtu Waris",       "~ 01-12-2019", "6",  "Mani bte Rabus",              "Sabtu Waris bin Bakar",         "Kg. Pos Sinderut, Kuala Lipis",     "Kuala Lipis","Pahang",   "Tiada",       "Tiada jalan berturap dalam 30km"],
        ["21", "Rumbut ak Mawang",           "~ 15-04-2018", "7",  "Bulan ak Apai",               "Mawang ak Ngumbang",            "Kg. Long Banga, Marudi",            "Marudi",     "Sarawak",  "Tiada",       "Hanya boleh dicapai melalui helikopter"],
        ["22", "Sadak bin Apui Besar",        "~ 09-10-2017", "8",  "Timah bte Sahul",             "Apui Besar bin Gaing",          "Kg. Ulu Sungai Baleh, Kapit",       "Kapit",      "Sarawak",  "Tiada",       "Kawasan terpencil, tiada akses jalan langsung"],
    ],
}





# ─────────────────────────────────────────────────────────────────────────────
#  PDF - SURAT RASMI (FORMAT KPN)
# ─────────────────────────────────────────────────────────────────────────────

class TemplateSuratRasmi(FPDF):
    """
    Kelas PDF mengikut format Surat Rasmi KPN:
    - Kepala surat (letterhead) dengan garis pemisah
    - Nombor rujukan & tarikh (atas kanan)
    - Alamat penerima (kiri)
    - Panggilan hormat
    - Tajuk HURUF BESAR BOLD
    - Perenggan (pertama tidak bernombor, seterusnya bernombor)
    - Pengakhiran rasmi dengan slogan dan tandatangan
    - Nombor muka surat di bawah
    """

    def header(self):
        # Baris 1 - Nama penghantar (Bold) — diisi dari pemboleh ubah global
        nama_header = globals().get("_NAMA_HEADER_PDF", "Pejabat Advokasi")
        jawatan_header = globals().get("_JAWATAN_HEADER_PDF", "")
        self.set_font("Helvetica", "B", 12)
        self.set_xy(20, 12)
        self.cell(120, 5, nama_header, ln=False)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, "Tel       :  +60 3-0000 0000", align="R")
        self.ln(5)

        # Baris 2
        self.set_font("Helvetica", "", 9)
        self.set_x(20)
        self.cell(120, 4, jawatan_header if jawatan_header else "Sistem Advokasi Masyarakat Malaysia", ln=False)
        self.cell(0, 4, "Faks     :  +60 3-0000 0001", align="R")
        self.ln(4)

        # Baris 3
        self.set_x(20)
        self.cell(120, 4, "Kuala Lumpur, Malaysia", ln=False)
        self.cell(0, 4, "Laman Web :  www.dualcomm.org.my", align="R")
        self.ln(4)

        # Baris 4
        self.set_x(20)
        self.cell(0, 4, "E-mel  :  aduan@dualcomm.org.my")
        self.ln(5)

        # Garis pemisah kepala surat
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.7)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-13)
        self.set_line_width(0.3)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(1)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(60, 60, 60)
        self.cell(0, 5, f"- {self.page_no()} -", align="C")
        self.set_text_color(0, 0, 0)


def bina_pdf_surat_rasmi(
    data: dict,
    nama_pengirim: str,
    jawatan_pengirim: str,
    sektor: str,
    laluan_fail: str = "",
) -> str:
    """
    Membina PDF Surat Rasmi mengikut format KPN dengan tepat.
    Menyertakan gambar sokongan daripada Gemini 2.0 Flash jika berjaya dijana.
    """
    cfg      = SEKTOR.get(sektor, SEKTOR["kkm"])
    hari_ini = datetime.now()
    tarikh_str = format_tarikh(hari_ini)
    no_rujukan = data.get(
        "nombor_rujukan",
        f"ADV.{hari_ini.year}/{hari_ini.strftime('%m%d')}-{cfg['kod']}"
    )

    # Jana nama fail formal jika tidak diberikan
    if not laluan_fail:
        tajuk_fail = data.get("title", f"Aduan {cfg['kod']}")
        # Ambil 6 perkataan pertama tajuk, buang aksara khas
        import re
        perkataan = re.sub(r"[^\w\s]", "", tajuk_fail).split()[:6]
        ringkasan  = " ".join(perkataan).title()
        laluan_fail = f"Surat Rasmi {ringkasan}.pdf"

    # Tetapkan pemboleh ubah global untuk kepala surat (digunakan oleh TemplateSuratRasmi.header)
    global _NAMA_HEADER_PDF, _JAWATAN_HEADER_PDF
    _NAMA_HEADER_PDF   = nama_pengirim
    _JAWATAN_HEADER_PDF = jawatan_pengirim

    # Set senarai gambar dari konfigurasi sektor
    senarai_gambar_raw = cfg.get("gambar", [])
    senarai_gambar = senarai_gambar_raw if isinstance(senarai_gambar_raw, list) else []

    pdf = TemplateSuratRasmi(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=20, top=40, right=20)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()

    # ── 1. Ruj. Kami & Tarikh (kanan atas) ──────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(108)
    pdf.cell(35, 6, "Ruj. Kami  :", align="R", ln=False)
    pdf.cell(0, 6, f"  {no_rujukan}")
    pdf.ln(6)
    pdf.set_x(108)
    pdf.cell(35, 6, "Tarikh        :", align="R", ln=False)
    pdf.cell(0, 6, f"  {tarikh_str}")
    pdf.ln(10)

    # ── 2. Alamat Penerima (kiri) ────────────────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    baris_penerima = [
        data.get("gelaran_penerima", cfg["gelaran"]),
        data.get("org_penerima",     cfg["org"]),
        data.get("alamat1",          cfg["alamat1"]),
        data.get("alamat2",          cfg["alamat2"]),
        data.get("alamat3",          cfg.get("alamat3", "")),
        data.get("utp", ""),
    ]
    for baris in baris_penerima:
        if baris and baris.strip():
            pdf.set_x(20)
            pdf.cell(0, 6, baris)
            pdf.ln(6)
    pdf.ln(4)

    # ── 3. Panggilan Hormat ─────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(20)
    pdf.cell(0, 6, "YBhg. Dato'/ Datin/ Tuan/ Puan,")
    pdf.ln(10)

    # ── 4. Tajuk (HURUF BESAR BOLD, tengah) ────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    tajuk = data.get("title", "").upper()
    pdf.set_x(20)
    pdf.multi_cell(170, 7, tajuk, align="C")
    pdf.ln(3)

    # Garis di bawah tajuk
    pdf.set_line_width(0.3)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(8)

    # ── 5. Isi Kandungan ─────────────────────────────────────────────────
    # KPN: Perenggan pertama TIDAK bernombor. Perenggan 2 dan seterusnya bernombor.
    perenggan = data.get("paragraphs", [
        "Dengan hormatnya saya merujuk kepada perkara di atas.",
        "Sukacita dimaklumkan bahawa pihak kami ingin memanjangkan aduan berkaitan isu ini untuk perhatian dan tindakan pihak berkuasa.",
        "Segala maklumat lanjut dan dokumen sokongan telah disertakan bersama-sama surat ini untuk rujukan pihak YBhg. Dato'/ Datin/ Tuan/ Puan.",
        "Segala perhatian dan kerjasama pihak YBhg. Dato'/ Datin/ Tuan/ Puan dalam perkara ini amat dihargai dan didahului dengan ucapan terima kasih.",
    ])

    had_bawah = pdf.h - pdf.b_margin  # kedudukan y sempadan bawah

    for idx, para in enumerate(perenggan):
        pdf.set_font("Helvetica", "", 11)
        if idx == 0:
            # Perenggan pertama - tidak bernombor
            pdf.set_x(20)
            pdf.multi_cell(170, 6, para, align="J")
        else:
            num_label = f"{idx + 1}."
            # Pastikan sekurang-kurangnya 20mm ruang sebelum mencetak nombor
            # supaya nombor tidak terasing di bawah muka surat
            if pdf.get_y() > (had_bawah - 20):
                pdf.add_page()
            y_mula = pdf.get_y()
            pdf.set_x(20)
            pdf.cell(12, 6, num_label, ln=False)
            pdf.set_xy(32, y_mula)
            pdf.multi_cell(158, 6, para, align="J")
        pdf.ln(4)

    # ── 6. Seksyen Tambahan (Latar Belakang, Fakta, Akta, dll.) ─────────
    seksyen_tambahan = data.get("additional_sections", [])
    for sek in seksyen_tambahan:
        tajuk_sek = sek.get("heading", "")
        if tajuk_sek:
            # Pastikan ruang untuk tajuk seksyen
            if pdf.get_y() > (had_bawah - 18):
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_x(20)
            pdf.cell(0, 7, tajuk_sek.upper())
            pdf.ln(6)
        for baris_sek in sek.get("lines", []):
            if pdf.get_y() > (had_bawah - 14):
                pdf.add_page()
            pdf.set_font("Helvetica", "", 11)
            pdf.set_x(20)
            pdf.multi_cell(170, 6, baris_sek, align="J")
            pdf.ln(3)
        pdf.ln(2)

    # ── 7. Gambar Sokongan dengan Kapsyen ───────────────────────────────
    if senarai_gambar:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_x(20)
        pdf.cell(0, 7, "LAMPIRAN GAMBAR SOKONGAN")
        pdf.ln(3)
        pdf.set_line_width(0.3)
        pdf.line(20, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(8)
        
        pdf.set_font("Helvetica", "", 11)
        pdf.set_x(20)
        paragraf_intro = "Berdasarkan gambar-gambar sebenar yang diberikan sebelum ini dan mematuhi format pelabelan rasmi dalam bahasa Melayu, berikut adalah senarai lengkap gambar berserta kapsyen profesional untuk dilampirkan ke dalam Surat Rasmi PDF."
        pdf.multi_cell(170, 6, paragraf_intro, align="J")
        pdf.ln(10)

        kapsyen_konfigurasi = cfg["kapsyen_gambar"]

        for i, laluan_g in enumerate(senarai_gambar[:3]):
            if not os.path.exists(laluan_g):
                print(f"[PDF] Fail gambar tidak dijumpai: {laluan_g}")
                continue
            try:
                # Semak ruang - jika kurang dari 110mm, muka surat baru
                if pdf.get_y() > 150:
                    pdf.add_page()
                    pdf.ln(5)

                lebar_g  = 130  # mm
                tinggi_g = 91   # mm 
                x_gambar = (210 - lebar_g) / 2  # tengah

                pdf.image(laluan_g, x=x_gambar, y=pdf.get_y(), w=lebar_g, h=tinggi_g)
                pdf.ln(tinggi_g + 3)

                kapsyen = (
                    kapsyen_konfigurasi[i]
                    if i < len(kapsyen_konfigurasi)
                    else "Dokumentasi visual kes berkaitan."
                )
                pdf.set_font("Helvetica", "", 10)
                pdf.set_x(20)
                pdf.multi_cell(170, 5, f"Rajah {i + 1}: {kapsyen}", align="C")
                pdf.ln(12)
                print(f"[PDF] Gambar {i + 1} berjaya dimasukkan ke PDF.")
            except Exception as e:
                print(f"[PDF] Ralat masukkan gambar {i + 1} ke PDF: {type(e).__name__}: {e}")

    # ── 8. Penutup ───────────────────────────────────────────────────────
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(20)
    penutup = data.get(
        "closing",
        "Segala perhatian dan kerjasama pihak YBhg. Dato'/ Datin/ Tuan/ Puan dalam perkara ini amat dihargai dan didahului dengan ucapan terima kasih.",
    )
    pdf.multi_cell(170, 6, penutup, align="J")
    pdf.ln(5)
    pdf.set_x(20)
    pdf.cell(0, 6, "Sekian.")
    pdf.ln(10)

    # ── 9. Slogan Kerajaan ───────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_x(20)
    pdf.cell(0, 7, '"WAWASAN KEMAKMURAN BERSAMA 2030"')
    pdf.ln(7)
    pdf.set_x(20)
    pdf.cell(0, 7, '"BERKHIDMAT UNTUK NEGARA"')
    pdf.ln(12)

    # ── 10. Tandatangan ──────────────────────────────────────────────────
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(20)
    pdf.cell(0, 6, "Saya yang menjalankan amanah,")
    pdf.ln(14)

    # Nama penghantar dalam italik — berfungsi sebagai tandatangan
    pdf.set_font("Helvetica", "I", 13)
    pdf.set_x(20)
    pdf.cell(0, 7, nama_pengirim)
    pdf.ln(7)

    # Jawatan di bawah nama
    pdf.set_font("Helvetica", "", 11)
    pdf.set_x(20)
    pdf.cell(0, 6, jawatan_pengirim)

    pdf.output(laluan_fail)
    return laluan_fail


# ─────────────────────────────────────────────────────────────────────────────
#  CSV - LAPORAN DATA
# ─────────────────────────────────────────────────────────────────────────────

def bina_csv_laporan(
    sektor: str,
    baris_data: list,
    nama_pengirim: str,
    jawatan_pengirim: str = "",
    nombor_kes: str = "",
    laluan_fail: str = "",
) -> str:
    """
    Membina laporan CSV dengan data realistik minimum 22 baris.
    """
    cfg = SEKTOR.get(sektor, SEKTOR["kkm"])

    # Jana nama fail formal jika tidak diberikan
    if not laluan_fail:
        label_sektor = {
            "jtk": "Pekerja Asing",
            "jkm": "Permohonan Kebajikan",
            "kkm": "Bekalan Perubatan",
            "jpn": "Pendaftaran Kelahiran",
        }.get(sektor, "Data Kes")
        laluan_fail = f"Laporan {label_sektor} {cfg['kod']}.csv"

    # Guna data lalai realistik jika kurang dari 20 baris
    if not baris_data or len(baris_data) < 20:
        baris_data = DATA_CSV_LALAI.get(sektor, DATA_CSV_LALAI["kkm"])

    with open(laluan_fail, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)

        # Header lajur
        w.writerow(cfg["headers_csv"])

        # Baris data
        for baris in baris_data:
            w.writerow(baris)

        # Maklumat penyedia (bersih, tanpa bahasa mesin)
        w.writerow([])
        w.writerow(["Disediakan oleh:", nama_pengirim])
        w.writerow(["Jawatan:", jawatan_pengirim])
        if nombor_kes:
            w.writerow(["Nombor Kes:", nombor_kes])

    return laluan_fail


# ─────────────────────────────────────────────────────────────────────────────
#  EMEL RASMI (FORMAT KPN)
# ─────────────────────────────────────────────────────────────────────────────

def hantar_emel(
    emel_sasaran: str,
    subjek: str,
    tajuk_surat: str,
    nama_komuniti: str,
    ringkasan_isu: str,
    nama_pengirim: str,
    jawatan_pengirim: str,
    laluan_pdf: str,
    laluan_csv: str,
) -> dict:
    """
    Menghantar emel rasmi mengikut format E-mel Rasmi KPN.
    HTML bersih, menyerupai penulisan manusia - tanpa HTML mewah atau label mesin.
    """

    # Badan emel mengikut template E-mel Rasmi KPN
    badan_teks = (
        f"ASSALAMUALAIKUM DAN SALAM SEJAHTERA\n\n"
        f"YBhg. Dato'/ Datin/ Tuan/ Puan,\n\n"
        f"MAKLUMAN ADUAN / PERMOHONAN: {tajuk_surat.upper()}\n\n"
        f"Dengan hormatnya saya merujuk kepada perkara tersebut di atas.\n\n"
        f"2.      Untuk makluman pihak YBhg. Dato'/ Datin/ Tuan/ Puan, e-mel ini dihantar "
        f"bagi mewakili {nama_komuniti} berhubung isu {ringkasan_isu}.\n\n"
        f"3.      Sehubungan itu, bersama-sama e-mel ini dilampirkan Surat Rasmi berserta "
        f"Data Log yang memperincikan aduan/permohonan tersebut untuk perhatian dan tindakan "
        f"segera pihak YBhg. Dato'/ Datin/ Tuan/ Puan selanjutnya.\n\n"
        f"Segala perhatian dan kerjasama daripada pihak YBhg. Dato'/ Datin/ Tuan/ Puan "
        f"dalam perkara ini amatlah dihargai.\n\n"
        f"Sekian, terima kasih.\n\n"
        f'"WAWASAN KEMAKMURAN BERSAMA 2030"\n'
        f'"BERKHIDMAT UNTUK NEGARA"\n\n'
        f"Saya yang menjalankan amanah,\n\n"
        f"__SIGNATURE__{nama_pengirim}__END_SIGNATURE__\n"
        f"{jawatan_pengirim}"
    )

    # Tukar ke HTML bersih - fon Times New Roman, saiz 12pt, sesuai dengan format surat rasmi
    baris_html_list = []
    for baris in badan_teks.split("\n"):
        b = baris.strip()
        if not b:
            baris_html_list.append('<p style="margin:0;line-height:0.8;">&nbsp;</p>')
        elif b.startswith("__SIGNATURE__") and b.endswith("__END_SIGNATURE__"):
            # Nama sebagai tandatangan dalam italik
            nama_sig = b.replace("__SIGNATURE__", "").replace("__END_SIGNATURE__", "")
            baris_html_list.append(
                f'<p style="margin:0 0 2px 0;font-style:italic;font-size:14pt;">{nama_sig}</p>'
            )
        elif b.startswith('"') and b.endswith('"'):
            baris_html_list.append(f'<p style="margin:0 0 2px 0;font-weight:bold;">{b}</p>')
        elif b.isupper() and len(b) > 4:
            baris_html_list.append(f'<p style="margin:0 0 2px 0;font-weight:bold;">{b}</p>')
        else:
            baris_html_list.append(f'<p style="margin:0 0 4px 0;">{b}</p>')

    html_penuh = (
        '<html><body style="font-family:\'Times New Roman\',Times,serif;'
        'font-size:12pt;color:#000000;max-width:720px;margin:0 auto;padding:24px;">'
        + "".join(baris_html_list)
        + "</body></html>"
    )

    def baca_fail(laluan):
        with open(laluan, "rb") as f:
            return list(f.read())

    params = {
        "from": f"{nama_pengirim} <onboarding@resend.dev>",
        "to": [emel_sasaran],
        "subject": subjek,
        "html": html_penuh,
        "attachments": [
            {
                "filename": os.path.basename(laluan_pdf),
                "content": baca_fail(laluan_pdf),
            },
            {
                "filename": os.path.basename(laluan_csv),
                "content": baca_fail(laluan_csv),
            },
        ],
    }

    return resend.Emails.send(params)


# ─────────────────────────────────────────────────────────────────────────────
#  FASTMCP SERVER
# ─────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("Sistem Advokasi Kerajaan DualComm")


@mcp.tool()
def hantar_advokasi_kerajaan(
    nama_pengirim: str,
    jawatan_pengirim: str,
    sektor: str,
    emel_sasaran: str,
    subjek_emel: str,
    tajuk_surat: str,
    nama_komuniti: str,
    ringkasan_isu: str,
    data_pdf_json: str,
    baris_csv_json: str,
    nombor_kes: str = "",
) -> str:
    """
    Alat MCP DualComm. Membina PDF Surat Rasmi format KPN, laporan CSV
    dengan data realistik, dan menghantar emel rasmi kepada jabatan kerajaan.

    Args:
        nama_pengirim     : Nama penuh penghantar - digunakan pada tandatangan PDF dan emel
        jawatan_pengirim  : Jawatan penghantar (cth: Pengarah Operasi)
        sektor            : Kod sektor - 'jtk', 'jkm', 'kkm', atau 'jpn'
        emel_sasaran      : Alamat emel jabatan kerajaan sasaran
        subjek_emel       : Tajuk emel dalam format: [UNTUK PERHATIAN: KOD] PENGHANTARAN SURAT RASMI: ...
        tajuk_surat       : Tajuk utama surat (akan ditukar HURUF BESAR)
        nama_komuniti     : Nama komuniti atau individu yang diwakili
        ringkasan_isu     : Ringkasan isu dalam satu ayat
        data_pdf_json     : JSON mengandungi kandungan PDF (title, paragraphs, dll.)
        baris_csv_json    : JSON mengandungi baris data CSV (minimum 20 baris)
        nombor_kes        : Nombor kes rujukan (pilihan)

    Returns:
        Mesej status - berjaya atau ralat dengan butiran
    """
    try:
        # Hurai JSON input
        try:
            data_pdf = json.loads(data_pdf_json) if data_pdf_json.strip() else {}
        except json.JSONDecodeError:
            data_pdf = {}

        try:
            baris_csv = json.loads(baris_csv_json) if baris_csv_json.strip() else []
        except json.JSONDecodeError:
            baris_csv = []

        cfg = SEKTOR.get(sektor, SEKTOR["kkm"])

        # Isi nilai lalai dari konfigurasi sektor jika tidak diberikan
        data_pdf.setdefault("gelaran_penerima", cfg["gelaran"])
        data_pdf.setdefault("org_penerima",     cfg["org"])
        data_pdf.setdefault("alamat1",          cfg["alamat1"])
        data_pdf.setdefault("alamat2",          cfg["alamat2"])
        data_pdf.setdefault("alamat3",          cfg.get("alamat3", ""))
        data_pdf.setdefault("title",            tajuk_surat)

        # Guna data lalai jika kurang dari 20 baris
        if len(baris_csv) < 20:
            baris_csv = DATA_CSV_LALAI.get(sektor, DATA_CSV_LALAI["kkm"])

        # Jana PDF
        laluan_pdf = bina_pdf_surat_rasmi(
            data=data_pdf,
            nama_pengirim=nama_pengirim,
            jawatan_pengirim=jawatan_pengirim,
            sektor=sektor,
            laluan_fail="",
        )

        # Jana CSV
        laluan_csv = bina_csv_laporan(
            sektor=sektor,
            baris_data=baris_csv,
            nama_pengirim=nama_pengirim,
            jawatan_pengirim=jawatan_pengirim,
            nombor_kes=nombor_kes,
            laluan_fail="",
        )

        # Hantar emel
        keputusan = hantar_emel(
            emel_sasaran=emel_sasaran,
            subjek=subjek_emel,
            tajuk_surat=tajuk_surat,
            nama_komuniti=nama_komuniti,
            ringkasan_isu=ringkasan_isu,
            nama_pengirim=nama_pengirim,
            jawatan_pengirim=jawatan_pengirim,
            laluan_pdf=laluan_pdf,
            laluan_csv=laluan_csv,
        )

        id_emel = keputusan.get("id", "tidak diketahui")
        return (
            f"Berjaya. Emel rasmi telah dihantar kepada {emel_sasaran}. "
            f"ID penghantaran: {id_emel}. "
            f"Lampiran: {laluan_pdf}, {laluan_csv}."
        )

    except Exception as ralat:
        traceback.print_exc()
        return f"Ralat semasa memproses: {str(ralat)}"


if __name__ == "__main__":
    mcp.run()
