import tkinter as tk
from tkinter import messagebox, ttk, Menu
import sqlite3
import requests
from datetime import datetime, timedelta
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Suprimir las advertencias de seguridad SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class Database:
    @staticmethod
    def init_db():
        conn = sqlite3.connect('asistencia.db')
        c = conn.cursor()

        # Crear tabla de asistencia con las columnas correctas
        c.execute('''CREATE TABLE IF NOT EXISTS asistencia
                     (dni TEXT PRIMARY KEY, nombre TEXT, paterno TEXT, materno TEXT, genero TEXT, hora_ingreso TEXT, hora_salida TEXT, fecha TEXT)''')
        # Intentar añadir la columna hora_salida si no existe
        try:
            c.execute("ALTER TABLE asistencia ADD COLUMN hora_salida TEXT")
        except sqlite3.OperationalError:
            # La columna ya existe
            pass

        # Crear tabla de usuarios
        c.execute('''CREATE TABLE IF NOT EXISTS usuarios
                     (username TEXT PRIMARY KEY, password TEXT, role TEXT)''')

        # Añadir un usuario administrador si no existe
        c.execute("INSERT OR IGNORE INTO usuarios (username, password, role) VALUES ('admin', 'admin', 'admin')")
        c.execute("INSERT OR IGNORE INTO usuarios (username, password, role) VALUES ('auxiliar', 'auxiliar', 'auxiliar')")
        conn.commit()
        conn.close()

    @staticmethod
    def get_db_cursor():
        conn = sqlite3.connect('asistencia.db')
        c = conn.cursor()
        return conn, c

class Login:
    def __init__(self, root):
        self.root = root
        self.root.title("Login")

        self.frame = tk.Frame(self.root)
        self.frame.pack(pady=20)

        tk.Label(self.frame, text="Username:").grid(row=0, column=0, padx=10)
        self.entry_username = tk.Entry(self.frame)
        self.entry_username.grid(row=0, column=1, padx=10)

        tk.Label(self.frame, text="Password:").grid(row=1, column=0, padx=10)
        self.entry_password = tk.Entry(self.frame, show="*")
        self.entry_password.grid(row=1, column=1, padx=10)

        tk.Button(self.frame, text="Login", command=self.verify_credentials).grid(row=2, column=0, columnspan=2, pady=10)

    def verify_credentials(self):
        username = self.entry_username.get()
        password = self.entry_password.get()
        if username and password:
            conn, c = Database.get_db_cursor()
            c.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            conn.close()
            if user:
                self.frame.destroy()
                App(self.root, user[2])  # Pasar el rol del usuario a la aplicación principal
            else:
                messagebox.showerror("Error", "Invalid credentials")
        else:
            messagebox.showwarning("Warning", "Please enter both username and password")

class API:
    @staticmethod
    def consultar_api_dni(dni):
        api_token = "FnthEvsED1YHEe6Dkx7IGGXg0ftDMFZllaCRweDOxrjlK4yf6M"
        url = f"https://api.perufacturacion.com/api?api_token={api_token}&json=dni&id={dni}"
        try:
            response = requests.get(url, verify=False)
            if response.status_code == 200:
                print(f"Respuesta de la API: {response.json()}")
                return response.json()
            else:
                print(f"Error en la respuesta de la API: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error consultando API DNI: {e}")
            return None

class Asistencia:
    def __init__(self, root):
        self.root = root

    def registrar_asistencia(self):
        dni = entry_dni.get()
        if dni:
            conn, c = Database.get_db_cursor()
            c.execute("SELECT * FROM asistencia WHERE dni=? AND fecha=?", (dni, datetime.now().strftime('%Y-%m-%d')))
            result = c.fetchone()
            if result:
                hora_salida = datetime.now().strftime('%H:%M:%S')
                c.execute("UPDATE asistencia SET hora_salida=? WHERE dni=?", (hora_salida, dni))
                conn.commit()
                messagebox.showinfo("Registro de Asistencia", "Salida registrada correctamente.")
            else:
                datos = API.consultar_api_dni(dni)
                if datos and datos.get('mensaje') == 'OK':
                    nombre = datos.get('nombres', '')
                    paterno = datos.get('apellido_paterno', '')
                    materno = datos.get('apellido_materno', '')
                    genero = "desconocido"  # Asumimos que no se obtiene el género de la API
                    self.ventana_registro_manual(dni, nombre, paterno, materno, genero)
                else:
                    self.ventana_registro_manual(dni)
            conn.close()
        else:
            messagebox.showwarning("Advertencia", "Por favor ingrese un DNI válido.")

    def registrar_datos(self, dni, nombre, paterno, materno, genero):
        conn, c = Database.get_db_cursor()
        hora_ingreso = datetime.now().strftime('%H:%M:%S')
        fecha = datetime.now().strftime('%Y-%m-%d')
        c.execute("INSERT INTO asistencia (dni, nombre, paterno, materno, genero, hora_ingreso, fecha) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (dni, nombre, paterno, materno, genero, hora_ingreso, fecha))
        conn.commit()
        conn.close()
        messagebox.showinfo("Registro de Asistencia", "Asistencia registrada correctamente.")
        self.actualizar_tabla_asistencia()

    def ventana_registro_manual(self, dni, nombre='', paterno='', materno='', genero='desconocido'):
        manual_window = tk.Toplevel(self.root)
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
        
        def guardar_datos():
            nombre = entry_nombre.get()
            paterno = entry_paterno.get()
            materno = entry_materno.get()
            genero = genero_var.get()
            self.registrar_datos(dni, nombre, paterno, materno, genero)
            manual_window.destroy()
        
        tk.Button(manual_window, text="Guardar", command=guardar_datos).grid(row=4, column=0, columnspan=2)

    def actualizar_tabla_asistencia(self, intervalo="Día"):
        conn, c = Database.get_db_cursor()

        if intervalo == "Día":
            c.execute("SELECT dni, nombre, paterno, materno, genero, hora_ingreso, hora_salida, fecha FROM asistencia WHERE fecha=?", (datetime.now().strftime('%Y-%m-%d'),))
        elif intervalo == "Semana":
            semana_pasada = datetime.now() - timedelta(days=7)
            c.execute("SELECT dni, nombre, paterno, materno, genero, hora_ingreso, hora_salida, fecha FROM asistencia WHERE fecha >= ?", (semana_pasada.strftime('%Y-%m-%d'),))
        elif intervalo == "Mes":
            mes_pasado = datetime.now() - timedelta(days=30)
            c.execute("SELECT dni, nombre, paterno, materno, genero, hora_ingreso, hora_salida, fecha FROM asistencia WHERE fecha >= ?", (mes_pasado.strftime('%Y-%m-%d'),))

        registros = c.fetchall()
        conn.close()

        for row in tabla_asistencia.get_children():
            tabla_asistencia.delete(row)

        for row in registros:
            tabla_asistencia.insert("", tk.END, values=row)

    def exportar_a_excel(self):
        conn, c = Database.get_db_cursor()
        c.execute("SELECT * FROM asistencia")
        registros = c.fetchall()
        conn.close()

        df = pd.DataFrame(registros, columns=['DNI', 'Nombre', 'Apellido Paterno', 'Apellido Materno', 'Genero', 'Hora de Ingreso', 'Hora de Salida', 'Fecha'])
        df.to_excel("Asistencia.xlsx", index=False)
        messagebox.showinfo("Exportar a Excel", "Datos exportados a Asistencia.xlsx")

    def exportar_a_pdf(self):
        conn, c = Database.get_db_cursor()
        c.execute("SELECT * FROM asistencia")
        registros = c.fetchall()
        conn.close()

        c = canvas.Canvas("Asistencia.pdf", pagesize=letter)
        c.drawString(30, 750, "Registro de Asistencia")
        y = 720
        for registro in registros:
            texto = f"DNI: {registro[0]}, Nombre: {registro[1]}, Apellido Paterno: {registro[2]}, Apellido Materno: {registro[3]}, Género: {registro[4]}, Hora de Ingreso: {registro[5]}, Hora de Salida: {registro[6]}, Fecha: {registro[7]}"
            c.drawString(30, y, texto)
            y -= 20
            if y < 40:
                c.showPage()
                y = 750
        c.save()
        messagebox.showinfo("Exportar a PDF", "Datos exportados a Asistencia.pdf")

    def registrar_salida(self):
        item = tabla_asistencia.selection()
        if item:
            item_data = tabla_asistencia.item(item, "values")
            dni = item_data[0]
            hora_salida = datetime.now().strftime('%H:%M:%S')
            conn, c = Database.get_db_cursor()
            c.execute("UPDATE asistencia SET hora_salida=? WHERE dni=?", (hora_salida, dni))
            conn.commit()
            conn.close()
            messagebox.showinfo("Registro de Asistencia", "Hora de salida registrada correctamente.")
            self.actualizar_tabla_asistencia()
        else:
            messagebox.showwarning("Advertencia", "Por favor seleccione un registro para registrar la hora de salida.")

class App:
    def __init__(self, root, role):
        self.root = root
        self.role = role
        self.root.title("Registro de Asistencia")
        
        self.create_widgets()

    def create_widgets(self):
        # Barra de Menú
        menubar = Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Exportar a Excel", command=Asistencia(self.root).exportar_a_excel)
        file_menu.add_command(label="Exportar a PDF", command=Asistencia(self.root).exportar_a_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.quit)

        self.root.geometry('800x600')

        frame_principal = tk.Frame(self.root)
        frame_principal.pack(pady=20)

        # Campo de entrada para el DNI
        global entry_dni
        tk.Label(frame_principal, text="DNI:").grid(row=0, column=0, padx=10)
        entry_dni = tk.Entry(frame_principal)
        entry_dni.grid(row=0, column=1, padx=10)

        # Botón para registrar la asistencia
        tk.Button(frame_principal, text="Registrar Asistencia", command=Asistencia(self.root).registrar_asistencia).grid(row=0, column=2, padx=10)

        # Tabla de asistencia
        global tabla_asistencia
        columns = ("dni", "nombre", "paterno", "materno", "genero", "hora_ingreso", "hora_salida", "fecha")
        tabla_asistencia = ttk.Treeview(frame_principal, columns=columns, show="headings")
        tabla_asistencia.grid(row=1, column=0, columnspan=3, pady=10)

        for col in columns:
            tabla_asistencia.heading(col, text=col.capitalize())

        # Selector de intervalo de tiempo para mostrar la asistencia
        tk.Label(frame_principal, text="Mostrar asistencia:").grid(row=2, column=0, padx=10, pady=10)
        intervalo_var = tk.StringVar(value="Día")
        intervalo_selector = ttk.Combobox(frame_principal, textvariable=intervalo_var, values=["Día", "Semana", "Mes"])
        intervalo_selector.grid(row=2, column=1, padx=10, pady=10)
        intervalo_selector.bind("<<ComboboxSelected>>", lambda event: Asistencia(self.root).actualizar_tabla_asistencia(intervalo_var.get()))

        Asistencia(self.root).actualizar_tabla_asistencia()

        # Menú contextual para la tabla de asistencia
        self.context_menu = Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Registrar Hora de Salida", command=Asistencia(self.root).registrar_salida)
        tabla_asistencia.bind("<Button-3>", self.show_context_menu)

        # Desactivar ciertas funcionalidades basadas en el rol del usuario
        if self.role == 'auxiliar':
            file_menu.entryconfig("Exportar a Excel", state="disabled")
            file_menu.entryconfig("Exportar a PDF", state="disabled")

    def show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

def main():
    Database.init_db()
    root = tk.Tk()
    Login(root)
    root.mainloop()

if __name__ == "__main__":
    main()
