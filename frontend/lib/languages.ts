import type { Language } from "./api";

export const LANGUAGES: { code: Language; label: string; flag: string }[] = [
  { code: "es", label: "Spanish", flag: "🇪🇸" },
  { code: "fr", label: "French", flag: "🇫🇷" },
  { code: "it", label: "Italian", flag: "🇮🇹" },
];

export function languageMeta(code: Language) {
  return LANGUAGES.find((l) => l.code === code) ?? LANGUAGES[0];
}
