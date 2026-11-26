// Form helpers for the built-in templates. The templates themselves (fields and layout) are
// served by the API: GET /v1/templates, POST /v1/templates/{id}/render.

export function isoDate(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function isoTime(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}`;
}

/** Browser local time for the `now` of a render request ("2026-11-25T14:07:00"). */
export function localNow(d = new Date()) {
  return `${isoDate(d)}T${isoTime(d)}:00`;
}

/** Same automatic values as the server applies to omitted keys. */
export function autoValue(auto, now) {
  if (auto === "today") return isoDate(now);
  if (auto === "now") return isoTime(now);
  if (auto === "id") return `T-${isoDate(now).slice(5).replace("-", "")}-${isoTime(now).replace(":", "")}`;
  return "";
}

/** Initial form values: defaults, automatic dates/times and card ids, else empty. */
export function initialValues(template, now = new Date()) {
  const values = {};
  for (const f of template.fields) {
    if (f.default !== null && f.default !== undefined) values[f.key] = f.default;
    else if (f.type === "checkbox") values[f.key] = false;
    else values[f.key] = autoValue(f.auto, now);
  }
  return values;
}

export function missingRequired(template, values) {
  return template.fields.filter((f) => f.required && !String(values[f.key] ?? "").trim()).map((f) => f.key);
}

/** 422 details → { fieldKey: reason } for loc ["body", "values", key]. */
export function errorsByField(body) {
  const out = {};
  for (const d of body?.details ?? []) {
    const loc = Array.isArray(d.loc) ? d.loc : [];
    const i = loc.indexOf("values");
    if (i >= 0 && typeof loc[i + 1] === "string") out[loc[i + 1]] = d.reason;
  }
  return out;
}
