function hub() {
    return {
        online: false,
        sistema: {},
        dispositivos: [],
        lecturas_recientes: [],
        historial: [],
        automatizaciones: [],
        mostrarFormAuto: false,
        nuevaAuto: {
            nombre: '',
            condicion_tipo: 'temperatura_mayor',
            condicion_valor: '',
            condicion_ubicacion: '',
            accion_actuador_id: '',
            accion_estado: 'encendido',
        },

        get cpuAlerta() {
            const temp = parseFloat(this.sistema.cpu_temperatura);
            return !isNaN(temp) && temp >= 70;
        },

        async init() {
            await this.cargarTodo();
            setInterval(() => this.cargarTodo(), 30000);
        },

        async cargarTodo() {
            await Promise.all([
                this.cargarSistema(),
                this.cargarDispositivos(),
                this.cargarSensores(),
                this.cargarAutomatizaciones(),
            ]);
        },

        async cargarSistema() {
            try {
                const r = await fetch('/ui/sistema');
                if (!r.ok) throw new Error();
                this.sistema = await r.json();
                this.online = true;
            } catch {
                this.online = false;
            }
        },

        async cargarDispositivos() {
            try {
                const r = await fetch('/ui/dispositivos');
                if (!r.ok) return;
                this.dispositivos = await r.json();
            } catch {}
        },

        async cargarSensores() {
            try {
                const r = await fetch('/ui/sensores/recientes');
                if (!r.ok) return;
                const data = await r.json();
                this.lecturas_recientes = data.recientes;
                this.historial = data.historial;
            } catch {}
        },

        async cargarAutomatizaciones() {
            try {
                const r = await fetch('/ui/automatizaciones');
                if (!r.ok) return;
                this.automatizaciones = await r.json();
            } catch {}
        },

        async toggleActuador(actuador) {
            const nuevoEstado = actuador.estado === 'encendido' ? 'apagado' : 'encendido';
            try {
                const r = await fetch(`/ui/actuadores/${actuador.id}/estado`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ estado: nuevoEstado }),
                });
                if (r.ok) actuador.estado = nuevoEstado;
            } catch {}
        },

        async toggleAuto(auto) {
            try {
                const r = await fetch(`/ui/automatizaciones/${auto.id}/toggle`, { method: 'PUT' });
                if (r.ok) auto.activa = !auto.activa;
            } catch {}
        },

        async eliminarAuto(id) {
            if (!confirm('¿Eliminar esta automatización?')) return;
            try {
                const r = await fetch(`/ui/automatizaciones/${id}`, { method: 'DELETE' });
                if (r.ok) this.automatizaciones = this.automatizaciones.filter(a => a.id !== id);
            } catch {}
        },

        async crearAutomatizacion() {
            const { nombre, condicion_valor, accion_actuador_id, condicion_ubicacion } = this.nuevaAuto;
            if (!nombre || !condicion_valor || !accion_actuador_id || !condicion_ubicacion) return;
            try {
                const r = await fetch('/ui/automatizaciones', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ...this.nuevaAuto,
                        condicion_valor: parseFloat(this.nuevaAuto.condicion_valor),
                        accion_actuador_id: parseInt(this.nuevaAuto.accion_actuador_id),
                    }),
                });
                if (r.ok) {
                    await this.cargarAutomatizaciones();
                    this.mostrarFormAuto = false;
                    this.nuevaAuto = {
                        nombre: '',
                        condicion_tipo: 'temperatura_mayor',
                        condicion_valor: '',
                        condicion_ubicacion: '',
                        accion_actuador_id: '',
                        accion_estado: 'encendido',
                    };
                }
            } catch {}
        },

        describirAuto(auto) {
            const labels = {
                temperatura_mayor: 'Temp >',
                temperatura_menor: 'Temp <',
                humedad_mayor: 'Humedad >',
                humedad_menor: 'Humedad <',
            };
            const unidad = auto.condicion_tipo.startsWith('temperatura') ? '°C' : '%';
            const cond = labels[auto.condicion_tipo] || auto.condicion_tipo;
            return `Si ${cond} ${auto.condicion_valor}${unidad} en ${auto.condicion_ubicacion} → ${auto.accion_estado}`;
        },

        formatFecha(fecha) {
            if (!fecha) return '';
            try {
                return new Date(fecha).toLocaleString('es', { dateStyle: 'short', timeStyle: 'short' });
            } catch {
                return fecha;
            }
        },
    };
}
