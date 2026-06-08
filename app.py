import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date

st.set_page_config(page_title="CBC", page_icon="📊", layout="wide")

DB = "postgresql://neondb_owner:npg_0QazKFN8logm@ep-sweet-block-aq1035ng-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"

FONDOS = {"1 - Efectivo $": 1, "2 - Efectivo Ale": 2, "3 - Santander": 3, "4 - Mercado Pago": 4, "5 - FCI": 5, "6 - Cheques": 6}

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

def get_titulares():
    df = query("SELECT id, nombre FROM titulares ORDER BY nombre")
    return dict(zip(df['nombre'], df['id']))

def get_tipos_comprobante():
    df = query("SELECT id, descripcion FROM tipos_comprobante WHERE activo=true ORDER BY id")
    return dict(zip(df['descripcion'], df['id']))

def get_ultimos(limit=20):
    return query(f"SELECT fecha, id_titular, detalle, importe FROM cashflow ORDER BY fecha DESC LIMIT {limit}")

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
        "Balance"
    ])
    st.caption("Neon PostgreSQL")

st.title("CBC Sistema Contable")

if pantalla == "Dashboard":
    try:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Cuentas", query("SELECT COUNT(*) as n FROM plan_de_cuentas").iloc[0]['n'])
        c2.metric("Titulares", query("SELECT COUNT(*) as n FROM titulares").iloc[0]['n'])
        c3.metric("Movimientos", query("SELECT COUNT(*) as n FROM cashflow").iloc[0]['n'])
        c4.metric("Comprobantes", query("SELECT COUNT(*) as n FROM operaciones").iloc[0]['n'])
        st.dataframe(get_ultimos(10), use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error: {e}")

elif pantalla == "Cargar Movimiento":
    modo = st.radio("Modo", ["Formulario", "Pantalla completa"], horizontal=True)
    titulares = get_titulares()
    if modo == "Formulario":
        with st.form("form"):
            col1, col2 = st.columns(2)
            fecha = col1.date_input("Fecha", value=date.today())
            fondo = col2.selectbox("Fondo", list(FONDOS.keys()))
            titular = st.selectbox("Titular", list(titulares.keys()))
            concepto = st.text_input("Concepto")
            col3, col4 = st.columns(2)
            importe = col3.number_input("Importe (negativo=egreso)", value=0.0, step=100.0)
            cuenta = col4.text_input("Cuenta contable")
            if st.form_submit_button("Guardar"):
                if not concepto:
                    st.error("Falta el concepto.")
                else:
                    try:
                        execute("INSERT INTO cashflow (mes,fecha,id_titular,cod_cuenta,detalle,importe) VALUES (%s,%s,%s,%s,%s,%s)", (fecha.month, fecha, titulares[titular], cuenta, concepto, importe))
                        st.success(f"Guardado: {concepto} | ${importe:,.2f}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        try:
            total = float(query("SELECT COALESCE(SUM(importe),0) as t FROM cashflow").iloc[0]['t'])
            c1,c2 = st.columns(2)
            c1.metric("Total", f"${total:,.2f}")
            c2.metric("Movimientos", query("SELECT COUNT(*) as n FROM cashflow").iloc[0]['n'])
        except Exception as e:
            st.warning(f"{e}")
        col_form, col_tabla = st.columns([1, 2])
        with col_form:
            fecha = st.date_input("Fecha", value=date.today(), key="f")
            fondo = st.selectbox("Fondo", list(FONDOS.keys()), key="fo")
            titular = st.selectbox("Titular", list(titulares.keys()), key="t")
            concepto = st.text_input("Concepto", key="c")
            importe = st.number_input("Importe", value=0.0, step=100.0, key="i")
            cuenta = st.text_input("Cuenta", key="cu")
            if st.button("Guardar", use_container_width=True):
                if not concepto:
                    st.error("Falta concepto.")
                else:
                    try:
                        execute("INSERT INTO cashflow (mes,fecha,id_titular,cod_cuenta,detalle,importe) VALUES (%s,%s,%s,%s,%s,%s)", (fecha.month, fecha, titulares[titular], cuenta, concepto, importe))
                        st.success(f"OK: ${importe:,.2f}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        with col_tabla:
            try:
                st.dataframe(get_ultimos(15), use_container_width=True, hide_index=True, height=450)
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
                    execute("""
                        INSERT INTO operaciones (fecha, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (fecha, titulares[titular], tipos[tipo], nro, descripcion, importe, fecha.month))
                    st.success(f"Comprobante guardado: {descripcion} | ${importe:,.2f}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    st.markdown("---")
    st.subheader("Ultimos comprobantes")
    try:
        df = query("""
            SELECT o.fecha, t.nombre Titular, tc.descripcion Tipo, o.numero_comprobante Numero,
                   o.descripcion Concepto, o.importe Importe,
                   CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END Estado
            FROM operaciones o
            LEFT JOIN titulares t ON o.id_titular = t.id
            LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id
            ORDER BY o.fecha DESC LIMIT 50
        """)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400)
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Gestion de Saldos":
    st.subheader("Facturas impagas")
    titulares = get_titulares()
    col1, col2 = st.columns(2)
    filtro_titular = col1.selectbox("Titular", ["Todos"] + list(titulares.keys()))
    filtro_tipo = col2.selectbox("Estado", ["IMPAGO", "PAGO", "Todos"])
    where = []
    if filtro_tipo == "IMPAGO": where.append("o.id_pago IS NULL")
    elif filtro_tipo == "PAGO": where.append("o.id_pago IS NOT NULL")
    if filtro_titular != "Todos":
        where.append(f"o.id_titular = '{titulares[filtro_titular]}'")
    sql = """
        SELECT o.id, o.fecha, t.nombre Titular, tc.descripcion Tipo,
               o.numero_comprobante Numero, o.descripcion Concepto,
               o.importe Importe,
               CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END Estado
        FROM operaciones o
        LEFT JOIN titulares t ON o.id_titular = t.id
        LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id
    """
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY o.fecha DESC LIMIT 200"
    try:
        df = query(sql)
        if df.empty:
            st.info("No hay comprobantes.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)
            st.metric("Total", f"${df['Importe'].sum():,.2f}")
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Cuenta Corriente":
    st.subheader("Cuenta Corriente por Titular")
    titulares = get_titulares()
    titular = st.selectbox("Seleccionar titular", list(titulares.keys()))
    id_titular = titulares[titular]
    try:
        df = query(f"""
            SELECT
                o.fecha,
                tc.descripcion Tipo,
                o.numero_comprobante Numero,
                o.descripcion Concepto,
                o.importe Debe,
                CASE WHEN o.id_pago IS NOT NULL THEN o.importe ELSE 0 END Haber,
                CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END Estado
            FROM operaciones o
            LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id
            WHERE o.id_titular = '{id_titular}'
            ORDER BY o.fecha ASC
        """)
        if df.empty:
            st.info(f"Sin movimientos para {titular}.")
        else:
            df['Saldo'] = (df['Debe'] - df['Haber']).cumsum()
            st.dataframe(df, use_container_width=True, hide_index=True, height=500)
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
    if tipo != "Todos": where.append(f"niv1_desc='{tipo}'")
    if buscar: where.append(f"nombre ILIKE '%{buscar}%'")
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY niv1,niv2,niv3,niv4,niv5"
    try:
        st.dataframe(query(sql), use_container_width=True, hide_index=True, height=550)
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Titulares":
    buscar = st.text_input("Buscar")
    sql = "SELECT id, nivel1 Tipo, nombre FROM titulares"
    if buscar: sql += f" WHERE nombre ILIKE '%{buscar}%'"
    sql += " ORDER BY nivel1, nombre"
    try:
        st.dataframe(query(sql), use_container_width=True, hide_index=True, height=550)
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "CashFlow":
    col1, col2, col3 = st.columns(3)
    mes = col1.selectbox("Mes", ["Todos","1","2","3","4","5","6","7","8","9","10","11","12"])
    buscar = col2.text_input("Buscar")
    cronologico = col3.checkbox("Orden cronologico (mas antiguo primero)")
    where = []
    if mes != "Todos": where.append(f"mes={mes}")
    if buscar: where.append(f"detalle ILIKE '%{buscar}%'")
    sql = "SELECT fecha, id_titular, cod_cuenta, detalle, importe FROM cashflow"
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " OR
