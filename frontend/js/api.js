// ============================================================
// DomoHub — capa de comunicación con el backend
// ============================================================


//const API_BASE = "http://127.0.0.1:8000";
//const API_KEY  = "tu-clave-secreta-123";
const API_BASE = "https://api.domotic-dev.online";

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    credentials: "include",  // ← necesario para enviar la cookie
    ...options,
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || `Error ${res.status}`);
  }

  return res.json();
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

const Api = {

  dashboard: {
    get: () => request("/dashboard/"),
  },

  // ── Dispositivos ─────────────────────────────────────────────────────────────

  dispositivos: {
    list:   ()           => request("/dispositivos/"),
    get:    (id)         => request(`/dispositivos/${id}`),
    update: (id, datos)  => request(`/dispositivos/${id}`, { method: "PATCH", body: JSON.stringify(datos) }),
    delete: (id)         => request(`/dispositivos/${id}`, { method: "DELETE" }),
  },

  // ── Sensores ──────────────────────────────────────────────────────────────────

  sensores: {
    list:     ()          => request("/sensores/"),
    get:      (id)        => request(`/sensores/${id}`),
    update:   (id, datos) => request(`/sensores/${id}`,          { method: "PATCH", body: JSON.stringify(datos) }),
    lecturas: (id, limit) => request(`/sensores/${id}/lecturas?limite=${limit || 50}`),
    toggleFavorito: (id) => request(`/sensores/${id}/favorito`, { method: "PATCH" }),
  },

  // ── Actuadores ────────────────────────────────────────────────────────────────

  actuadores: {
    list:   ()            => request("/actuadores/"),
    get:    (id)          => request(`/actuadores/${id}`),
    //getStreamUrl:    (id)          => request(`/actuadores/${id}/stream`),
    update: (id, datos)   => request(`/actuadores/${id}`,         { method: "PATCH", body: JSON.stringify(datos) }),
    estado: (id, estado)  => request(`/actuadores/${id}/estado`,  { method: "PUT",   body: JSON.stringify({ estado }) }),
    toggleFavorito: (id) => request(`/actuadores/${id}/favorito`, { method: "PATCH" }),
  },

  // ── Automatizaciones — Reglas ─────────────────────────────────────────────────

  reglas: {
    list:   ()           => request("/automatizaciones/reglas"),
    create: (datos)      => request("/automatizaciones/reglas",      { method: "POST",   body: JSON.stringify(datos) }),
    update: (id, datos)  => request(`/automatizaciones/reglas/${id}`, { method: "PATCH",  body: JSON.stringify(datos) }),
    delete: (id)         => request(`/automatizaciones/reglas/${id}`, { method: "DELETE" }),
  },

  // ── Automatizaciones — Escenas ────────────────────────────────────────────────

  escenas: {
    list:     ()          => request("/automatizaciones/escenas"),
    create:   (datos)     => request("/automatizaciones/escenas",          { method: "POST",   body: JSON.stringify(datos) }),
    update:   (id, datos) => request(`/automatizaciones/escenas/${id}`,    { method: "PATCH",  body: JSON.stringify(datos) }),
    delete:   (id)        => request(`/automatizaciones/escenas/${id}`,    { method: "DELETE" }),
    activar:  (id)        => request(`/automatizaciones/escenas/${id}/activar`, { method: "POST" }),
  },

  // ── Vinculación ───────────────────────────────────────────────────────────────

  vincular: {
    codigo:    ()       => request("/vincular/codigo",    { method: "POST" }),
    registrar: (datos)  => request("/vincular/registrar", { method: "POST", body: JSON.stringify(datos) }),
  },

  // ── Sistema ───────────────────────────────────────────────────────────────────

  sistema: {
    estado: () => request("/sistema/estado"),
  },
};