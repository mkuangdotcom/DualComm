# test_webhook.py
# DualComm - Skrip Ujian Interaktif

import requests
import json

URL = "http://localhost:8080/webhook"

KES_UJI = {
    "1": {
        "label": "Sektor 1 - Buruh dan Pekerjaan (JTK)",
        "teks": (
            "I am a Bangladeshi worker in Shah Alam, Selangor. My employer at a textile factory "
            "has not paid my wages for 4 months, totalling RM 12,800 for me and 21 colleagues. "
            "He has also confiscated all our passports and threatened us not to report. "
            "We are living at the factory dormitory under surveillance and cannot leave freely. "
            "Please help us file a formal complaint to the Labour Department immediately."
        ),
    },
    "2": {
        "label": "Sektor 2 - Kebajikan Sosial / Warga Emas (JKM)",
        "teks": (
            "Saya seorang warga emas berumur 78 tahun tinggal seorang diri di Kuala Lipis, Pahang. "
            "Suami saya meninggal dunia 6 bulan lalu dan saya tidak mempunyai sebarang pendapatan. "
            "Anak-anak saya bekerja jauh di Kuala Lumpur dan tidak dapat menjaga saya. "
            "Saya tidak tahu cara menggunakan komputer atau telefon pintar untuk memohon bantuan kerajaan. "
            "Kaki saya sakit dan saya tidak boleh berjalan jauh atau menaiki bas untuk ke pejabat JKM. "
            "Tolong bantu saya mohon Bantuan Orang Tua."
        ),
    },
    "3": {
        "label": "Sektor 3 - Kesihatan Awam / Klinik Desa (KKM)",
        "teks": (
            "We are a rural clinic serving three Orang Asli villages near Tongod, Sabah. "
            "We have completely run out of: paracetamol, basic bandages, oral rehydration salts, "
            "anti-malarial medication, and hepatitis B vaccines for newborns. "
            "We currently have 62 patients including 14 children with high fever and signs of malaria. "
            "Two infants need hepatitis B vaccination urgently. The road has been flooded for 8 days "
            "and we cannot reach the nearest district hospital. We need emergency medical supply "
            "deployment and possibly medical evacuation for two critical cases."
        ),
    },
    "4": {
        "label": "Sektor 4 - Pendaftaran Negara / Kanak-kanak Tanpa Dokumen (JPN)",
        "teks": (
            "I live in Kampung Pos Lebir, a remote Orang Asli settlement near Gua Musang, Kelantan. "
            "I have five children aged 3 to 11 who have never been registered with JPN. "
            "They have no birth certificates and no identity cards. Our village is accessible only "
            "by a dirt road that takes 5 hours. We are extremely poor and cannot afford transport "
            "to the JPN office in town. Without documents, my children cannot enroll in school "
            "and may face statelessness as adults. Please request the JPN mobile unit MEKAR "
            "to come to our village to register all our children."
        ),
    },
}


def jalankan_kes(nombor: str):
    kes = KES_UJI[nombor]
    print(f"\n{'=' * 65}")
    print(f"  {kes['label']}")
    print(f"{'=' * 65}")
    print(f"Input  : {kes['teks'][:120]}...")

    cuba = requests.post(URL, data={"Body": kes["teks"]}, timeout=120)
    hasil = cuba.json()

    print(f"\nStatus          : {hasil.get('status')}")
    print(f"Sektor          : {hasil.get('sektor', '')}")
    print(f"Emel Sasaran    : {hasil.get('emel_sasaran')}")
    print(f"ID Resend       : {hasil.get('id_resend')}")
    print(f"Lampiran        : {hasil.get('lampiran')}")
    print(f"\nBalasan kepada pengguna:\n  {hasil.get('balasan_pengguna')}")

    if hasil.get("status") == "ralat":
        print(f"\nRalat: {hasil.get('mesej')}")

    return hasil


def main():
    print("\n" + "=" * 65)
    print("  Sistem Advokasi Kerajaan DualComm - Konsol Ujian")
    print("=" * 65)
    print("\nPilih kes ujian:")
    for k, v in KES_UJI.items():
        print(f"  [{k}] {v['label']}")
    print("  [S] Jalankan SEMUA kes ujian")
    print("  [T] Masukkan aduan sendiri")
    print()

    pilihan = input("Pilihan anda: ").strip().upper()

    if pilihan == "S":
        for k in KES_UJI:
            jalankan_kes(k)

    elif pilihan == "T":
        aduan = input("Masukkan aduan anda:\n> ").strip()
        if aduan:
            cuba = requests.post(URL, data={"Body": aduan}, timeout=120)
            print("\n" + json.dumps(cuba.json(), indent=2, ensure_ascii=False))

    elif pilihan in KES_UJI:
        jalankan_kes(pilihan)

    else:
        print("Pilihan tidak sah.")


if __name__ == "__main__":
    main()