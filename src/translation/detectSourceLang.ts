import type { SupportedSourceLang } from "./translateToMalay.js";

export function detect_source_lang(text: string): SupportedSourceLang {
  // If it contains CJK ideographs, assume Cantonese/Chinese script -> yue_Hant.
  // Otherwise, assume Javanese in Latin script -> jav_Latn.
  return /[\u3400-\u9FFF]/u.test(text) ? "yue_Hant" : "jav_Latn";
}

