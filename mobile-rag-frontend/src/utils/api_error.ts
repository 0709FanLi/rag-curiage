type ValidationDetailItem = {
  msg?: unknown;
  loc?: unknown;
  type?: unknown;
};

function extract_chinese(text: string): string {
  const raw = String(text || '').trim();
  if (!raw) {
    return '';
  }

  // Common Pydantic message format: "Value error, 验证码格式不正确"
  const comma_idx = raw.indexOf(',');
  if (comma_idx >= 0) {
    const tail = raw.slice(comma_idx + 1).trim();
    if (tail) {
      return tail;
    }
  }

  // Try to keep only the Chinese part (plus digits/spaces and common punctuation).
  const match = raw.match(/[\u4e00-\u9fff][\u4e00-\u9fff0-9\s，。；：、！“”‘’（）()\-]*$/);
  if (match && match[0]) {
    return match[0].trim();
  }

  return raw;
}

function normalize_validation_details(details: unknown): string[] {
  if (!Array.isArray(details)) {
    return [];
  }

  const messages: string[] = [];
  for (const item of details) {
    const msg = (item as ValidationDetailItem | null)?.msg;
    if (typeof msg !== 'string') {
      continue;
    }
    const cn = extract_chinese(msg);
    if (cn) {
      messages.push(cn);
    }
  }
  return messages;
}

export function get_error_message(err: unknown, fallback: string): string {
  const any_err = err as any;
  const detail =
    any_err?.response?.data?.detail ??
    any_err?.data?.detail ??
    any_err?.response?.data ??
    any_err?.data;

  // FastAPI validation errors: { detail: [ { msg, loc, ... }, ... ] }
  const validation_messages = normalize_validation_details(detail);
  if (validation_messages.length > 0) {
    // De-duplicate while preserving order
    const seen = new Set<string>();
    const uniq = validation_messages.filter((m) => {
      if (seen.has(m)) {
        return false;
      }
      seen.add(m);
      return true;
    });
    return uniq.join('；');
  }

  if (typeof detail === 'string' && detail.trim()) {
    return extract_chinese(detail);
  }

  if (typeof any_err?.message === 'string' && any_err.message.trim()) {
    return extract_chinese(any_err.message);
  }

  return fallback;
}


