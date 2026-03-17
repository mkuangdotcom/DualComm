import os
import json
import logging
import traceback
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import resend
from fpdf import FPDF
from groq import Groq

# ─────────────────────────────────────────────────────────────────────────────
#  ADVOKASI UTILITIES (Incorporated from mcp_server.py)
# ─────────────────────────────────────────────────────────────────────────────

BULAN_MELAYU = [
    "Januari", "Februari", "Mac", "April", "Mei", "Jun",
    "Julai", "Ogos", "September", "Oktober", "November", "Disember",
]

def format_tarikh(dt: datetime) -> str:
    return f"{dt.day} {BULAN_MELAYU[dt.month - 1]} {dt.year}"

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
        "headers_csv": ["Bil.", "Nama Individu", "Tarikh Lahir", "Umur", "Isu", "Kampung", "Daerah", "Negeri", "Dokumen", "Halangan"],
        "gambar": ["Assets/jpn/img_jpn_1.jpg", "Assets/jpn/img_jpn_2.jpg", "Assets/jpn/img_jpn_3.jpg"],
        "kapsyen_gambar": ["Budak pedalaman", "Logistik", "Unit MEKAR"],
    }
}

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
        ["8",  "Encik Mustafa bin Daud",     "490728-07-0123", "76", "Lelaki",    "Kg. Lubuk China, 78000 Alor Gajah, Melaka",            "Bantuan Orang Tua (BOT)", "0",   "OKU Fizikal",        "Tiada"],
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
        ["21", "Ibuprofen 400mg Tablet",            "Ibuprofen",                      "NSAID Anti-Radang",      "2,000 tablet",   "0 tablet",    "2,000 tablet",   "TINGGI",    "Anti-radang and pereda kesakitan",          "3 hari"],
        ["22", "Plaster Luka Pelbagai Saiz",        "Adhesive Bandage",               "Penjagaan Luka",         "2,000 pcs",      "100 pcs",     "1,900 pcs",      "RENDAH",    "Luka kecil dan calar harian",               "10 hari"],
    ],
    "jpn": [
        ["1",  "Bah Siti bte Bah Ali",        "15-03-2021", "5",  "Siti Maimunah", "Bah Ali", "Kg. Woh, Tapah", "Tapah", "Perak", "Tiada", "Logistik"],
    ]
}

class TemplateSuratRasmi(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def header(self):
        # Baris 1 - Nama penghantar (Bold) — diisi dari pemboleh ubah global (mcp_server.py style)
        nama_header = globals().get("_NAMA_HEADER_PDF", "Pejabat Advokasi")
        jawatan_header = globals().get("_JAWATAN_HEADER_PDF", "Sistem Advokasi Masyarakat Malaysia")
        self.set_font("Helvetica", "B", 12)
        self.set_xy(20, 12)
        self.cell(120, 5, nama_header, ln=False)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, "Tel       :  +60 3-0000 0000", align="R")
        self.ln(5)

        # Baris 2
        self.set_font("Helvetica", "", 9)
        self.set_x(20)
        self.cell(120, 4, jawatan_header, ln=False)
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

# ─────────────────────────────────────────────────────────────────────────────
#  ADVOCACY SERVICE (Integrated)
# ─────────────────────────────────────────────────────────────────────────────

class AdvocacyService:
    def __init__(self, groq_api_key: str):
        self.groq_client = Groq(api_key=groq_api_key)
        self.resend_api_key = os.environ.get("RESEND_API_KEY", "")
        self.sender_name = os.environ.get("SENDER_NAME", "Pegawai Advokasi DualComm")
        self.sender_role = os.environ.get("SENDER_ROLE", "Pengarah Operasi")
        
        # Paths
        self.project_root = Path(__file__).resolve().parent.parent.parent.parent
        self.media_root = self.project_root / "media_staging" / "advocacy"
        self.media_root.mkdir(parents=True, exist_ok=True)
        self.assets_root = self.project_root / "Assets"

    def kesan_sektor(self, teks: str) -> str:
        """Strictly detects sectors based on the user's provided logic."""
        t = teks.lower()
        if any(k in t for k in ["labour", "worker", "wage", "salary", "passport",
                                "jtk", "pekerja", "gaji", "buruh", "tenaga kerja", "unpaid"]):
            return "jtk"
        if any(k in t for k in ["welfare", "elderly", "oku", "disabled", "jkm", "warga emas",
                                "kebajikan", "bantuan orang tua", "bot", "old age", "senior"]):
            return "jkm"
        if any(k in t for k in ["health", "medical", "clinic", "medicine", "hospital", "kkm",
                                "ubatan", "klinik", "kesihatan", "bandage", "paracetamol",
                                "vaccine", "antivenom", "rural clinic", "supplies"]):
            return "kkm"
        if any(k in t for k in ["identity", " ic ", "birth cert", "jpn", "pendaftaran",
                                "stateless", "mekar", "kelahiran", "undocumented"]):
            return "jpn"
        if t.strip() == "1": return "jtk"
        if t.strip() == "2": return "jkm"
        if t.strip() == "3": return "kkm"
        if t.strip() == "4": return "jpn"
        return "kkm"

    def get_menu(self) -> str:
        return (
            "🇲🇾 *Sistem Advokasi Kerajaan DualComm*\n\n"
            "Sila pilih sektor aduan untuk memulakan advokasi rasmi:\n\n"
            "1️⃣ *Sektor Buruh & Pekerjaan (JTK)*\n"
            "2️⃣ *Sektor Kebajikan Sosial (JKM)*\n"
            "3️⃣ *Sektor Kesihatan Awam (KKM)*\n"
            "4️⃣ *Sektor Pendaftaran Negara (JPN)*\n\n"
            "*PENTING*: Sila taip nombor sektor (1-4)."
        )

    async def generate_draft(self, sector: str, user_text: str) -> Dict[str, Any]:
        """Generates the documents and email draft but DOES NOT send the email."""
        cfg = SEKTOR[sector]
        prompt = self._build_arahan_sistem(sector)
        
        try:
            respons = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user",   "content": user_text},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=3500,
            )
            
            keputusan = json.loads(respons.choices[0].message.content)
            logging.info(f"[Advocacy] AI Generated Decision for {sector}")

            # ── Content Extraction ────────────────────────────
            data_pdf = keputusan.get("data_pdf", {})
            tajuk_surat = keputusan.get("tajuk_surat") or f"ADUAN RASMI {cfg['kod']}"
            if not data_pdf.get("title"):
                data_pdf["title"] = tajuk_surat

            # Use detected name/role if provided by AI
            detected_name = keputusan.get("nama_pengirim_dikesan") or self.sender_name
            detected_role = keputusan.get("jawatan_pengirim_dikesan") or self.sender_role

            # 1. Bina PDF
            pdf_filename = f"Surat_Rasmi_{sector.upper()}_{datetime.now().strftime('%H%M%S')}.pdf"
            pdf_path = self.media_root / pdf_filename
            self._bina_pdf(data_pdf, sector, str(pdf_path), detected_name, detected_role)

            # 2. Bina CSV
            csv_filename = f"Laporan_Data_{cfg['kod']}_{datetime.now().strftime('%H%M%S')}.csv"
            csv_path = self.media_root / csv_filename
            self._bina_csv(sector, keputusan.get("nombor_kes", ""), str(csv_path), detected_name, detected_role)

            # 3. Return Draft Status
            draft_msg = (
                f"📝 *DRAF ADVOKASI SEDIA*\n\n"
                f"*Tajuk:* {data_pdf['title']}\n"
                f"*Penerima:* {cfg['org']}\n"
                f"*Pengirim:* {detected_name} ({detected_role})\n\n"
                f"Sila semak dokumen yang dilampirkan. Adakah anda bersetuju untuk menghantarnya ke {cfg['emel']}?\n\n"
                f"1️⃣ *Ya, hantar sekarang*\n"
                f"2️⃣ *Tidak, batalkan*\n\n"
                f"_Sila taip 1 atau 2._"
            )

            return {
                "status": "draft_ready",
                "text": draft_msg,
                "attachments": [str(pdf_path), str(csv_path)],
                "keputusan": keputusan,
                "sector": sector,
                "pdf_path": str(pdf_path),
                "csv_path": str(csv_path),
                "detected_name": detected_name,
                "detected_role": detected_role
            }

        except Exception:
            logging.error(f"[Advocacy] Error: {traceback.format_exc()}")
            return {
                "status": "error",
                "text": "Maaf, ralat berlaku semasa memproses dokumen advokasi anda. Sila cuba lagi sebentar.",
                "attachments": []
            }

    def execute_send(self, draft_data: Dict[str, Any]):
        """Executes the actual email sending."""
        self._hantar_emel(
            draft_data["keputusan"], 
            draft_data["sector"], 
            draft_data["pdf_path"], 
            draft_data["csv_path"],
            draft_data.get("detected_name", self.sender_name),
            draft_data.get("detected_role", self.sender_role)
        )

    def _build_arahan_sistem(self, sektor: str) -> str:
        cfg = SEKTOR[sektor]
        arahan_tambahan = {
            "jtk": "Aduan BURUH (Akta Kerja 1955). Siasatan segera penahanan gaji/pasport. Min 6 perenggan.",
            "jkm": "Kebajikan OKU/Warga Emas. Minta lawatan rumah (BOT). Min 6 perenggan.",
            "kkm": "Kecemasan Kesihatan / Bekalan. Klinik Desa / Medevac. Min 6 perenggan.",
            "jpn": "Pendaftaran Kelahiran / MEKAR. Masalah dokumen pedalaman. Min 6 perenggan.",
        }.get(sektor, "Surat rasmi kerajaan.")

        return f"""
Anda adalah sistem advokasi kerajaan Malaysia. 
{arahan_tambahan}

Ekstrak Nama & Jawatan pengirim daripada input. Letakkan dlm "nama_pengirim_dikesan" & "jawatan_pengirim_dikesan".

JSON output TEPAT:
{{
  "nama_pengirim_dikesan": "...",
  "jawatan_pengirim_dikesan": "...",
  "subjek_emel": "[UNTUK PERHATIAN: {cfg['kod']}] PENGHANTARAN SURAT RASMI: [TAJUK]",
  "tajuk_surat": "[TAJUK HURUF BESAR SPESIFIK]",
  "nama_komuniti": "...",
  "ringkasan_isu": "...",
  "data_pdf": {{
    "title": "[TAJUK]",
    "paragraphs": [
      "Dengan hormatnya saya merujuk kepada perkara di atas.",
      "[Perenggan 2: Huraikan masalah SECARA TERPERINCI - min 4 ayat]",
      "[Perenggan 3: Impak kepada komuniti - min 4 ayat]",
      "[Perenggan 4: Rujukan akta/undang-undang - min 4 ayat]",
      "[Perenggan 5: Butiran khusus / Statistik - min 4 ayat]",
      "[Perenggan 6: Permintaan tindakan rasmi - min 4 ayat]",
      "[Perenggan 7: Penutup & Tindakan susulan - min 4 ayat]"
    ],
    "additional_sections": [
      {{ "heading": "FAKTA KES", "lines": ["Fakta 1", "Fakta 2"] }},
      {{ "heading": "RUJUKAN UNDANG-UNDANG", "lines": ["Akta berkaitan"] }}
    ],
    "closing": "Segala perhatian pihak Tuan amat dihargai."
  }},
  "nombor_kes": "DUALCOMM-{cfg['kod']}-2026-001",
  "balasan_pengguna": "Draf telah dijana."
}}
"""

    def _bina_pdf(self, data: Dict[str, Any], sektor: str, path: str, nama_pengirim: str, jawatan_pengirim: str):
        cfg = SEKTOR[sektor]
        globals()["_NAMA_HEADER_PDF"] = nama_pengirim
        globals()["_JAWATAN_HEADER_PDF"] = jawatan_pengirim
        
        pdf = TemplateSuratRasmi(orientation="P", unit="mm", format="A4")
        pdf.set_margins(left=20, top=40, right=20)
        pdf.set_auto_page_break(auto=True, margin=22)
        pdf.add_page()
        
        tarikh_str = format_tarikh(datetime.now())
        no_rujukan = data.get("nombor_rujukan", f"ADV.2026/{cfg['kod']}/001")

        pdf.set_font("Helvetica", "", 11)
        pdf.set_x(108)
        pdf.cell(35, 6, "Ruj. Kami  :", align="R"); pdf.cell(0, 6, f"  {no_rujukan}"); pdf.ln(6)
        pdf.set_x(108)
        pdf.cell(35, 6, "Tarikh        :", align="R"); pdf.cell(0, 6, f"  {tarikh_str}"); pdf.ln(10)

        pdf.set_font("Helvetica", "", 11)
        # Fix: using direct access for clarity
        items_penerima = [
            data.get("gelaran_penerima") or cfg.get("gelaran"),
            cfg.get("org"),
            cfg.get("alamat1"),
            cfg.get("alamat2"),
            cfg.get("alamat3")
        ]
        for line in items_penerima:
            if line:
                pdf.set_x(20)
                pdf.cell(0, 6, str(line))
                pdf.ln(6)
        pdf.ln(6)

        pdf.set_font("Helvetica", "", 11); pdf.set_x(20); pdf.cell(0, 6, "YBhg. Dato'/ Tuan/ Puan,"); pdf.ln(10)

        pdf.set_font("Helvetica", "B", 11)
        tajuk = data.get("title") or data.get("tajuk_surat") or "ADUAN"
        pdf.set_x(20); pdf.multi_cell(170, 7, str(tajuk).upper(), align="C"); pdf.ln(3)
        pdf.set_line_width(0.3); pdf.line(20, pdf.get_y(), 190, pdf.get_y()); pdf.ln(8)

        perenggan = data.get("paragraphs")
        if not isinstance(perenggan, list):
            perenggan = []
            
        had_bawah = pdf.h - pdf.b_margin
        for idx, para in enumerate(perenggan):
            pdf.set_font("Helvetica", "", 11)
            if idx == 0:
                pdf.set_x(20)
                pdf.multi_cell(170, 6, str(para), align="J")
            else:
                if pdf.get_y() > (had_bawah - 20): pdf.add_page()
                y = pdf.get_y()
                pdf.set_x(20)
                pdf.cell(12, 6, f"{idx+1}.")
                pdf.set_xy(32, y)
                pdf.multi_cell(158, 6, str(para), align="J")
            pdf.ln(4)

        sections = data.get("additional_sections")
        if isinstance(sections, list):
            for sek in sections:
                if pdf.get_y() > (had_bawah - 30): pdf.add_page()
                h = sek.get("heading","")
                pdf.set_font("Helvetica", "B", 11); pdf.set_x(20); pdf.cell(0, 7, str(h).upper()); pdf.ln(6)
                lines = sek.get("lines", [])
                if isinstance(lines, list):
                    for sl in lines:
                        pdf.set_font("Helvetica", "", 11); pdf.set_x(20); pdf.multi_cell(170, 6, str(sl), align="J"); pdf.ln(2)

        raw_gambar = cfg.get("gambar")
        kapsyen_list = cfg.get("kapsyen_gambar")
        if isinstance(raw_gambar, list):
            pdf.add_page(); pdf.set_font("Helvetica", "B", 11); pdf.set_x(20); pdf.cell(0, 7, "LAMPIRAN GAMBAR"); pdf.ln(15)
            # Use a basic for loop to avoid complex indexing in inferred types
            count = 0
            for img_rel in raw_gambar:
                if count >= 3: break
                img_path = self.assets_root / str(img_rel).replace("Assets/", "")
                if img_path.exists():
                    if pdf.get_y() > 160: pdf.add_page()
                    pdf.image(str(img_path), x=35, y=pdf.get_y(), w=140, h=98); pdf.ln(102)
                    pdf.set_font("Helvetica", "I", 9); pdf.set_x(20)
                    kapsyen = "Imej sokongan."
                    if isinstance(kapsyen_list, list) and count < len(kapsyen_list):
                        kapsyen = str(kapsyen_list[count])
                    pdf.multi_cell(170, 5, f"Rajah {count+1}: {kapsyen}", align="C"); pdf.ln(10)
                    count += 1

        pdf.ln(5); pdf.set_font("Helvetica", "", 11); pdf.set_x(20); pdf.multi_cell(170, 6, str(data.get("closing", "Terima kasih.")), align="J")
        pdf.ln(5); pdf.set_x(20); pdf.cell(0, 6, "Sekian,"); pdf.ln(10)
        pdf.set_font("Helvetica", "B", 11); pdf.set_x(20); pdf.cell(0, 7, '"BERKHIDMAT UNTUK NEGARA"'); pdf.ln(15)
        pdf.set_font("Helvetica", "I", 13); pdf.set_x(20); pdf.cell(0, 7, str(nama_pengirim)); pdf.ln(7)
        pdf.set_font("Helvetica", "", 11); pdf.set_x(20); pdf.cell(0, 6, str(jawatan_pengirim))
        pdf.output(path)

    def _bina_csv(self, sektor: str, nombor_kes: str, path: str, nama_pengirim: str, jawatan_pengirim: str):
        cfg = SEKTOR[sektor]; data = DATA_CSV_LALAI.get(sektor, [])
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(cfg["headers_csv"])
            for r in data: w.writerow(r)
            w.writerow([]); w.writerow(["Penyedia:", str(nama_pengirim)]); w.writerow(["Jawatan:", str(jawatan_pengirim)]); w.writerow(["Kes:", str(nombor_kes)])

    def _hantar_emel(self, data: Dict[str, Any], sektor: str, pdf_path: str, csv_path: str, nama_pengirim: str, jawatan_pengirim: str):
        if not self.resend_api_key: return
        try:
            resend.api_key = self.resend_api_key; cfg = SEKTOR[sektor]
            subj = data.get("subjek_emel") or f"[UNTUK PERHATIAN: {cfg['kod']}] PENGHANTARAN SURAT RASMI"
            t_surat = data.get("tajuk_surat") or f"ADUAN RASMI {cfg['kod']}"
            community = data.get("nama_komuniti") or "komuniti yang diwakili"
            summary = data.get("ringkasan_isu") or "isu yang dilaporkan"
            
            # Detailed email template following the user's provided structure
            badan_teks = (
                f"ASSALAMUALAIKUM DAN SALAM SEJAHTERA\n\n"
                f"YBhg. Dato'/ Datin/ Tuan/ Puan,\n\n"
                f"MAKLUMAN ADUAN / PERMOHONAN: {str(t_surat).upper()}\n\n"
                f"Dengan hormatnya saya merujuk kepada perkara tersebut di atas.\n\n"
                f"2.      Untuk makluman pihak YBhg. Dato'/ Datin/ Tuan/ Puan, e-mel ini dihantar "
                f"bagi mewakili {community} berhubung isu {summary}.\n\n"
                f"3.      Sehubungan itu, bersama-sama e-mel ini dilampirkan Surat Rasmi berserta "
                f"Data Log yang memperincikan aduan/permohonan tersebut untuk perhatian dan tindakan "
                f"segera pihak YBhg. Dato'/ Datin/ Tuan/ Puan selanjutnya.\n\n"
                f"Segala perhatian dan kerjasama daripada pihak YBhg. Dato'/ Datin/ Tuan/ Puan "
                f"dalam perkara ini amatlah dihargai.\n\n"
                f"Sekian, terima kasih.\n\n"
                f'"WAWASAN KEMAKMURAN BERSAMA 2030"\n'
                f'"BERKHIDMAT UNTUK NEGARA"\n\n'
                f"Saya yang menjalankan amanah,\n\n"
                f"{nama_pengirim}\n"
                f"{jawatan_pengirim}"
            )
            
            badan_html = badan_teks.replace('\n', '<br>')
            html = f"<html><body style='font-family:serif; font-size:12pt;'>{badan_html}</body></html>"
            def rb(p):
                with open(p, "rb") as f: return list(f.read())
            resend.Emails.send({"from": f"{nama_pengirim} <onboarding@resend.dev>", "to": ["kv.kevin.official@gmail.com"], "subject": str(subj), "html": html,
                "attachments": [{"filename": os.path.basename(pdf_path), "content": rb(pdf_path)}, {"filename": os.path.basename(csv_path), "content": rb(csv_path)}]
            })
        except: logging.error("Email Error")
