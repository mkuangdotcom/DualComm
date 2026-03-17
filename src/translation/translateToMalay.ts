import { config } from "../config.js";

export type SupportedSourceLang = "yue_Hant" | "jav_Latn";

type TranslationPipeline = (
  text: string,
  options: { src_lang: string; tgt_lang: string },
) => Promise<Array<{ translation_text: string }>>;

let translatorPromise: Promise<TranslationPipeline> | null = null;

async function getTranslator(): Promise<TranslationPipeline> {
  if (translatorPromise) return translatorPromise;

  translatorPromise = (async () => {
    const { pipeline, env } = await import("@xenova/transformers");

    // Keep model cache inside the repo by default
    env.cacheDir = process.env.TRANSFORMERS_CACHE_DIR || ".hf_cache";

    const requested = config.translation.nllb.model;
    const model =
      requested === "facebook/nllb-200-distilled-600M"
        ? "Xenova/nllb-200-distilled-600M"
        : requested;

    return (await pipeline("translation", model)) as TranslationPipeline;
  })();

  return translatorPromise;
}

export async function translate_to_malay(
  text: string,
  src_lang: SupportedSourceLang,
): Promise<string> {
  const normalized = (text || "").trim();
  if (!normalized) return "";

  const translator = await getTranslator();
  const out = await translator(normalized, {
    src_lang,
    tgt_lang: "zsm_Latn",
  });
  return (out?.[0]?.translation_text || "").trim();
}

