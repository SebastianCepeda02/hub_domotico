// ============================================================
// DomoHub — estado global de la aplicación
// ============================================================

const Store = {

  // ── Estado ───────────────────────────────────────────────────────────────────

  dashboard:    [],
  reglas:       [],
  escenas:      [],
  system:       null,
  systemError:  null,
  _systemTimer: null,

  // ── Dashboard ─────────────────────────────────────────────────────────────────

  async cargarDashboard() {
    try {
      const data = await Api.dashboard.get();
      // mutar en lugar de reemplazar — Alpine mantiene la reactividad
      this.dashboard.splice(0, this.dashboard.length, ...data);
    } catch (e) {
      console.error("[store] dashboard:", e.message);
      throw e;
    }
  },

  // ── Actuadores ────────────────────────────────────────────────────────────────

  async toggleActuador(id) {
    try {
      const actualizado = await Api.actuadores.estado(id, "toggle");
      const item = this.dashboard.find(d => d.id === id && d.category === "actuador");
      if (item) item.on = actualizado.estado === "on";
    } catch (e) {
      console.error("[store] toggleActuador:", e.message);
      throw e;
    }
  },

  async setEstadoActuador(id, estado) {
    try {
      const actualizado = await Api.actuadores.estado(id, estado);
      const item = this.dashboard.find(d => d.id === id && d.category === "actuador");
      if (item) item.on = actualizado.estado === "on";
    } catch (e) {
      console.error("[store] setEstadoActuador:", e.message);
      throw e;
    }
  },

  // ── Edición de nombre ─────────────────────────────────────────────────────────

  async editarSensor(id, nombre) {
    try {
      await Api.sensores.update(id, { nombre });
      const item = this.dashboard.find(d => d.id === id && d.category === "sensor");
      if (item) item.name = nombre;
    } catch (e) {
      console.error("[store] editarSensor:", e.message);
      throw e;
    }
  },

  async editarActuador(id, nombre) {
    try {
      await Api.actuadores.update(id, { nombre });
      const item = this.dashboard.find(d => d.id === id && d.category === "actuador");
      if (item) item.name = nombre;
    } catch (e) {
      console.error("[store] editarActuador:", e.message);
      throw e;
    }
  },

  async editarDispositivo(id, datos) {
    try {
      await Api.dispositivos.update(id, datos);
      // actualizar ubicacion en todos los items del dashboard que pertenezcan a este dispositivo
      if (datos.ubicacion) {
        this.dashboard
          .filter(d => d.dispositivo_id === id)
          .forEach(d => d.room = datos.ubicacion);
      }
    } catch (e) {
      console.error("[store] editarDispositivo:", e.message);
      throw e;
    }
  },

  async eliminarDispositivo(id) {
    try {
      await Api.dispositivos.delete(id);
      this.dashboard = this.dashboard.filter(d => d.dispositivo_id !== id);
    } catch (e) {
      console.error("[store] eliminarDispositivo:", e.message);
      throw e;
    }
  },

  // ── Reglas ────────────────────────────────────────────────────────────────────

  async cargarReglas() {
    try {
      this.reglas = await Api.reglas.list();
    } catch (e) {
      console.error("[store] cargarReglas:", e.message);
      throw e;
    }
  },

  async crearRegla(datos) {
    try {
      const nueva = await Api.reglas.create(datos);
      this.reglas.push(nueva);
    } catch (e) {
      console.error("[store] crearRegla:", e.message);
      throw e;
    }
  },

  async toggleRegla(id) {
    try {
      const regla  = this.reglas.find(r => r.id === id);
      if (!regla) return;
      const activa = regla.activa === 1 ? 0 : 1;
      await Api.reglas.update(id, { activa });
      regla.activa = activa;
    } catch (e) {
      console.error("[store] toggleRegla:", e.message);
      throw e;
    }
  },

  async eliminarRegla(id) {
    try {
      await Api.reglas.delete(id);
      this.reglas = this.reglas.filter(r => r.id !== id);
    } catch (e) {
      console.error("[store] eliminarRegla:", e.message);
      throw e;
    }
  },

  // ── Escenas ───────────────────────────────────────────────────────────────────

  async cargarEscenas() {
    try {
      this.escenas = await Api.escenas.list();
    } catch (e) {
      console.error("[store] cargarEscenas:", e.message);
      throw e;
    }
  },

  async activarEscena(id) {
    try {
      const resultado = await Api.escenas.activar(id);
      // reflejar el nuevo estado del actuador en el dashboard
      const item = this.dashboard.find(d => d.id === resultado.actuador_id && d.category === "actuador");
      if (item) item.on = resultado.estado_nuevo === "on";
      return resultado;
    } catch (e) {
      console.error("[store] activarEscena:", e.message);
      throw e;
    }
  },

  async crearEscena(datos) {
    try {
      const nueva = await Api.escenas.create(datos);
      this.escenas.push(nueva);
    } catch (e) {
      console.error("[store] crearEscena:", e.message);
      throw e;
    }
  },

  async toggleEscena(id) {
    try {
      const escena = this.escenas.find(e => e.id === id);
      if (!escena) return;
      const activa = escena.activa === 1 ? 0 : 1;
      await Api.escenas.update(id, { activa });
      escena.activa = activa;
    } catch (e) {
      console.error("[store] toggleEscena:", e.message);
      throw e;
    }
  },

  async eliminarEscena(id) {
    try {
      await Api.escenas.delete(id);
      this.escenas = this.escenas.filter(e => e.id !== id);
    } catch (e) {
      console.error("[store] eliminarEscena:", e.message);
      throw e;
    }
  },

  // ── Sistema ───────────────────────────────────────────────────────────────────

  async fetchSystem() {
    this.systemError = null;
    try {
      this.system = await Api.sistema.estado();
      // Forzar a Lucide a renderizar iconos nuevos
      setTimeout(() => { if(window.lucide) lucide.createIcons(); }, 100);
    } catch (e) {
      console.error("[store] fetchSystem:", e.message);
      this.systemError = "No se pudo obtener el estado del sistema";
    }
  },

  startSystemPolling() {
    this.fetchSystem();
    //this.stopSystemPolling();
    if (this._systemTimer) clearInterval(this._systemTimer);
    // Usamos flecha () => para no perder el "this"
    this._systemTimer = setInterval(() => this.fetchSystem(), 30000);
  },

  stopSystemPolling() {
    if (this._systemTimer) {
      clearInterval(this._systemTimer);
      this._systemTimer = null;
    }
  },

  startDashboardPolling() {
    if (this._dashboardTimer) clearInterval(this._dashboardTimer);
    this._dashboardTimer = setInterval(async () => {
      try {
        const data = await Api.dashboard.get();
        this.dashboard.splice(0, this.dashboard.length, ...data);
      } catch (e) {
        console.error("[poll] dashboard:", e.message);
        // no lanza — el polling falla silenciosamente
      }
    }, 30000);
  },

  stopDashboardPolling() {
    if (this._dashboardTimer) {
      clearInterval(this._dashboardTimer);
      this._dashboardTimer = null;
    }
  },

  // ── Vinculación ───────────────────────────────────────────────────────────────

  async generarCodigo() {
    try {
      return await Api.vincular.codigo();
    } catch (e) {
      console.error("[store] generarCodigo:", e.message);
      throw e;
    }
  },

  // ── Helpers de dashboard ──────────────────────────────────────────────────────

  get sensores() {
    return this.dashboard.filter(d => d.category === "sensor");
  },

  get actuadores() {
    return this.dashboard.filter(d => d.category === "actuador");
  },

  get rooms() {
    return [...new Set(this.dashboard.map(d => d.room))];
  },

  devicesByRoom(room) {
    return this.dashboard.filter(d => d.room === room);
  },

  // ── Favoritos ────────────────────────────────────────────────────────

  async toggleFavorito(id, category) {
    try {
      if (category === 'sensor') {
        await Api.sensores.toggleFavorito(id);
      } else {
        await Api.actuadores.toggleFavorito(id);
      }
      const item = this.dashboard.find(d => d.id === id && d.category === category);
      if (item) item.favorite = !item.favorite;
    } catch (e) {
      console.error("[store] toggleFavorito:", e.message);
      throw e;
    }
  },

  // ── Helpers de sistema ────────────────────────────────────────────────────────

  pct(s) {
    if (!s) return 0;
    const n = parseFloat(String(s).replace("%", "").trim());
    return isNaN(n) ? 0 : Math.max(0, Math.min(100, n));
  },

  sdUsedPct() {
    const s = this.system?.almacenamiento_sd;
    if (!s || !s.total_gb) return 0;
    return Math.max(0, Math.min(100, ((s.total_gb - s.libre_gb) / s.total_gb) * 100));
  },
};

document.addEventListener('alpine:init', () => {window.globalStore = Alpine.reactive(Store);});