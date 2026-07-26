const LOCAL_HTTP_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

type ApiBaseResolution =
  | { readonly valid: true; readonly value: string }
  | { readonly valid: false };

let cachedResolution: ApiBaseResolution | undefined;

function invalidConfiguration(): never {
  cachedResolution = { valid: false };
  throw new Error("API_CONFIGURATION_INVALID");
}

export function getApiBaseUrl(): string {
  if (cachedResolution) {
    if (cachedResolution.valid) return cachedResolution.value;
    throw new Error("API_CONFIGURATION_INVALID");
  }

  const configuredValue = import.meta.env.VITE_API_BASE_URL;
  if (typeof configuredValue !== "string" || configuredValue.trim() === "") {
    return invalidConfiguration();
  }

  let url: URL;
  try {
    url = new URL(configuredValue.trim());
  } catch {
    return invalidConfiguration();
  }

  if (
    !["http:", "https:"].includes(url.protocol)
    || (url.protocol === "http:" && !LOCAL_HTTP_HOSTS.has(url.hostname))
    || url.username !== ""
    || url.password !== ""
    || url.search !== ""
    || url.hash !== ""
  ) {
    return invalidConfiguration();
  }

  const normalizedPath = url.pathname.replace(/\/+$/, "");
  url.pathname = normalizedPath;
  const normalizedValue = url.toString().replace(/\/$/, "");
  cachedResolution = { valid: true, value: normalizedValue };
  return normalizedValue;
}
