from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

from groq import Groq
from mcp import ClientSession, StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)


SEKTOR: Dict[str, Dict[str, str]] = {
    "jtk": {
        "emel": "jtksm@mohr.gov.my",
        "kod": "JTK",
        "org": "Jabatan Tenaga Kerja Semenanjung Malaysia",
    },
    "jkm": {
        "emel": "pertanyaan@jkm.gov.my",
        "kod": "JKM",
        "org": "Jabatan Kebajikan Masyarakat Malaysia",
    },
    "kkm": {
        "emel": "cprc@moh.gov.my",
        "kod": "KKM",
        "org": "Kementerian Kesihatan Malaysia",
    },
    "jpn": {
        "emel": "pro@jpn.gov.my",
        "kod": "JPN",
        "org": "Jabatan Pendaftaran Negara",
    },
}


class MCPAdvocacyService:
    """
    Real MCP client integration for advocacy send flow.
    """

    def __init__(self, groq_api_key: str | None):
        self.groq_client = Groq(api_key=groq_api_key)
        self.sender_name = os.environ.get("SENDER_NAME", "Pegawai Advokasi DualComm")
        self.sender_role = os.environ.get("SENDER_ROLE", "Pengarah Operasi")
        self.project_root = Path(__file__).resolve().parents[3]
        self.mcp_server_path = self.project_root / "mcp_agent" / "mcp_server.py"

    async def translate_text(self, text: str, user_language_context: str) -> str:
        if not user_language_context or user_language_context.lower() in {
            "malay",
            "bahasa melayu",
            "1",
            "2",
            "3",
            "4",
        }:
            return text

        try:
            prompt = (
                "You are a strict translation engine. Translate only the provided system message into the exact language/dialect used in the user context.\n"
                f"User context: '{user_language_context}'\n\n"
                "Rules:\n"
                "1. Do not answer the question.\n"
                "2. Keep all formatting and bullets.\n"
                "3. Output only translated text.\n"
            )
            result = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
            )
            return result.choices[0].message.content.strip()
        except Exception:
            return text

    async def get_menu(self, user_language_context: str = "Malay") -> str:
        base_menu = (
            "*Sistem Advokasi Kerajaan DualComm*\n\n"
            "Sila pilih sektor aduan:\n"
            "1) Sektor Buruh & Pekerjaan (JTK)\n"
            "2) Sektor Kebajikan Sosial (JKM)\n"
            "3) Sektor Kesihatan Awam (KKM)\n"
            "4) Sektor Pendaftaran Negara (JPN)\n\n"
            "Taip nombor sektor (1-4)."
        )
        return await self.translate_text(base_menu, user_language_context)

    async def get_info_request(self, user_language_context: str = "Malay") -> str:
        return await self.translate_text(
            "Boleh berikan nama dan jawatan anda?",
            user_language_context,
        )

    async def generate_draft(self, sector: str, user_text: str) -> Dict[str, Any]:
        cfg = SEKTOR.get(sector, SEKTOR["kkm"])
        prompt = self._build_arahan_sistem(sector)

        try:
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_text},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=3500,
            )
            keputusan = json.loads(response.choices[0].message.content)

            detected_name = keputusan.get("nama_pengirim_dikesan") or self.sender_name
            detected_role = keputusan.get("jawatan_pengirim_dikesan") or self.sender_role
            tajuk_surat = keputusan.get("tajuk_surat") or f"ADUAN RASMI {cfg['kod']}"

            draft_msg = (
                "*Draf advokasi siap*\n\n"
                f"Tajuk: {tajuk_surat}\n"
                f"Penerima: {cfg['org']}\n"
                f"Pengirim: {detected_name} ({detected_role})\n\n"
                f"Sahkan untuk hantar ke {cfg['emel']}?\n"
                "1) Ya, hantar sekarang\n"
                "2) Tidak, batalkan\n\n"
                "Taip 1 atau 2."
            )
            draft_msg_translated = await self.translate_text(draft_msg, user_text)

            return {
                "status": "draft_ready",
                "text": draft_msg_translated,
                "attachments": [],
                "keputusan": keputusan,
                "sector": sector,
                "detected_name": detected_name,
                "detected_role": detected_role,
            }
        except Exception:
            logger.error("[Advocacy-MCP] Draft error: %s", traceback.format_exc())
            return {
                "status": "error",
                "text": "Maaf, ralat berlaku semasa memproses draf advokasi anda. Sila cuba lagi.",
                "attachments": [],
            }

    async def execute_send(self, draft_data: Dict[str, Any]) -> str:
        keputusan = draft_data.get("keputusan", {}) or {}
        sector = draft_data.get("sector", "kkm")
        cfg = SEKTOR.get(sector, SEKTOR["kkm"])

        arguments: Dict[str, Any] = {
            "nama_pengirim": draft_data.get("detected_name", self.sender_name),
            "jawatan_pengirim": draft_data.get("detected_role", self.sender_role),
            "sektor": sector,
            "emel_sasaran": cfg["emel"],
            "subjek_emel": keputusan.get(
                "subjek_emel",
                f"[UNTUK PERHATIAN: {cfg['kod']}] PENGHANTARAN SURAT RASMI",
            ),
            "tajuk_surat": keputusan.get("tajuk_surat") or f"ADUAN RASMI {cfg['kod']}",
            "nama_komuniti": keputusan.get("nama_komuniti") or "komuniti yang diwakili",
            "ringkasan_isu": keputusan.get("ringkasan_isu") or "isu yang dilaporkan",
            "data_pdf_json": json.dumps(keputusan.get("data_pdf", {}), ensure_ascii=False),
            "baris_csv_json": "[]",
            "nombor_kes": keputusan.get("nombor_kes", ""),
        }

        result_text = await self._call_mcp_tool(
            tool_name="hantar_advokasi_kerajaan",
            arguments=arguments,
        )
        logger.info("[Advocacy-MCP] Send result: %s", result_text)
        return result_text

    async def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if not self.mcp_server_path.exists():
            raise RuntimeError(f"MCP server file not found: {self.mcp_server_path}")

        server_params = StdioServerParameters(
            command=os.environ.get("PYTHON_EXECUTABLE", sys.executable),
            args=[str(self.mcp_server_path)],
            cwd=str(self.project_root),
            env=dict(os.environ),
        )

        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tool_result = await session.call_tool(name=tool_name, arguments=arguments)

        if tool_result.isError:
            raise RuntimeError(self._extract_tool_text(tool_result))

        return self._extract_tool_text(tool_result)

    @staticmethod
    def _extract_tool_text(tool_result: Any) -> str:
        texts: list[str] = []
        for block in getattr(tool_result, "content", []) or []:
            if getattr(block, "type", "") == "text":
                texts.append(getattr(block, "text", ""))
        joined = "\n".join([t for t in texts if t]).strip()
        if joined:
            return joined
        return str(tool_result)

    def _build_arahan_sistem(self, sektor: str) -> str:
        cfg = SEKTOR.get(sektor, SEKTOR["kkm"])
        arahan_tambahan = {
            "jtk": "Aduan buruh. Nyatakan isu gaji/pasport dengan fakta khusus.",
            "jkm": "Aduan kebajikan sosial. Nyatakan keperluan lawatan rumah dan bantuan.",
            "kkm": "Aduan kesihatan awam. Nyatakan kekurangan bekalan/perkhidmatan dengan terperinci.",
            "jpn": "Aduan pendaftaran negara. Nyatakan isu dokumen dan tindakan diperlukan.",
        }.get(sektor, "Surat rasmi kerajaan.")

        return f"""
Anda adalah sistem advokasi kerajaan Malaysia.
{arahan_tambahan}

Ekstrak nama dan jawatan pengirim jika ada.
Kembalikan JSON sah sahaja dengan format berikut:
{{
  "nama_pengirim_dikesan": "...",
  "jawatan_pengirim_dikesan": "...",
  "subjek_emel": "[UNTUK PERHATIAN: {cfg['kod']}] PENGHANTARAN SURAT RASMI: [TAJUK]",
  "tajuk_surat": "[TAJUK SPESIFIK]",
  "nama_komuniti": "...",
  "ringkasan_isu": "...",
  "data_pdf": {{
    "title": "[TAJUK]",
    "paragraphs": [
      "Dengan hormatnya saya merujuk kepada perkara di atas.",
      "[Perenggan terperinci 2]",
      "[Perenggan terperinci 3]",
      "[Perenggan terperinci 4]",
      "[Perenggan terperinci 5]",
      "[Perenggan terperinci 6]"
    ],
    "additional_sections": [
      {{"heading": "FAKTA KES", "lines": ["Fakta 1", "Fakta 2"]}},
      {{"heading": "RUJUKAN UNDANG-UNDANG", "lines": ["Rujukan 1"]}}
    ],
    "closing": "Segala perhatian pihak Tuan amat dihargai."
  }},
  "nombor_kes": "DUALCOMM-{cfg['kod']}-2026-001"
}}
"""
