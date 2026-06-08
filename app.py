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

def get_ultimos(limit=20):
    return query(f"SELECT fecha, id_titular, detalle, importe FROM cashflow ORDER BY fecha DESC LIMIT {limit}")

with st.sidebar:
    st.markdown("### CBC Sistema Contable")
    pantalla = st.radio("Menu", ["Dashboard", "Cargar Movimiento", "Plan de Cuentas", "Titulares", "CashFlow", "Balance"])
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
    sql += " ORDER BY fecha ASC LIMIT 500" if cronologico else " ORDER BY fecha DESC LIMIT 500"
    try:
        df = query(sql)
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)
        st.metric("Total", f"${df['importe'].sum():,.2f}")
    except Exception as e:
        st.error(f"{e}")

elif pantalla == "Balance":
    mes = st.selectbox("Mes", ["Todos","1-Enero","2-Febrero","3-Marzo","4-Abril","5-Mayo","6-Junio","7-Julio","8-Agosto","9-Septiembre","10-Octubre","11-Noviembre","12-Diciembre"])
    mes_num = None if mes == "Todos" else int(mes.split("-")[0])
    try:
        where_mes = f"AND EXTRACT(MONTH FROM c.fecha)={mes_num}" if mes_num else ""
        df = query(f"""
            SELECT p.niv2_desc Subtipo, p.nombre Cuenta, COALESCE(SUM(c.importe),0) Importe
            FROM plan_de_cuentas p
            LEFT JOIN cashflow c ON c.detalle=p.nombre {where_mes}
            WHERE p.niv1=1
            GROUP BY p.niv2_desc,p.nombre,p.niv1,p.niv2,p.niv3,p.niv4,p.niv5
            HAVING COALESCE(SUM(c.importe),0)<>0
            ORDER BY p.niv1,p.niv2,p.niv3,p.niv4,p.niv5
        """)
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
