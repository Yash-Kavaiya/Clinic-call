const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function setToken(token) {
  if (typeof window !== "undefined") localStorage.setItem("token", token);
}

export function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}

export async function api(path, { method = "GET", json, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = token ?? getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`${API}${path}`, {
    method,
    headers,
    body: json ? JSON.stringify(json) : undefined,
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!res.ok) {
    const detail = data.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}
