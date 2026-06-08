elif pantalla == "CashFlow":
    col1, col2, col3 = st.columns(3)
    mes = col1.selectbox("Mes", ["Todos","1","2","3","4","5","6","7","8","9","10","11","12"])
    buscar = col2.text_input("Buscar")
    cronologico = col3.checkbox("Orden cronológico (más antiguo primero)")
    where = []
    if mes != "Todos": where.append(f"mes={mes}")
    if buscar: where.append(f"detalle ILIKE '%{buscar}%'")
    sql = "SELECT fecha, id_titular, cod_cuenta, detalle, importe FROM cashflow"
    if where: sql += " WHERE " + " AND ".join(where)
    if cronologico:
        sql += " ORDER BY fecha ASC LIMIT 500"
    else:
        sql += " ORDER BY fecha DESC LIMIT 500"
    try:
        df = query(sql)
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)
        st.metric("Total", f"${df['importe'].sum():,.2f}")
    except Exception as e:
        st.error(f"{e}")
