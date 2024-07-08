import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import requests
from datetime import datetime, timedelta

# Función para inicializar la base de datos
def init_db():
    conn = sqlite3.connect('asistencia.db')
    c = conn.cursor()

    # Crear tabla de asistencia con las columnas correctas
    c.execute('''CREATE TABLE IF NOT EXISTS asistencia
                 (dni TEXT PRIMARY KEY, nombre TEXT, paterno TEXT, materno TEXT, genero TEXT, estado_civil TEXT, fecha_nacimiento TEXT, hora_ingreso TEXT, fecha TEXT)''')

    # Crear tabla de usuarios
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')

    # Añadir un usuario administrador si no existe
    c.execute("INSERT OR IGNORE INTO usuarios (username, password, role) VALUES ('admin', 'admin', 'admin')")
    conn.commit()
    conn.close()

init_db()

# Función para conectar a la base de datos y obtener un cursor
def get_db_cursor():
    conn = sqlite3.connect('asistencia.db')
    c = conn.cursor()
    return conn, c

# Función para consultar API de DNI
def consultar_api_dni(dni):
    url = f'https://dniruc.apisperu.com/api/v1/dni/{dni}?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IkVjYXlvbWFAZ21haWwuY29tIn0.4w94GBUGg1bJmN50EiHBd1qHYEpnmjmS93lRP_7Nsr8'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"Error consultando API DNI: {e}")
        return None

# Función para registrar asistencia
def registrar_asistencia():
    dni = entry_dni.get()
    if dni:
        conn, c = get_db_cursor()
        c.execute("SELECT * FROM asistencia WHERE dni=?", (dni,))
        result = c.fetchone()
        if result:
            messagebox.showinfo("Registro de Asistencia", "Asistencia registrada correctamente.")
        else:
            datos = consultar_api_dni(dni)
            if datos:
                if datos.get('success', True):
                    nombre = datos.get('nombres', '')
                    paterno = datos.get('apellidoPaterno', '')
                    materno = datos.get('apellidoMaterno', '')
                    genero = "desconocido"  # Asumimos que no se obtiene el género de la API
                    ventana_registro_manual(dni, nombre, paterno, materno, genero)
                else:
                    ventana_registro_manual(dni)
            else:
                ventana_registro_manual(dni)
        conn.close()
    else:
        messagebox.showwarning("Advertencia", "Por favor ingrese un DNI válido.")

# Función para registrar datos en la base de datos
def registrar_datos(dni, nombre, paterno, materno, genero, estado_civil, fecha_nacimiento):
    conn, c = get_db_cursor()
    hora_ingreso = datetime.now().strftime('%H:%M:%S')
    fecha = datetime.now().strftime('%Y-%m-%d')
    c.execute("INSERT INTO asistencia (dni, nombre, paterno, materno, genero, estado_civil, fecha_nacimiento, hora_ingreso, fecha) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (dni, nombre, paterno, materno, genero, estado_civil, fecha_nacimiento, hora_ingreso, fecha))
    conn.commit()
    conn.close()
    messagebox.showinfo("Registro de Asistencia", "Asistencia registrada correctamente.")
    actualizar_tabla_asistencia()

# Función para actualizar datos en la base de datos
def actualizar_datos():
    dni = entry_dni.get()
    nombre = entry_nombre.get()
    paterno = entry_paterno.get()
    materno = entry_materno.get()
    genero = genero_var.get()
    estado_civil = estado_civil_var.get()
    fecha_nacimiento = entry_fecha_nacimiento.get()
    conn, c = get_db_cursor()
    c.execute("UPDATE asistencia SET nombre=?, paterno=?, materno=?, genero=?, estado_civil=?, fecha_nacimiento=? WHERE dni=?",
              (nombre, paterno, materno, genero, estado_civil, fecha_nacimiento, dni))
    conn.commit()
    conn.close()
    messagebox.showinfo("Actualización de Asistencia", "Asistencia actualizada correctamente.")
    actualizar_tabla_asistencia()

# Función para eliminar datos en la base de datos
def eliminar_datos():
    dni = entry_dni.get()
    conn, c = get_db_cursor()
    c.execute("DELETE FROM asistencia WHERE dni=?", (dni,))
    conn.commit()
    conn.close()
    messagebox.showinfo("Eliminación de Asistencia", "Asistencia eliminada correctamente.")
    actualizar_tabla_asistencia()

# Función para ventana de registro manual
def ventana_registro_manual(dni, nombre='', paterno='', materno='', genero='desconocido'):
    manual_window = tk.Toplevel(root)
    manual_window.title("Registro Manual")
    
    tk.Label(manual_window, text="Nombre:").grid(row=0, column=0)
    global entry_nombre
    entry_nombre = tk.Entry(manual_window)
    entry_nombre.insert(0, nombre)
    entry_nombre.grid(row=0, column=1)
    
    tk.Label(manual_window, text="Apellido Paterno:").grid(row=1, column=0)
    global entry_paterno
    entry_paterno = tk.Entry(manual_window)
    entry_paterno.insert(0, paterno)
    entry_paterno.grid(row=1, column=1)
    
    tk.Label(manual_window, text="Apellido Materno:").grid(row=2, column=0)
    global entry_materno
    entry_materno = tk.Entry(manual_window)
    entry_materno.insert(0, materno)
    entry_materno.grid(row=2, column=1)
    
    tk.Label(manual_window, text="Género:").grid(row=3, column=0)
    global genero_var
    genero_var = tk.StringVar(value=genero)
    
    frame_genero = tk.Frame(manual_window)
    frame_genero.grid(row=3, column=1)
    
    tk.Radiobutton(frame_genero, text="Masculino", variable=genero_var, value="masculino").pack(side=tk.LEFT)
    tk.Radiobutton(frame_genero, text="Femenino", variable=genero_var, value="femenino").pack(side=tk.LEFT)
    
    tk.Label(manual_window, text="Estado Civil:").grid(row=4, column=0)
    global estado_civil_var
    estado_civil_var = tk.StringVar()
    
    frame_estado_civil = tk.Frame(manual_window)
    frame_estado_civil.grid(row=4, column=1)
    
    tk.Radiobutton(frame_estado_civil, text="Soltero", variable=estado_civil_var, value="soltero").pack(side=tk.LEFT)
    tk.Radiobutton(frame_estado_civil, text="Casado", variable=estado_civil_var, value="casado").pack(side=tk.LEFT)
    tk.Radiobutton(frame_estado_civil, text="Viudo", variable=estado_civil_var, value="viudo").pack(side=tk.LEFT)
    tk.Radiobutton(frame_estado_civil, text="Divorciado", variable=estado_civil_var, value="divorciado").pack(side=tk.LEFT)
    
    tk.Label(manual_window, text="Fecha de Nacimiento (AAAA-MM-DD):").grid(row=5, column=0)
    global entry_fecha_nacimiento
    entry_fecha_nacimiento = tk.Entry(manual_window)
    entry_fecha_nacimiento.grid(row=5, column=1)
    
    def guardar_datos():
        nombre = entry_nombre.get()
        paterno = entry_paterno.get()
        materno = entry_materno.get()
        genero = genero_var.get()
        estado_civil = estado_civil_var.get()
        fecha_nacimiento = entry_fecha_nacimiento.get()
        registrar_datos(dni, nombre, paterno, materno, genero, estado_civil, fecha_nacimiento)
        manual_window.destroy()
    
    tk.Button(manual_window, text="Guardar", command=guardar_datos).grid(row=6, column=0, columnspan=2)

# Función para iniciar sesión
def iniciar_sesion():
    username = entry_username.get()
    password = entry_password.get()
    conn, c = get_db_cursor()
    c.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
    result = c.fetchone()
    conn.close()
    if result:
        role = result[2]
        if role == 'admin':
            ventana_administrador()
        else:
            messagebox.showwarning("Acceso Denegado", "No tienes permisos de administrador.")
    else:
        messagebox.showwarning("Error", "Credenciales incorrectas.")

# Función para ventana de administrador
def ventana_administrador():
    admin_window = tk.Toplevel(root)
    admin_window.title("Panel de Administrador")
    
    tk.Label(admin_window, text="Filtrar por:").grid(row=0, column=0)
    filtro_opciones = ['Día', 'Semana', 'Mes']
    filtro_var = tk.StringVar(admin_window)
    filtro_var.set(filtro_opciones[0])
    filtro_menu = tk.OptionMenu(admin_window, filtro_var, *filtro_opciones)
    filtro_menu.grid(row=0, column=1)
    
    def mostrar_registros():
        filtro = filtro_var.get()
        ahora = datetime.now()
        conn, c = get_db_cursor()
        if filtro == 'Día':
            fecha_inicio = ahora.strftime('%Y-%m-%d')
            c.execute("SELECT * FROM asistencia WHERE fecha=?", (fecha_inicio,))
        elif filtro == 'Semana':
            semana_inicio = (ahora - timedelta(days=ahora.weekday())).strftime('%Y-%m-%d')
            semana_fin = (ahora + timedelta(days=(6 - ahora.weekday()))).strftime('%Y-%m-%d')
            c.execute("SELECT * FROM asistencia WHERE fecha BETWEEN ? AND ?", (semana_inicio, semana_fin))
        elif filtro == 'Mes':
            mes_inicio = ahora.strftime('%Y-%m-01')
            mes_fin = (ahora.replace(month=ahora.month + 1, day=1) - timedelta(days=1)).strftime('%Y-%m-%d')
            c.execute("SELECT * FROM asistencia WHERE fecha BETWEEN ? AND ?", (mes_inicio, mes_fin))
        
        registros = c.fetchall()
        conn.close()
        registros.sort(key=lambda x: x[7])  # Ordenar por hora de ingreso
        for registro in registros:
            registros_text.insert(tk.END, f"DNI: {registro[0]}, Nombre: {registro[1]} {registro[2]} {registro[3]}, Género: {registro[4]}, Estado Civil: {registro[5]}, Fecha de Nacimiento: {registro[6]}, Hora de Ingreso: {registro[7]}, Fecha: {registro[8]}\n")
    
    tk.Button(admin_window, text="Mostrar Registros", command=mostrar_registros).grid(row=1, column=0, columnspan=2)

    registros_text = tk.Text(admin_window, wrap=tk.WORD, width=100, height=20)
    registros_text.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

# Función para actualizar la tabla de asistencia en la interfaz
def actualizar_tabla_asistencia():
    for i in tabla_asistencia.get_children():
        tabla_asistencia.delete(i)
    
    conn, c = get_db_cursor()
    c.execute("SELECT * FROM asistencia")
    registros = c.fetchall()
    conn.close()
    
    for registro in registros:
        tabla_asistencia.insert("", tk.END, values=(registro[0], registro[1], registro[2], registro[3], registro[4], registro[5], registro[6], registro[7], registro[8]))

# Ventana principal
root = tk.Tk()
root.title("Registro de Asistencia")
root.configure(bg='blue')

# Título principal
tk.Label(root, text="Bienvenido", font=('Helvetica', 18, 'bold'), bg='blue', fg='white').grid(row=0, column=0, columnspan=2, pady=10)
tk.Label(root, text="REGISTRO DE ASISTENCIA", font=('Helvetica', 14, 'bold'), bg='blue', fg='white').grid(row=1, column=0, columnspan=2, pady=5)

# Pantalla de inicio de sesión
login_frame = tk.Frame(root, bg='blue')
login_frame.grid(row=2, column=0, pady=10)

tk.Label(login_frame, text="Usuario:", bg='blue', fg='white').grid(row=0, column=0)
entry_username = tk.Entry(login_frame)
entry_username.grid(row=0, column=1)

tk.Label(login_frame, text="Contraseña:", bg='blue', fg='white').grid(row=1, column=0)
entry_password = tk.Entry(login_frame, show='*')
entry_password.grid(row=1, column=1)

tk.Button(login_frame, text="Iniciar Sesión", command=iniciar_sesion).grid(row=2, column=0, columnspan=2, pady=5)

# Pantalla de registro de asistencia
asistencia_frame = tk.Frame(root, bg='blue')
asistencia_frame.grid(row=3, column=0, pady=10)

tk.Label(asistencia_frame, text="DNI:", bg='blue', fg='white').grid(row=0, column=0)
entry_dni = tk.Entry(asistencia_frame)
entry_dni.grid(row=0, column=1)

tk.Button(asistencia_frame, text="Registrar", command=registrar_asistencia).grid(row=1, column=0, columnspan=2, pady=5)

# Tabla de asistencia
tabla_frame = tk.Frame(root, bg='blue')
tabla_frame.grid(row=4, column=0, padx=10, pady=10)

columns = ("dni", "nombre", "paterno", "materno", "genero", "estado_civil", "fecha_nacimiento", "hora_ingreso", "fecha")
tabla_asistencia = ttk.Treeview(tabla_frame, columns=columns, show="headings")
for col in columns:
    tabla_asistencia.heading(col, text=col)

tabla_asistencia.grid(row=0, column=0, columnspan=4)

tk.Button(tabla_frame, text="Actualizar", command=actualizar_datos).grid(row=1, column=0)
tk.Button(tabla_frame, text="Eliminar", command=eliminar_datos).grid(row=1, column=1)
tk.Button(tabla_frame, text="Mostrar Todos", command=actualizar_tabla_asistencia).grid(row=1, column=2)

root.mainloop()
