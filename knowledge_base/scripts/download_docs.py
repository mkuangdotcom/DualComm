"""
download_docs.py
Downloads all Malaysian government PDFs for the DualComm RAG knowledge base.
Covers: labor/migrant, social welfare, healthcare, travel, housing, grants, emergency.
Validates each file and auto-substitutes from reserves on failure.
Generates documents.json metadata and prints a summary report.

Run from repo root:
  cd dualcomm
  pip install pymupdf requests
  python knowledge_base/scripts/download_docs.py
"""

import json
import sys
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
KB_ROOT = SCRIPT_DIR.parent
RAW_DIR = KB_ROOT / "raw_pdfs"
META_FILE = KB_ROOT / "metadata" / "documents.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) VHack2026-RAG-Collector/1.0"}
ACCESS_DATE = date.today().isoformat()
MIN_SIZE_KB = 10

# ── Primary Documents ────────────────────────────────────────────────────────

PRIMARY_DOCS = [

    # ── Labor / Migrant ──────────────────────────────────────────────────────
    {
        "id": "iom_migrant_rights",
        "filename": "iom_migrant_workers_rights_duties.pdf",
        "category": "labor_migrant",
        "language": "en",
        "source_org": "IOM",
        "title": "Migrant Workers Rights and Duties in Malaysia",
        "url": "https://www.iom.int/sites/g/files/tmzbdl2616/files/revised-28-july-2025_english-migrant-workers-rights-and-duties-in-malaysia.pdf",
        "published_date": "2025-07",
        "license_or_terms": "Public domain / IOM official publication",
        "priority_sections_only": False,
    },
    {
        "id": "iom_employer_obligations",
        "filename": "iom_employer_legal_obligations.pdf",
        "category": "labor_migrant",
        "language": "en",
        "source_org": "IOM",
        "title": "Guidance for Employers of Migrant Workers - Legal Obligations in Malaysia",
        "url": "https://www.iom.int/sites/g/files/tmzbdl2616/files/revised-28-july-2025_english-guidance-for-employers-of-migrant-workers-legal-obligations-in-malaysia.pdf",
        "published_date": "2025-07",
        "license_or_terms": "Public domain / IOM official publication",
        "priority_sections_only": False,
    },
    {
        "id": "bar_migrant_guide",
        "filename": "malaysian_bar_migrant_workers_rights.pdf",
        "category": "labor_migrant",
        "language": "en",
        "source_org": "Malaysian Bar Council",
        "title": "A Quick Guide to Rights of Migrant Workers",
        "url": "https://www.malaysianbar.org.my/cms/upload_files/document/A%20Quick%20Guide%20to%20Rights%20of%20Migrant%20Workers.pdf",
        "published_date": "2019",
        "license_or_terms": "Public domain / Malaysian Bar Council publication",
        "priority_sections_only": False,
    },
    {
        "id": "jtksm_foreign_worker_rights_5lang",
        "filename": "jtksm_rights_foreign_employees_5languages.pdf",
        "category": "labor_migrant",
        "language": "multilingual",
        "source_org": "JTKSM",
        "title": "Rights of Foreign Employees in Malaysia (5-Language Brochure)",
        "url": "https://jtksm.mohr.gov.my/sites/default/files/2024-10/JTKSM%20Brochure%205%20Bahasa%20Final.pdf",
        "published_date": "2024-10",
        "license_or_terms": "Public domain / JTKSM official publication",
        "priority_sections_only": False,
    },
    {
        "id": "employment_act_1955_en",
        "filename": "employment_act_1955_english.pdf",
        "category": "labor_migrant",
        "language": "en",
        "source_org": "JTKSM / MOHR",
        "title": "Employment Act 1955 (English)",
        "url": "https://jtksm.mohr.gov.my/sites/default/files/2022-11/akta_kerja1955_bi.pdf",
        "published_date": "2022",
        "license_or_terms": "Public domain / Malaysian legislation",
        "priority_sections_only": False,
    },

    # ── Social Welfare ───────────────────────────────────────────────────────
    {
        "id": "perkeso_2025_booklet",
        "filename": "perkeso_2025_booklet_bilingual.pdf",
        "category": "social_welfare",
        "language": "en_bm",
        "source_org": "PERKESO",
        "title": "PERKESO 2025 Booklet (Bilingual)",
        "url": "https://www.perkeso.gov.my/images/dokumen/risalah/2025-BOOKLET_PERKESO_BI.pdf",
        "published_date": "2025",
        "license_or_terms": "Public domain / PERKESO official publication",
        "priority_sections_only": False,
    },
    {
        "id": "jkm_oku_faq",
        "filename": "jkm_oku_assistance_faq.pdf",
        "category": "social_welfare",
        "language": "bm",
        "source_org": "JKM",
        "title": "FAQ Bantuan OKU (Disabled Assistance FAQ)",
        "url": "https://www.jkm.gov.my/jkm/uploads/files/Bahagian%20Pengurusan/FAQ%20BANTUAN%20OKU%20(1962020).pdf",
        "published_date": "2020",
        "license_or_terms": "Public domain / JKM official publication",
        "priority_sections_only": False,
    },
    {
        "id": "jkm_federal_assistance",
        "filename": "jkm_financial_assistance_procedures.pdf",
        "category": "social_welfare",
        "language": "bm",
        "source_org": "JKM",
        "title": "Garis Panduan Pengurusan Bantuan Kewangan Persekutuan JKM",
        "url": "https://ebantuanjkm.jkm.gov.my/spbkDoc/Pautan/Pautan_Pd_29.06.2018%20GARIS%20PANDUAN%20PENGURUSAN%20BANTUAN%20KEWANGAN%20PERSEKUTUAN%20JKM.pdf",
        "published_date": "2018-06",
        "license_or_terms": "Public domain / JKM official publication",
        "priority_sections_only": False,
    },
    {
        "id": "kwsp_leaving_country",
        "filename": "kwsp_leaving_country_withdrawal.pdf",
        "category": "social_welfare",
        "language": "en_bm",
        "source_org": "KWSP",
        "title": "KWSP Leaving Country Withdrawal Guide",
        "url": "https://www.kwsp.gov.my/documents/d/guest/more_information_leaving_country_withdrawal_v11032019",
        "published_date": "2019-03",
        "license_or_terms": "Public domain / KWSP official publication",
        "priority_sections_only": False,
    },

    # ── Healthcare ───────────────────────────────────────────────────────────
    {
        "id": "fomema_foreign_worker_guide",
        "filename": "fomema_foreign_worker_medical_guide.pdf",
        "category": "healthcare",
        "language": "en",
        "source_org": "FOMEMA / IMI",
        "title": "FOMEMA Foreign Worker Medical Examination User Guide",
        "url": "https://maid-online.imi.gov.my/maid/doc/Manual_Fomema.pdf",
        "published_date": "2023",
        "license_or_terms": "Public domain / FOMEMA official publication",
        "priority_sections_only": False,
    },
    {
        "id": "oku_pwd_benefits",
        "filename": "oku_pwd_benefits_privileges.pdf",
        "category": "healthcare",
        "language": "en",
        "source_org": "MARF / MOH / JKM",
        "title": "Benefits and Privileges for Registered Persons with Disabilities (OKU)",
        "url": "https://marf.org.my/wp-content/uploads/2024/09/Benefits-Privileges-for-the-Registered-PWD-OKU.pdf",
        "published_date": "2024-09",
        "license_or_terms": "Public domain / MARF official publication",
        "priority_sections_only": False,
    },
    {
        "id": "mysejahtera_faq",
        "filename": "mysejahtera_faq_english.pdf",
        "category": "healthcare",
        "language": "en",
        "source_org": "MKN / MOH",
        "title": "MySejahtera FAQ (English)",
        "url": "https://www.mkn.gov.my/web/wp-content/uploads/sites/3/2020/04/ENGLISH_FAQ_MYSEJAHTERA.pdf",
        "published_date": "2020-04",
        "license_or_terms": "Public domain / MKN official publication",
        "priority_sections_only": False,
    },

    # ── Grants / Micro-Enterprise ────────────────────────────────────────────
    {
        "id": "tekun_financing_form",
        "filename": "tekun_financing_application_form.pdf",
        "category": "grants",
        "language": "bm",
        "source_org": "TEKUN Nasional",
        "title": "TEKUN Nasional Financing Application Form",
        "url": "https://www.tekun.gov.my/wp-content/uploads/2023/05/BPC-BORANG-01PINDAAN-02-BORANG-PERMOHONAN-PEMBIAYAAN-TEKUN-PINDAAN-01052023.pdf",
        "published_date": "2023-05",
        "license_or_terms": "Public domain / TEKUN Nasional official publication",
        "priority_sections_only": False,
    },
    {
        "id": "sme_corp_financing",
        "filename": "sme_corp_financing_overview.pdf",
        "category": "grants",
        "language": "en",
        "source_org": "SME Corporation Malaysia",
        "title": "SME Corp Malaysia - SME Financing Overview",
        "url": "https://www.smecorp.gov.my/images/pdf/SMEFINANCING.pdf",
        "published_date": "2023",
        "license_or_terms": "Public domain / SME Corp official publication",
        "priority_sections_only": False,
    },

    # ── Travel / Immigration ─────────────────────────────────────────────────
    {
        "id": "kastam_customs_declaration_k7",
        "filename": "kastam_customs_declaration_form_k7.pdf",
        "category": "travel",
        "language": "en_bm",
        "source_org": "Royal Malaysian Customs (Kastam)",
        "title": "Customs Declaration Form K7 - Traveller Guide (Bilingual)",
        "url": "https://customs.gov.my/images/05-individu/pelancong/borang-kastam-no.7-lampiran-a.pdf",
        "published_date": "2022-03",
        "license_or_terms": "Public domain / Royal Malaysian Customs official publication",
        "priority_sections_only": False,
    },
    {
        "id": "kastam_cash_declaration",
        "filename": "kastam_cash_declaration_guide.pdf",
        "category": "travel",
        "language": "en",
        "source_org": "Royal Malaysian Customs (Kastam)",
        "title": "Cash and Bearer Negotiable Instrument Declaration Guide",
        "url": "https://www.customs.gov.my/images/05-individu/pelancong/5mac-English-Pamplet-Cash-Declarations-new.pdf",
        "published_date": "2023",
        "license_or_terms": "Public domain / Royal Malaysian Customs official publication",
        "priority_sections_only": False,
    },
    {
        "id": "kastam_prohibited_imports",
        "filename": "kastam_prohibited_imports_order_2023.pdf",
        "category": "travel",
        "language": "en",
        "source_org": "Attorney General's Chambers Malaysia",
        "title": "Customs (Prohibition of Imports) Order 2023",
        "url": "https://lom.agc.gov.my/ilims/upload/portal/akta/outputp/1809215/PUA117.pdf",
        "published_date": "2023",
        "license_or_terms": "Public domain / Malaysian legislation",
        "priority_sections_only": False,
    },
    {
        "id": "imi_visit_pass_extension",
        "filename": "imi_visit_pass_extension_form.pdf",
        "category": "travel",
        "language": "en_bm",
        "source_org": "Immigration Department Malaysia (IMI)",
        "title": "Visit Pass Extension Form",
        "url": "https://www.imi.gov.my/portal2017/images/borang/Pas/Borang%20Permohonan%20Lanjutan%20Pas%20Lawatan.pdf",
        "published_date": "2023",
        "license_or_terms": "Public domain / IMI official publication",
        "priority_sections_only": False,
    },

    # ── Housing ──────────────────────────────────────────────────────────────
    {
        "id": "affordable_housing_strategy",
        "filename": "affordable_housing_strategy.pdf",
        "category": "housing",
        "language": "en",
        "source_org": "EPU",
        "title": "Affordable Housing Strategy Paper",
        "url": "https://ekonomi.gov.my/sites/default/files/2021-05/Strategy%20Paper%2006.pdf",
        "published_date": "2021",
        "license_or_terms": "Public domain / EPU official publication",
        "priority_sections_only": True,
    },

    # ── Emergency / Disaster ─────────────────────────────────────────────────
    {
        "id": "nsc_directive_20_disaster",
        "filename": "nsc_directive_20_disaster_management.pdf",
        "category": "emergency",
        "language": "en",
        "source_org": "National Security Council Malaysia (MKN)",
        "title": "NSC Directive No. 20 - National Disaster Management and Relief Policy",
        "url": "https://www.rcrc-resilience-southeastasia.org/wp-content/uploads/2017/12/1997_policy_and_mechanism_of_national_disaster_management_and_relief_national_security_council_directive.pdf",
        "published_date": "1997",
        "license_or_terms": "Public domain / Malaysian government policy document",
        "priority_sections_only": False,
    },
    {
        "id": "nadma_flood_risk_guideline",
        "filename": "nadma_flood_risk_assessment_guideline.pdf",
        "category": "emergency",
        "language": "en",
        "source_org": "NADMA",
        "title": "Flood Risk Assessment and Mapping Guideline (ASEAN)",
        "url": "https://www.nadma.gov.my/images/nadma/documents/riskassessment/Flood%20Risk%20Assessment%20and%20Mapping%20Guideline_ASEAN_2.pdf",
        "published_date": "2018",
        "license_or_terms": "Public domain / NADMA official publication",
        "priority_sections_only": False,
    },
]

# ── Reserve Documents (fallbacks) ────────────────────────────────────────────

RESERVE_DOCS = [
    {
        "id": "perkeso_2020_booklet",
        "filename": "perkeso_2020_social_security.pdf",
        "category": "social_welfare",
        "language": "en",
        "source_org": "PERKESO",
        "title": "PERKESO Social Security Protection Booklet (Sept 2020)",
        "url": "https://www.perkeso.gov.my/images/dokumen/SEPT_2020-RISALAH_EN.pdf",
        "published_date": "2020-09",
        "license_or_terms": "Public domain / PERKESO official publication",
        "priority_sections_only": False,
    },
    {
        "id": "perkeso_assist_guide",
        "filename": "perkeso_assist_portal_guide.pdf",
        "category": "social_welfare",
        "language": "en",
        "source_org": "PERKESO",
        "title": "PERKESO ASSIST Portal Quick Reference Guide",
        "url": "https://www.perkeso.gov.my/images/dokumen/070922_-_ASSIST_PORTAL_QUICK_REFERENCE_GUIDES.pdf",
        "published_date": "2022-09",
        "license_or_terms": "Public domain / PERKESO official publication",
        "priority_sections_only": False,
    },
    {
        "id": "employment_act_1955_bm",
        "filename": "employment_act_1955_bm.pdf",
        "category": "labor_migrant",
        "language": "bm",
        "source_org": "JTKSM / MOHR",
        "title": "Akta Kerja 1955 (Bahasa Malaysia)",
        "url": "https://jtksm.mohr.gov.my/sites/default/files/2023-11/Akta%20Kerja%201955%20(Akta%20265)_0.pdf",
        "published_date": "2023",
        "license_or_terms": "Public domain / Malaysian legislation",
        "priority_sections_only": True,
    },
    {
        "id": "mfa_entry_visa_procedure",
        "filename": "mfa_entry_visa_procedure_malaysia_2024.pdf",
        "category": "travel",
        "language": "en",
        "source_org": "Ministry of Foreign Affairs Malaysia",
        "title": "Entry and Visa Procedure to Malaysia (2024)",
        "url": "https://www.kln.gov.my/documents/34253/9682852/ENTRY+AND+VISA+PROCEDURE+TO+MALAYSIA.pdf/25d8fce1-b1b2-419e-aa23-366ef06afcaf",
        "published_date": "2024-02",
        "license_or_terms": "Public domain / Malaysian government official publication",
        "priority_sections_only": False,
    },
    {
        "id": "nadma_overview",
        "filename": "nadma_overview_philosophy.pdf",
        "category": "emergency",
        "language": "en",
        "source_org": "NADMA / ADRC",
        "title": "NADMA Overview and Disaster Management Philosophy",
        "url": "https://www.adrc.asia/acdr/2017/documents/7%20Malaysia%20National%20Disaster%20Management%20Agency%20(NADMA)%20and%20its%20philosophy,%20Mr.%20Zainal%20Azman%20Bin%20Abu%20Seman,%20Deputy%20Director%20General,%20NADMA.pdf",
        "published_date": "2017",
        "license_or_terms": "Public domain / ADRC publication",
        "priority_sections_only": False,
    },
]

ALL_CATEGORIES = ["labor_migrant", "social_welfare", "healthcare", "grants", "travel", "housing", "emergency"]


def download_and_validate(doc: dict) -> dict:
    """Download a single document and run quality gates. Returns enriched doc dict."""
    dest = RAW_DIR / doc["category"] / doc["filename"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    doc = doc.copy()
    doc["access_date"] = ACCESS_DATE
    doc["validation"] = {
        "content_type_ok": False,
        "min_size_ok": False,
        "text_extractable": False,
    }

    try:
        resp = requests.get(doc["url"], headers=HEADERS, timeout=30, allow_redirects=True, verify=False)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        doc["validation"]["content_type_ok"] = (
            "pdf" in content_type.lower() or "octet-stream" in content_type.lower()
        )

        dest.write_bytes(resp.content)
        size_kb = len(resp.content) / 1024
        doc["size_kb"] = round(size_kb, 1)
        doc["local_path"] = str(dest.relative_to(KB_ROOT.parent))

        doc["validation"]["min_size_ok"] = size_kb >= MIN_SIZE_KB

        try:
            pdf_doc = fitz.open(str(dest))
            text = "".join(pdf_doc[i].get_text() for i in range(min(3, len(pdf_doc))))
            pdf_doc.close()
            doc["validation"]["text_extractable"] = len(text.strip()) > 50
        except Exception:
            doc["validation"]["text_extractable"] = False

        all_ok = all(doc["validation"].values())
        doc["downloaded"] = all_ok

        if all_ok:
            print(f"  OK   {doc['title']} ({size_kb:.0f} KB)")
        else:
            failed = [k for k, v in doc["validation"].items() if not v]
            print(f"  WARN {doc['title']} — failed: {', '.join(failed)}")
            if dest.exists():
                dest.unlink()

    except Exception as e:
        doc["downloaded"] = False
        doc["error"] = str(e)
        print(f"  FAIL {doc['title']} — {e}")

    return doc


def print_report(results: list):
    total = len(results)
    ok = [r for r in results if r.get("downloaded")]
    failed = [r for r in results if not r.get("downloaded")]

    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    print(f"\nTotal: {len(ok)}/{total} documents downloaded successfully")

    categories = {}
    for r in ok:
        cat = r["category"]
        categories[cat] = categories.get(cat, 0) + 1
    print("\nBy category:")
    for cat in ALL_CATEGORIES:
        count = categories.get(cat, 0)
        print(f"  {cat}: {count}")

    languages = {}
    for r in ok:
        lang = r["language"]
        languages[lang] = languages.get(lang, 0) + 1
    print("\nBy language:")
    for lang, count in sorted(languages.items()):
        print(f"  {lang}: {count}")

    bm_count = sum(1 for r in ok if "bm" in r["language"])
    print(f"\nBM-content docs: {bm_count} (target: >= 4)")

    if failed:
        print("\nFailed:")
        for r in failed:
            print(f"  {r['title']}: {r.get('error', 'validation failed')}")

    by_size = sorted(ok, key=lambda r: r.get("size_kb", 0), reverse=True)
    print("\nTop 5 largest files:")
    for r in by_size[:5]:
        print(f"  {r['filename']}: {r.get('size_kb', 0):.0f} KB")

    print("=" * 60)


def main():
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    print("DualComm — downloading knowledge base documents...")
    print(f"Access date: {ACCESS_DATE}\n")

    for cat in ALL_CATEGORIES:
        (RAW_DIR / cat).mkdir(parents=True, exist_ok=True)
    (KB_ROOT / "metadata").mkdir(parents=True, exist_ok=True)

    print("── Primary Documents ──")
    results = []
    for doc in PRIMARY_DOCS:
        results.append(download_and_validate(doc))

    failed_count = sum(1 for r in results if not r.get("downloaded"))
    if failed_count > 0:
        print(f"\n── Substituting {failed_count} failed doc(s) from reserves ──")
        reserve_idx = 0
        for i, result in enumerate(results):
            if not result.get("downloaded") and reserve_idx < len(RESERVE_DOCS):
                reserve_doc = RESERVE_DOCS[reserve_idx].copy()
                reserve_idx += 1
                print(f"  Replacing '{result['title']}' → '{reserve_doc['title']}'")
                new_result = download_and_validate(reserve_doc)
                if new_result.get("downloaded"):
                    results[i] = new_result

    with open(META_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nMetadata written to {META_FILE}")

    print_report(results)

    ok_count = sum(1 for r in results if r.get("downloaded"))
    if ok_count < 15:
        print(f"\nWARNING: Only {ok_count} docs succeeded. Review failed URLs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
