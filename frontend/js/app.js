// ============================================================
// DomoHub — lógica Alpine.js (solo UI, sin fetch directos)
// ============================================================

function domoHub() {

  const globalStore = Alpine.reactive(Store);

  return {
    
    // ── Estado UI ───────────────────────────────────────────────────────────────

    page:        'home',
    sidebarOpen: true,
    search:      '',
    loading:     false,
    apiStatus:   'Conectando…',

    toast:  { show: false, message: '', type: 'info' },
    modal:  { show: false, type: null, data: {} },

    // ── Referencias al store ────────────────────────────────────────────────────

    get dashboard()   { return globalStore.dashboard   },
    get reglas()      { return globalStore.reglas      },
    get escenas()     { return globalStore.escenas     },
    get system()      { return globalStore.system      },
    get systemError() { return globalStore.systemError },

    // ── Nav ─────────────────────────────────────────────────────────────────────

    nav: [
      { id: 'home',        label: 'Inicio',           icon: 'home'     },
      { id: 'devices',     label: 'Dispositivos',     icon: 'cpu'      },
      { id: 'automations', label: 'Automatizaciones', icon: 'workflow' },
      { id: 'system',      label: 'Sistema',          icon: 'server'   },
    ],

    // ── Init ────────────────────────────────────────────────────────────────────

    async init() {
      try {
        await fetch('/auth/verificar').then(r => {
          if (!r.ok) window.location.href = '/app/login.html';
        });
      } catch (e) {
        window.location.href = '/app/login.html';
      }

      await this.cargarDashboard();
      globalStore.startSystemPolling();
      globalStore.startDashboardPolling();
      
      await this.cargarDashboard();
      globalStore.startSystemPolling();
      globalStore.startDashboardPolling();
      
      this.$watch('page', (p) => {
        this.$nextTick(() => lucide.createIcons());
        if (p === 'system')      { globalStore.startSystemPolling(); }
        else                     { globalStore.stopSystemPolling();  }
        if (p === 'automations') { this.cargarAutomatizaciones(); }
      });

      this.$watch('dashboard',   () => this.$nextTick(() => lucide.createIcons()), { deep: true });
      this.$watch('search',      () => this.$nextTick(() => lucide.createIcons()));
      this.$watch('system',      () => this.$nextTick(() => lucide.createIcons()));
    },
    
    async cargarDashboard() {
      this.loading = true;
      try {
        await globalStore.cargarDashboard();
        this.apiStatus = 'Conectado';
      } catch (e) {
        this.apiStatus = 'API offline';
        this.notify('No se pudo conectar con el hub', 'error');
      } finally {
        this.loading = false;
        this.$nextTick(() => lucide.createIcons());
      }
    },

    async cargarAutomatizaciones() {
      try {
        await Promise.all([globalStore.cargarReglas(), globalStore.cargarEscenas()]);
      } catch (e) {
        this.notify('Error cargando automatizaciones', 'error');
      }
    },

    // ── Helpers de vista ────────────────────────────────────────────────────────

    pageTitle() {
      return ({ home: 'Inicio', devices: 'Dispositivos', automations: 'Automatizaciones', system: 'Sistema' })[this.page];
    },

    greeting() {
      const h = new Date().getHours();
      if (h < 6)  return 'Buenas noches';
      if (h < 13) return 'Buenos días';
      if (h < 21) return 'Buenas tardes';
      return 'Buenas noches';
    },

    iconFor(kind) {
      return ({
        temperature: 'thermometer',
        humidity:    'droplets',
        light:       'lightbulb',
        plug:        'plug',
        motion:      'activity',
        relay:       'zap',
        camera:      'video',
      })[kind] || 'circle';
    },

    // ── Filtros de dashboard ────────────────────────────────────────────────────

    favoriteRooms() {
      return [...new Set(globalStore.dashboard.filter(d => d.favorite).map(d => d.room))];
    },

    devicesByRoom(room) {
      return globalStore.devicesByRoom(room);
    },

    filteredDevices() {
      const q = this.search.toLowerCase();
      if (!q) return globalStore.dashboard;
      return globalStore.dashboard.filter(d =>
        d.name.toLowerCase().includes(q) ||
        d.room.toLowerCase().includes(q) ||
        d.kind.toLowerCase().includes(q)
      );
    },

    // ── Acciones de dispositivos ────────────────────────────────────────────────

    async toggleActuador(id) {
      try {
        await globalStore.toggleActuador(id);
        const item = globalStore.dashboard.find(d => d.id === id && d.category === "actuador");
        this.notify(`${item?.name} → ${item?.on ? 'ON' : 'OFF'}`);
      } catch (e) {
        this.notify('Error al cambiar estado', 'error');
      }
    },

    async activarEscena(escena) {
      try {
        await globalStore.activarEscena(escena.id);
        this.notify(`Escena «${escena.nombre}» activada`);
      } catch (e) {
        this.notify('Error al activar escena', 'error');
      }
    },

    async toggleRegla(id) {
      try {
        await globalStore.toggleRegla(id);
      } catch (e) {
        this.notify('Error al cambiar regla', 'error');
      }
    },

    async toggleEscena(id) {
      try {
        await globalStore.toggleEscena(id);
      } catch (e) {
        this.notify('Error al cambiar escena', 'error');
      }
    },

    async eliminarRegla(id) {
      try {
        await globalStore.eliminarRegla(id);
        this.notify('Regla eliminada');
      } catch (e) {
        this.notify('Error al eliminar regla', 'error');
      }
    },

    async eliminarEscena(id) {
      try {
        await globalStore.eliminarEscena(id);
        this.notify('Escena eliminada');
      } catch (e) {
        this.notify('Error al eliminar escena', 'error');
      }
    },

    async eliminarDispositivo(id) {
      try {
        await globalStore.eliminarDispositivo(id);
        this.cerrarModal();
        this.notify('Dispositivo desvinculado');
      } catch (e) {
        this.notify('Error al desvincular dispositivo', 'error');
      }
    },

    async toggleFavorito(id, category) {
      try {
        await globalStore.toggleFavorito(id, category);
      } catch (e) {
        this.notify('Error al actualizar favorito', 'error');
      }
    },

    // ── Modales ─────────────────────────────────────────────────────────────────

    abrirModalEditar(device) {
      this.modal = {
        show: true,
        type: 'editar',
        data: { ...device, nombreEdit: device.name, roomEdit: device.room }
      };
      this.$nextTick(() => lucide.createIcons());
    },

    abrirModalVincular() {
      this.modal = { show: true, type: 'vincular', data: { codigo: null, expira: null, cargando: false } };
      this.generarCodigo();
      this.$nextTick(() => lucide.createIcons());
    },

    abrirModalRegla() {
      this.modal = {
        show: true,
        type: 'regla',
        data: {
          nombre:      '',
          sensor_id:   null,
          operador:    '>',
          umbral:      0,
          actuador_id: null,
          accion:      'on',
        }
      };
      this.$nextTick(() => lucide.createIcons());
    },

    abrirModalEscena() {
      this.modal = {
        show: true,
        type: 'escena',
        data: {
          nombre:      '',
          disparador:  'manual',
          actuador_id: null,
          accion:      'on',
        }
      };
      this.$nextTick(() => lucide.createIcons());
    },

    cerrarModal() {
      this.modal = { show: false, type: null, data: {} };
    },

    async guardarEdicion() {
      const { id, category, nombreEdit, roomEdit } = this.modal.data;
      try {
        if (category === 'sensor') {
          await globalStore.editarSensor(id, nombreEdit);
        } else {
          await globalStore.editarActuador(id, nombreEdit);
        }
        if (roomEdit) {
          const item     = globalStore.dashboard.find(d => d.id === id && d.category === category);
          const dispId   = item?.dispositivo_id;
          if (dispId) await globalStore.editarDispositivo(dispId, { ubicacion: roomEdit });
        }
        this.cerrarModal();
        this.notify('Cambios guardados');
      } catch (e) {
        this.notify('Error al guardar cambios', 'error');
      }
    },

    async guardarRegla() {
      try {
        await globalStore.crearRegla(this.modal.data);
        this.cerrarModal();
        this.notify('Regla creada');
      } catch (e) {
        this.notify('Error al crear regla', 'error');
      }
    },

    async guardarEscena() {
      try {
        await globalStore.crearEscena(this.modal.data);
        this.cerrarModal();
        this.notify('Escena creada');
      } catch (e) {
        this.notify('Error al crear escena', 'error');
      }
    },

    abrirModalCamara(device) {
      this.modal = { show: true, type: 'camara', data: { ...device } };
      this.$nextTick(() => lucide.createIcons());
    },

    cerrarModalCamara() {
      this.modal = { show: false, type: null, data: {} };
    },

    // ── Vinculación ─────────────────────────────────────────────────────────────

    async generarCodigo() {
      this.modal.data.cargando = true;
      try {
        const res              = await globalStore.generarCodigo();
        this.modal.data.codigo = res.codigo;
        this.modal.data.expira = res.expira_en;
      } catch (e) {
        this.notify('Error al generar código', 'error');
      } finally {
        this.modal.data.cargando = false;
      }
    },

    // ── Login ──────────────────────────────────────────────────────────
    async logout() {
      await fetch('/auth/logout', { method: 'POST' });
      window.location.href = '/app/login.html';
    },

    // ── Sistema ─────────────────────────────────────────────────────────────────

    fetchSystem() { globalStore.fetchSystem(); },
    pct(s)        { return globalStore.pct(s); },
    sdUsedPct()   { return globalStore.sdUsedPct(); },

    // ── Toast ───────────────────────────────────────────────────────────────────

    notify(message, type = 'info') {
      this.toast = { show: true, message, type };
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => this.toast.show = false, 2500);
    },
  };
}