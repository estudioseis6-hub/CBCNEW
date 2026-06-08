import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date

st.set_page_config(page_title="CBC", page_icon="📊", layout="wide")

DB = "postgresql://neondb_owner:npg_0QazKFN8logm@ep-sweet-block-aq1035ng-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_conn():
    return psycopg2.connect(DB, cursor_factory=RealDictCursor)

def query(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return pd.DataFrame(cur.fetchall())
    finally:
        conn.close()

def execute(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()

def fmt_fecha(df):
    for col in ['fecha', 'Fecha']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.strftime('%a %d %b %Y').str.title()
    return df

def get_titulares():
    df = query("SELECT id, nombre FROM titulares ORDER BY nombre")
    return dict(zip(df['nombre'], df['id']))

def get_titulares_movimiento():
    df = query("SELECT id, nombre FROM titulares WHERE nivel1 = 'SISTEMA' ORDER BY nombre")
    df2 = query("SELECT id, nombre FROM titulares WHERE nivel1 != 'SISTEMA' ORDER BY nombre")
    df_all = pd.concat([df, df2], ignore_index=True)
    return dict(zip(df_all['nombre'], df_all['id']))

def get_tipos_comprobante():
    df = query("SELECT id, descripcion FROM tipos_comprobante WHERE activo=true ORDER BY id")
    return dict(zip(df['descripcion'], df['id']))

def get_fondos():
    df = query("SELECT id, nombre FROM fondos WHERE activo=true ORDER BY id")
    return dict(zip(df['nombre'], df['id']))

def get_fondos_completo():
    return query("SELECT id, nombre, tipo, saldo_inicial, permite_negativo FROM fondos WHERE activo=true ORDER BY id")

def get_cuentas():
    df = query("SELECT nombre FROM plan_de_cuentas ORDER BY niv1,niv2,niv3,niv4,niv5")
    return df['nombre'].tolist()

def get_saldo_fondo(id_fondo):
    r = query(f"""
        SELECT f.saldo_inicial, COALESCE(SUM(c.importe),0) as movimientos
        FROM fondos f
        LEFT JOIN cashflow c ON c.id_fondo = f.id
        WHERE f.id = {id_fondo}
        GROUP BY f.saldo_inicial
    """)
    if r.empty:
        return 0.0
    return float(r.iloc[0]['saldo_inicial']) + float(r.iloc[0]['movimientos'])

def get_ultimos(limit=20):
    return query(f"SELECT fecha, id_titular, cod_cuenta, detalle, importe FROM cashflow ORDER BY fecha DESC LIMIT {limit}")

def mostrar_saldos_fondos():
    try:
        saldos = query("""
            SELECT f.id, f.nombre, f.saldo_inicial, COALESCE(SUM(c.importe),0) as movimientos
            FROM fondos f
            LEFT JOIN cashflow c ON c.id_fondo = f.id
            WHERE f.activo = true
            GROUP BY f.id, f.nombre, f.saldo_inicial
            ORDER BY f.id
        """)
        if not saldos.empty:
            cols = st.columns(len(saldos))
            for i, row in saldos.iterrows():
                saldo = float(row['saldo_inicial']) + float(row['movimientos'])
                cols[i].metric(row['nombre'], f"${saldo:,.2f}")
    except Exception as e:
        st.error(f"{e}")

with st.sidebar:
    st.markdown("### CBC Sistema Contable")
    pantalla = st.radio("Menu", [
        "Dashboard",
        "Cargar Movimiento",
        "Cargar Comprobante",
        "Gestion de Saldos",
        "Cuenta Corriente",
        "Plan de Cuentas",
        "Titulares",
        "CashFlow",
        "Balance",
        "── Config ──",
        "Fondos",
    ])
    st.caption("Neon PostgreSQL")

titulos = {
    "Dashboard": "Dashboard",
    "Cargar Movimiento": "Cargar Movimiento",
    "Cargar Comprobante": "Cargar Comprobante",
    "Gestion de Saldos": "Gestión de Saldos",
    "Cuenta Corriente": "Cuenta Corriente",
    "Plan de Cuentas": "Plan de Cuentas",
    "Titulares": "Titulares",
    "CashFlow": "Tesorería",
    "Balance": "Balance",
    "── Config ──": "Configuración",
    "Fondos": "Configuración — Fondos",
}
st.title(titulos.get(pantalla, "CBC"))

if pantalla == "Dashboard":
    try:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Cuentas", query("SELECT COUNT(*) as n FROM plan_de_cuentas").iloc[0]['n'])
        c2.metric("Titulares", query("SELECT COUNT(*) as n FROM titulares").iloc[0]['n'])
        c3.metric("Movimientos", query("SELECT COUNT(*) as n FROM cashflow").iloc[0]['n'])
        c4.metric("Comprobantes", query("SELECT COUNT(*) as n FROM operaciones").iloc[0]['n'])
        st.dataframe(fmt_fecha(get_ultimos(10)), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error: {e}")

elif pantalla == "Cargar Movimiento":
    titulares = get_titulares_movimiento()
    fondos = get_fondos()
    fondos_completo = get_fondos_completo()
    cuentas = get_cuentas()

    def guardar_movimiento(fecha, fondo_nombre, titular_nombre, concepto, importe, cuenta):
        id_fondo = fondos[fondo_nombre]
        id_titular = titulares[titular_nombre]
        fila_fondo = fondos_completo[fondos_completo['id'] == id_fondo].iloc[0]
        if not fila_fondo['permite_negativo']:
            saldo_actual = get_saldo_fondo(id_fondo)
            if saldo_actual + importe < 0:
                st.error(f"Saldo insuficiente en {fondo_nombre}. Saldo actual: ${saldo_actual:,.2f}")
                return False
        execute("INSERT INTO cashflow (mes,fecha,id_titular,cod_cuenta,detalle,importe,id_fondo) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (fecha.month, fecha, id_titular, cuenta, concepto, importe, id_fondo))
        return True

    modo = st.radio("Modo", ["Formulario", "Pantalla completa"], horizontal=True)

    if modo == "Formulario":
        with st.form("form"):
            col1, col2 = st.columns(2)
            fecha = col1.date_input("Fecha", value=date.today())
            fondo = col2.selectbox("Fondo", list(fondos.keys()))
            titular = st.selectbox("Titular", list(titulares.keys()))
            concepto = st.text_input("Concepto")
            col3, col4 = st.columns(2)
            importe = col3.number_input("Importe (negativo=egreso)", value=0.0, step=100.0)
            cuenta = col4.selectbox("Cuenta contable", cuentas)
            if st.form_submit_button("Guardar"):
                if not concepto:
                    st.error("Falta el concepto.")
                else:
                    if guardar_movimiento(fecha, fondo, titular, concepto, importe, cuenta):
                        st.success(f"Guardado: {concepto} | ${importe:,.2f}")
                        st.rerun()

    else:
        st.subheader("Saldos actuales")
        mostrar_saldos_fondos()
        st.markdown("---")
        col_form, col_tabla = st.columns([1, 2])
        with col_form:
            fecha = st.date_input("Fecha", value=date.today(), key="f")
            fondo = st.selectbox("Fondo", list(fondos.keys()), key="fo")
            titular = st.selectbox("Titular", list(titulares.keys()), key="t")
            concepto = st.text_input("Concepto", key="c")
            importe = st.number_input("Importe (negativo=egreso)", value=0.0, step=100.0, key="i")
            cuenta = st.selectbox("Cuenta", cuentas, key="cu")
            if st.button("Guardar", use_container_width=True):
                if not concepto:
                    st.error("Falta concepto.")
                else:
                    if guardar_movimiento(fecha, fondo, titular, concepto, importe, cuenta):
                        st.success(f"OK: ${importe:,.2f}")
                        st.rerun()
        with col_tabla:
            try:
                st.dataframe(fmt_fecha(get_ultimos(15)), use_container_width=True, hide_index=True, height=450)
            except Exception as e:
                st.error(f"{e}")

elif pantalla == "Cargar Comprobante":
    st.subheader("Nuevo comprobante")
    titulares = get_titulares()
    tipos = get_tipos_comprobante()
    with st.form("form_comp"):
        col1, col2, col3 = st.columns(3)
        fecha = col1.date_input("Fecha", value=date.today())
        tipo = col2.selectbox("Tipo comprobante", list(tipos.keys()))
        nro = col3.text_input("Numero comprobante")
        titular = st.selectbox("Titular", list(titulares.keys()))
        descripcion = st.text_input("Descripcion")
        col4, col5 = st.columns(2)
        importe = col4.number_input("Importe", value=0.0, step=100.0)
        if st.form_submit_button("Guardar comprobante", use_container_width=True):
            if not descripcion:
                st.error("Falta la descripcion.")
            else:
                try:
                    execute("INSERT INTO operaciones (fecha, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (fecha, titulares[titular], tipos[tipo], nro, descripcion, importe, fecha.month))
                    st.success(f"Comprobante guardado: {descripcion} | ${importe:,.2f}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    st.markdown("---")
    st.subheader("Ultimos comprobantes")
    try:
        df = query("SELECT o.fecha, t.nombre Titular, tc.descripcion Tipo, o.numero_comprobante Numero, o.descripcion Concepto, o.importe Importe, CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END Estado FROM operaciones o LEFT JOIN titulares t ON o.id_titular = t.id LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id ORDER BY o.fecha DESC LIMIT 50")
        st.dataframe(fmt_fecha(df), use_container_width=True, hide_index=True, height=400)
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Gestion de Saldos":
    st.subheader("Comprobantes")
    titulares = get_titulares()
    col1, col2 = st.columns(2)
    filtro_titular = col1.selectbox("Titular", ["Todos"] + list(titulares.keys()))
    filtro_tipo = col2.selectbox("Estado", ["IMPAGO", "PAGO", "Todos"])
    where = []
    if filtro_tipo == "IMPAGO":
        where.append("o.id_pago IS NULL")
    elif filtro_tipo == "PAGO":
        where.append("o.id_pago IS NOT NULL")
    if filtro_titular != "Todos":
        tid = titulares[filtro_titular]
        where.append(f"o.id_titular = '{tid}'")
    sql = "SELECT o.id, o.fecha, t.nombre Titular, tc.descripcion Tipo, o.numero_comprobante Numero, o.descripcion Concepto, o.importe Importe, CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END Estado FROM operaciones o LEFT JOIN titulares t ON o.id_titular = t.id LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.fecha DESC LIMIT 200"
    try:
        df = query(sql)
        if df.empty:
            st.info("No hay comprobantes.")
        else:
            st.dataframe(fmt_fecha(df), use_container_width=True, hide_index=True, height=500)
            st.metric("Total", f"${df['Importe'].sum():,.2f}")
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Cuenta Corriente":
    st.subheader("Cuenta Corriente por Titular")
    titulares = get_titulares()
    titular = st.selectbox("Seleccionar titular", list(titulares.keys()))
    id_titular = titulares[titular]
    try:
        df = query(f"SELECT o.fecha, tc.descripcion AS \"Tipo\", o.numero_comprobante AS \"Numero\", o.descripcion AS \"Concepto\", o.importe::float AS \"Debe\", CASE WHEN o.id_pago IS NOT NULL THEN o.importe::float ELSE 0 END AS \"Haber\", CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END AS \"Estado\" FROM operaciones o LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id WHERE o.id_titular = '{id_titular}' ORDER BY o.fecha ASC")
        if df.empty:
            st.info(f"Sin movimientos para {titular}.")
        else:
            df['Debe'] = pd.to_numeric(df['Debe'], errors='coerce').fillna(0)
            df['Haber'] = pd.to_numeric(df['Haber'], errors='coerce').fillna(0)
            df['Saldo'] = (df['Debe'] - df['Haber']).cumsum()
            st.dataframe(fmt_fecha(df), use_container_width=True, hide_index=True, height=500)
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Facturado", f"${df['Debe'].sum():,.2f}")
            col2.metric("Total Pagado", f"${df['Haber'].sum():,.2f}")
            col3.metric("Saldo Pendiente", f"${df['Saldo'].iloc[-1]:,.2f}")
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Plan de Cuentas":
    col1, col2 = st.columns(2)
    tipo = col1.selectbox("Tipo", ["Todos","Resultados","Patrimonial","Movimiento"])
    buscar = col2.text_input("Buscar")
    sql = "SELECT niv1_desc Tipo, niv2_desc Subtipo, nombre Cuenta, signo Signo FROM plan_de_cuentas"
    where = []
    if tipo != "Todos":
        where.append(f"niv1_desc='{tipo}'")
    if buscar:
        where.append(f"nombre ILIKE '%{buscar}%'")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY niv1,niv2,niv3,niv4,niv5"
    try:
        st.dataframe(query(sql), use_container_width=True, hide_index=True, height=550)
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Titulares":
    buscar = st.text_input("Buscar")
    sql = "SELECT id, nivel1 Tipo, nombre FROM titulares"
    if buscar:
        sql += f" WHERE nombre ILIKE '%{buscar}%'"
    sql += " ORDER BY nivel1, nombre"
    try:
        st.dataframe(query(sql), use_container_width=True, hide_index=True, height=550)
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "CashFlow":
    st.subheader("Saldos por Fondo")

    # Saldos por fondo con click para filtrar
    try:
        saldos = query("""
            SELECT f.id, f.nombre, f.tipo, f.saldo_inicial, COALESCE(SUM(c.importe),0) as movimientos
            FROM fondos f
            LEFT JOIN cashflow c ON c.id_fondo = f.id
            WHERE f.activo = true
            GROUP BY f.id, f.nombre, f.tipo, f.saldo_inicial
            ORDER BY f.id
        """)

        if not saldos.empty:
            # Total libre disponibilidad
            tipos_libres = ['Efectivo', 'Banco', 'Billetera Digital']
            total_libre = sum(
                float(row['saldo_inicial']) + float(row['movimientos'])
                for _, row in saldos.iterrows()
                if row['tipo'] in tipos_libres
            )

            # Mostrar fondos como botones
            cols = st.columns(len(saldos) + 1)
            fondo_seleccionado = st.session_state.get('fondo_cf', 'Todos')

            for i, (_, row) in enumerate(saldos.iterrows()):
                saldo = float(row['saldo_inicial']) + float(row['movimientos'])
                label = f"{row['nombre']}\n${saldo:,.2f}"
                if cols[i].button(label, use_container_width=True, key=f"btn_fondo_{row['id']}"):
                    if fondo_seleccionado == row['nombre']:
                        st.session_state['fondo_cf'] = 'Todos'
                    else:
                        st.session_state['fondo_cf'] = row['nombre']
                    st.rerun()

            # Total libre disponibilidad al final
            cols[-1].metric("💰 Libre disponibilidad", f"${total_libre:,.2f}")

            fondo_seleccionado = st.session_state.get('fondo_cf', 'Todos')
            if fondo_seleccionado != 'Todos':
                st.info(f"Filtrando: {fondo_seleccionado} — hacé click de nuevo para ver todos")

    except Exception as e:
        st.error(f"{e}")

    st.markdown("---")

    fondos = get_fondos()
    col1, col2 = st.columns(2)
    mes = col1.selectbox("Mes", ["Todos","1","2","3","4","5","6","7","8","9","10","11","12"])
    cronologico = col2.checkbox("Orden cronologico (mas antiguo primero)")

    fondo_seleccionado = st.session_state.get('fondo_cf', 'Todos')

    where = []
    if mes != "Todos":
        where.append(f"c.mes={mes}")
    if fondo_seleccionado != 'Todos':
        id_fondo_sel = fondos.get(fondo_seleccionado)
        if id_fondo_sel:
            where.append(f"c.id_fondo={id_fondo_sel}")

    sql = """
        SELECT
            c.fecha AS "Fecha",
            COALESCE(t.nombre, c.id_titular::text) AS "Titular",
            f.nombre AS "Fondo",
            c.detalle AS "Detalle",
            c.importe AS "Importe"
        FROM cashflow c
        LEFT JOIN titulares t ON c.id_titular = t.id
        LEFT JOIN fondos f ON c.id_fondo = f.id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY c.fecha " + ("ASC" if cronologico else "DESC") + " LIMIT 500"

    try:
        df = query(sql)
        if df.empty:
            st.info("Sin movimientos.")
        else:
            df['Importe'] = pd.to_numeric(df['Importe'], errors='coerce').fillna(0)
            if fondo_seleccionado != 'Todos':
                df_asc = df.iloc[::-1].copy() if not cronologico else df.copy()
                df_asc['Saldo'] = df_asc['Importe'].cumsum()
                df = df_asc.iloc[::-1].copy() if not cronologico else df_asc
            st.dataframe(fmt_fecha(df), use_container_width=True, hide_index=True, height=500)
            col1, col2 = st.columns(2)
            col1.metric("Movimientos", len(df))
            col2.metric("Total periodo", f"${df['Importe'].sum():,.2f}")
    except Exception as e:
        st.error(f"{e}")
elif pantalla == "Balance":
    mes = st.selectbox("Mes", ["Todos","1-Enero","2-Febrero","3-Marzo","4-Abril","5-Mayo","6-Junio","7-Julio","8-Agosto","9-Septiembre","10-Octubre","11-Noviembre","12-Diciembre"])
    mes_num = None if mes == "Todos" else int(mes.split("-")[0])
    try:
        where_mes = f"AND EXTRACT(MONTH FROM c.fecha)={mes_num}" if mes_num else ""
        df = query(f"SELECT p.niv2_desc Subtipo, p.nombre Cuenta, COALESCE(SUM(c.importe),0) Importe FROM plan_de_cuentas p LEFT JOIN cashflow c ON c.detalle=p.nombre {where_mes} WHERE p.niv1=1 GROUP BY p.niv2_desc,p.nombre,p.niv1,p.niv2,p.niv3,p.niv4,p.niv5 HAVING COALESCE(SUM(c.importe),0)<>0 ORDER BY p.niv1,p.niv2,p.niv3,p.niv4,p.niv5")
        if df.empty:
            st.info("Sin datos.")
        else:
            for sub in df["Subtipo"].unique():
                st.markdown(f"**{sub}**")
                s = df[df["Subtipo"]==sub][["Cuenta","Importe"]]
                st.dataframe(s, use_container_width=True, hide_index=True)
                st.markdown(f"Total: **${s['Importe'].sum():,.2f}**")
            st.metric("Resultado Neto", f"${df['Importe'].sum():,.2f}")
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "── Config ──":
    st.info("Seleccioná una opción de configuración del menu.")

elif pantalla == "Fondos":
    st.subheader("Configuracion de Fondos")
    TIPOS_FONDO = ["Efectivo", "Banco", "Billetera Digital", "Cheques", "Inversión"]
    MONEDAS = ["ARS", "USD", "EUR"]

    try:
        df = query("SELECT id, nombre, tipo, moneda, saldo_inicial, activo, es_sistema FROM fondos ORDER BY id")
        st.dataframe(df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"{e}")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Agregar fondo**")
        with st.form("nuevo_fondo"):
            nombre = st.text_input("Nombre")
            tipo = st.selectbox("Tipo", TIPOS_FONDO)
            moneda = st.selectbox("Moneda", MONEDAS)
            saldo_inicial = st.number_input("Saldo inicial", value=0.0, step=100.0)
            if st.form_submit_button("Agregar"):
                if not nombre:
                    st.error("Falta el nombre.")
                else:
                    try:
                        execute("INSERT INTO fondos (nombre, tipo, moneda, saldo_inicial, es_sistema) VALUES (%s, %s, %s, %s, false)",
                                (nombre, tipo, moneda, saldo_inicial))
                        st.success(f"Fondo '{nombre}' agregado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"{e}")

    with col2:
        st.markdown("**Editar fondo propio / desactivar**")
        try:
            df_fondos = query("SELECT id, nombre, es_sistema FROM fondos ORDER BY id")
            df_usuario = df_fondos[df_fondos['es_sistema'] == False]
            if df_usuario.empty:
                st.info("No tenés fondos propios agregados todavía.")
            else:
                fondo_sel = st.selectbox("Fondo", df_usuario['nombre'].tolist())
                id_sel = int(df_usuario[df_usuario['nombre'] == fondo_sel]['id'].iloc[0])
                fila = query(f"SELECT * FROM fondos WHERE id={id_sel}").iloc[0]
                nuevo_nombre = st.text_input("Nuevo nombre", value=fila['nombre'])
                nuevo_tipo = st.selectbox("Tipo", TIPOS_FONDO, index=TIPOS_FONDO.index(fila['tipo']) if fila['tipo'] in TIPOS_FONDO else 0)
                nueva_moneda = st.selectbox("Moneda", MONEDAS, index=MONEDAS.index(fila['moneda']) if fila['moneda'] in MONEDAS else 0)
                nuevo_saldo_inicial = st.number_input("Saldo inicial", value=float(fila['saldo_inicial']), step=100.0)
                activo = st.checkbox("Activo", value=bool(fila['activo']))
                if st.button("Guardar cambios"):
                    execute("UPDATE fondos SET nombre=%s, tipo=%s, moneda=%s, saldo_inicial=%s, activo=%s WHERE id=%s",
                            (nuevo_nombre, nuevo_tipo, nueva_moneda, nuevo_saldo_inicial, activo, id_sel))
                    st.success("Actualizado.")
                    st.rerun()
        except Exception as e:
            st.error(f"{e}")

    st.markdown("---")
    st.markdown("**Configurar saldo inicial de fondos del sistema**")
    try:
        df_sistema = query("SELECT id, nombre, saldo_inicial FROM fondos WHERE es_sistema = true ORDER BY id")
        fondo_sis = st.selectbox("Fondo del sistema", df_sistema['nombre'].tolist(), key="sis")
        id_sis = int(df_sistema[df_sistema['nombre'] == fondo_sis]['id'].iloc[0])
        saldo_actual = float(df_sistema[df_sistema['id'] == id_sis]['saldo_inicial'].iloc[0])
        nuevo_saldo = st.number_input("Saldo inicial", value=saldo_actual, step=100.0, key="saldo_sis")
        if st.button("Guardar saldo inicial"):
            execute("UPDATE fondos SET saldo_inicial=%s WHERE id=%s", (nuevo_saldo, id_sis))
            st.success("Saldo inicial actualizado.")
            st.rerun()
    except Exception as e:
        st.error(f"{e}")
