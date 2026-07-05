import { parseOptionalHttpUrl } from "@/lib/safe-url";

export function formString(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

export function optionalHttpUrl(formData: FormData, key: string): string | null {
  return parseOptionalHttpUrl(formString(formData, key));
}
