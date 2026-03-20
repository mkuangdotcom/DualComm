# main.py
# DualComm - Sistem Advokasi Kerajaan Malaysia
# FastAPI + Groq menghantar kepada fungsi MCP

import os
import json

from fastapi import FastAPI, Form
from groq import Groq

from mcp_server import (
    SEKTOR,
    DATA_CSV_LALAI,
    bina_pdf_surat_rasmi,
    bina_csv_laporan,
    hantar_emel,
)

# ─── Konfigurasi Pengirim (Gunakan .env atau Nilai Lalai) ──────────────
NAMA_PENGIRIM    = os.environ.get("SENDER_NAME", "Pegawai Advokasi DualComm")
JAWATAN_PENGIRIM = os.environ.get("SENDER_ROLE", "Pengarah Operasi")

print("\n" + "=" * 60)
print("  Sistem Advokasi Kerajaan DualComm")
print(f"  Pengirim : {NAMA_PENGIRIM}")
print(f"  Jawatan  : {JAWATAN_PENGIRIM}")
print("=" * 60 + "\n")

app = FastAPI()
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def kesan_sektor(teks: str) -> str:
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
    return "kkm"


ARAHAN_SEKTOR = {
    "jtk": (
        "Anda memproses aduan BURUH DAN PEKERJAAN. "
        "Sertakan rujukan kepada Akta Kerja 1955 (Pindaan 2022) Seksyen 25 berkenaan "
        "penahanan gaji haram dan penahanan pasport secara haram. Minta siasatan segera. "
        "Tulis perenggan PDF terperinci - minimum 6 perenggan dengan fakta spesifik."
    ),
    "jkm": (
        "Anda memproses permohonan KEBAJIKAN SOSIAL untuk warga emas atau OKU. "
        "Minta lawatan rumah rasmi (Siasatan ke Rumah). "
        "Rujuk program Bantuan Orang Tua (BOT) dan Bantuan OKU. "
        "Tulis perenggan PDF terperinci - minimum 6 perenggan dengan latar belakang pemohon."
    ),
    "kkm": (
        "Anda memproses laporan KECEMASAN KESIHATAN AWAM. "
        "Huraikan kekurangan bekalan perubatan dan pengasingan geografi. "
        "Rujuk program Klinik Desa. Minta penggunaan logistik kecemasan atau Medevac. "
        "Tulis perenggan PDF terperinci - minimum 6 perenggan."
    ),
    "jpn": (
        "Anda memproses kes PENDAFTARAN NEGARA untuk individu tanpa dokumen. "
        "Jelaskan halangan keluarga ke cawangan JPN. "
        "Minta unit bergerak Program MEKAR. "
        "Tulis perenggan PDF terperinci - minimum 6 perenggan."
    ),
}


def bina_arahan_sistem(sektor: str) -> str:
    cfg    = SEKTOR[sektor]
    arahan = ARAHAN_SEKTOR[sektor]
    return f"""
Anda adalah sistem advokasi undang-undang Malaysia yang menulis surat rasmi kerajaan.
{arahan}

Balas HANYA dalam JSON yang sah dengan kunci-kunci TEPAT ini:

{{
  "subjek_emel": "[UNTUK PERHATIAN: {cfg['kod']}] PENGHANTARAN SURAT RASMI: [TAJUK HURUF BESAR SPESIFIK]",
  "tajuk_surat": "[TAJUK SURAT RASMI HURUF BESAR - SANGAT SPESIFIK KEPADA SITUASI INI]",
  "nama_komuniti": "[Nama komuniti atau individu yang diwakili]",
  "ringkasan_isu": "[Ringkasan isu dalam SATU ayat yang jelas dan spesifik]",
  "data_pdf": {{
    "title": "[TAJUK SAMA SEPERTI tajuk_surat]",
    "paragraphs": [
      "Dengan hormatnya saya merujuk kepada perkara di atas.",
      "[Perenggan 2: Nyatakan siapa yang diwakili dan huraikan masalah SECARA TERPERINCI - minimum 4 ayat panjang]",
      "[Perenggan 3: Latar belakang lengkap masalah, impak kepada mangsa dan komuniti - minimum 4 ayat]",
      "[Perenggan 4: Rujukan kepada akta, undang-undang, atau program kerajaan yang relevan - spesifik dengan nombor seksyen]",
      "[Perenggan 5: Butiran khusus - nombor mangsa, jumlah kerugian, tarikh kejadian, nama tempat, koordinat jika ada]",
      "[Perenggan 6: Permintaan tindakan rasmi yang spesifik - apa yang diperlukan, dalam tempoh masa berapa]",
      "[Perenggan 7: Tindakan susulan yang dijangka dan komitmen pihak DualComm untuk bekerjasama]"
    ],
    "additional_sections": [
      {{
        "heading": "BUTIRAN KES DAN FAKTA SOKONGAN",
        "lines": [
          "[Fakta 1: butiran spesifik tentang kes ini dengan nombor atau statistik]",
          "[Fakta 2: maklumat geografi atau konteks kawasan]",
          "[Fakta 3: maklumat tambahan yang menyokong keperluan tindakan segera]"
        ]
      }},
      {{
        "heading": "RUJUKAN UNDANG-UNDANG DAN DASAR KERAJAAN",
        "lines": [
          "[Rujukan akta atau dasar yang berkaitan - nama akta dan nombor seksyen]",
          "[Implikasi undang-undang dan tanggungjawab jabatan kerajaan berkenaan]",
          "[Preseden atau kes terdahulu yang menyokong permohonan ini jika berkaitan]"
        ]
      }}
    ],
    "closing": "Segala perhatian dan kerjasama pihak YBhg. Dato'/ Datin/ Tuan/ Puan dalam perkara ini amat dihargai dan didahului dengan ucapan terima kasih."
  }},
  "nombor_kes": "DUALCOMM-{cfg['kod']}-YYYYMMDD-001",
  "balasan_pengguna": "[Balasan mudah, mesra, dan menenangkan kepada pengguna dalam bahasa yang mereka gunakan. Sahkan tindakan yang diambil.]"
}}

PERATURAN KRITIKAL:
- SEMUA kandungan PDF dan emel MESTI dalam Bahasa Melayu yang formal dan sopan.
- Setiap perenggan dalam paragraphs[] mestilah PANJANG - minimum 3 hingga 5 ayat.
- JANGAN masukkan sebarang teks di luar objek JSON.
- Tajuk surat mesti sangat spesifik kepada situasi yang dilaporkan.
"""


@app.post("/webhook")
async def ejen_dualcomm(Body: str = Form(...)):
    sektor = kesan_sektor(Body)
    cfg    = SEKTOR[sektor]
    print(f"\n[DualComm] Sektor dikesan: {sektor.upper()}")

    try:
        respons = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": bina_arahan_sistem(sektor)},
                {"role": "user",   "content": Body},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=4000,
        )

        keputusan = json.loads(respons.choices[0].message.content)
        print("\n=== KEPUTUSAN AI DUALCOMM ===")
        print(json.dumps(keputusan, indent=2, ensure_ascii=False))
        print("=============================\n")

        data_pdf   = keputusan.get("data_pdf", {})
        nombor_kes = keputusan.get("nombor_kes", "")

        if not data_pdf.get("title"):
            data_pdf["title"] = keputusan.get("tajuk_surat", "")

        laluan_pdf = bina_pdf_surat_rasmi(
            data=data_pdf,
            nama_pengirim=NAMA_PENGIRIM,
            jawatan_pengirim=JAWATAN_PENGIRIM,
            sektor=sektor,
            laluan_fail="",           # Jana nama formal secara automatik
        )

        laluan_csv = bina_csv_laporan(
            sektor=sektor,
            baris_data=[],
            nama_pengirim=NAMA_PENGIRIM,
            jawatan_pengirim=JAWATAN_PENGIRIM,
            nombor_kes=nombor_kes,
            laluan_fail="",           # Jana nama formal secara automatik
        )

        keputusan_emel = hantar_emel(
            emel_sasaran=cfg["emel"],
            subjek=keputusan.get(
                "subjek_emel",
                f"[UNTUK PERHATIAN: {cfg['kod']}] {keputusan.get('tajuk_surat', '')}"
            ),
            tajuk_surat=keputusan.get("tajuk_surat", ""),
            nama_komuniti=keputusan.get("nama_komuniti", "Komuniti yang diwakili"),
            ringkasan_isu=keputusan.get("ringkasan_isu", ""),
            nama_pengirim=NAMA_PENGIRIM,
            jawatan_pengirim=JAWATAN_PENGIRIM,
            laluan_pdf=laluan_pdf,
            laluan_csv=laluan_csv,
        )

        return {
            "status":           "berjaya",
            "sektor":           sektor.upper(),
            "emel_sasaran":     cfg["emel"],
            "id_resend":        keputusan_emel.get("id", "tidak diketahui"),
            "balasan_pengguna": keputusan.get("balasan_pengguna", ""),
            "lampiran":         [laluan_pdf, laluan_csv],
        }

    except Exception as ralat:
        import traceback
        traceback.print_exc()
        return {"status": "ralat", "mesej": str(ralat)}