import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import sqlite3
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import aiohttp
import asyncio
from datetime import datetime, date, timedelta
import calendar
import pandas as pd
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
import pytz

# Suprimir las advertencias de seguridad SSL
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Crear la base de datos y las tablas necesarias
def create_tables():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dni TEXT NOT NULL,
        first_name TEXT,
        paternal_surname TEXT,
        maternal_surname TEXT,
        entry_time TEXT,
        exit_time TEXT,
        date TEXT NOT NULL
    )
    ''')
    
    # Insertar usuarios predeterminados
    cursor.execute('''
    INSERT OR IGNORE INTO users (username, password, role) VALUES 
    ('admin', 'admin123', 'admin'),
    ('auxiliar', 'auxiliar123', 'auxiliar')
    ''')
    
    # Crear índice en la columna dni para mejorar la velocidad de consulta
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dni ON attendance (dni)')
    
    conn.commit()
    conn.close()

class AttendanceSystem:
    def __init__(self):
        self.conn = sqlite3.connect('attendance.db', detect_types=sqlite3.PARSE_DECLTYPES)
        self.cursor = self.conn.cursor()
        self.cache = {}
        self.timezone = pytz.timezone("America/Lima")  # Zona horaria de Perú
        
    async def consultar_dni(self, dni):
        if dni in self.cache:
            return self.cache[dni], None
        
        api_token = "FnthEvsED1YHEe6Dkx7IGGXg0ftDMFZllaCRweDOxrjlK4yf6M"
        url = f"https://api.perufacturacion.com/api?api_token={api_token}&json=dni&id={dni}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False) as response:
                    if response.status != 200:
                        return None, f"Error en la solicitud: {response.status}"
                    data = await response.json()
                    if "mensaje" in data and data["code"] == "404":
                        return None, None
                    else:
                        self.cache[dni] = data
                        return data, None
        except Exception as e:
            return None, f"Error en la solicitud: {str(e)}"
    
    def is_registered_today(self, dni):
        current_date = datetime.now(self.timezone).strftime('%Y-%m-%d')
        self.cursor.execute('''
        SELECT entry_time, exit_time FROM attendance WHERE dni = ? AND date = ?
        ''', (dni, current_date))
        return self.cursor.fetchone()
    
    def register_entry(self, dni, first_name, paternal_surname, maternal_surname):
        current_time = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
        current_date = datetime.now(self.timezone).strftime('%Y-%m-%d')
        
        self.cursor.execute('''
        INSERT INTO attendance (dni, first_name, paternal_surname, maternal_surname, entry_time, date)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (dni, first_name, paternal_surname, maternal_surname, current_time, current_date))
        
        self.conn.commit()
    
    def register_exit(self, dni):
        current_time = datetime.now(self.timezone).strftime('%Y-%m-%d %H:%M:%S')
        
        self.cursor.execute('''
        UPDATE attendance SET exit_time = ?
        WHERE dni = ? AND date = date('now', 'localtime') AND exit_time IS NULL
        ''', (current_time, dni))
        
        self.conn.commit()
    
    def get_daily_records(self):
        self.cursor.execute('''
        SELECT dni, first_name, paternal_surname, maternal_surname, entry_time, exit_time 
        FROM attendance WHERE date = date('now', 'localtime') ORDER BY entry_time DESC
        ''')
        return self.cursor.fetchall()
    
    def get_weekly_records(self):
        current_date = datetime.now(self.timezone).date()
        start_of_week = current_date - timedelta(days=current_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)  # Incluye el domingo

        self.cursor.execute('''
        SELECT dni, first_name || ' ' || paternal_surname || ' ' || maternal_surname as full_name,
        date,
        CASE 
            WHEN entry_time IS NULL THEN 'F'
            ELSE 'A'
        END as status
        FROM attendance 
        WHERE date BETWEEN ? AND ?
        ''', (start_of_week, end_of_week))
        records = self.cursor.fetchall()
        return self.process_weekly_records(records, start_of_week, end_of_week)
    
    def process_weekly_records(self, records, start_of_week, end_of_week):
        dni_names = {record[0]: record[1] for record in records}
        days_in_week = (end_of_week - start_of_week).days + 1
        weekly_data = {dni: {str(day): 'F' for day in range(days_in_week)} for dni in dni_names.keys()}
        
        for record in records:
            dni, date, status = record[0], record[2], record[3]
            day = (datetime.strptime(date, '%Y-%m-%d').date() - start_of_week).days
            if 0 <= day < days_in_week:
                weekly_data[dni][str(day)] = status
        
        result = []
        for dni, days in weekly_data.items():
            result.append((dni, dni_names[dni]) + tuple(days[str(day)] for day in range(days_in_week)))
        
        return result

    def get_monthly_records(self, month):
        self.cursor.execute('''
        SELECT dni, first_name || ' ' || paternal_surname || ' ' || maternal_surname as full_name,
        date,
        CASE 
            WHEN entry_time IS NOT NULL AND exit_time IS NOT NULL THEN '✓'
            ELSE 'x'
        END as status
        FROM attendance 
        WHERE strftime('%Y-%m', date) = ?
        ''', (month,))
        records = self.cursor.fetchall()
        return self.process_monthly_records(records, month)

    def process_monthly_records(self, records, month):
        dni_names = {record[0]: record[1] for record in records}
        days_in_month = calendar.monthrange(int(month.split('-')[0]), int(month.split('-')[1].strip()))[1]
        monthly_data = {dni: {str(day): 'x' for day in range(1, days_in_month + 1)} for dni in dni_names.keys()}
        
        for record in records:
            dni, date, status = record[0], record[2], record[3]
            day = int(date.split('-')[2])
            monthly_data[dni][str(day)] = status
        
        result = []
        for dni, days in monthly_data.items():
            result.append((dni, dni_names[dni]) + tuple(days[str(day)] for day in range(1, days_in_month + 1)))
        
        return result

class AttendanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Attendance System")
        self.system = AttendanceSystem()
        self.dni_map = {}  # Dictionary to map widgets to DNI
        self.create_login_screen()

    def create_login_screen(self):
        self.clear_screen()
        
        # Crear un canvas para el degradado de fondo
        self.canvas = tk.Canvas(self.root, width=400, height=400)
        self.canvas.pack(fill="both", expand=True)

        # Crear el degradado
        self.create_gradient(self.canvas, '#00BFFF', '#6E260E')

        # Agregar la imagen
        self.image = Image.open("IMAGEN_PANDA.png")
        self.image = self.image.resize((120, 120), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(self.image)
        self.canvas.create_image(200, 50, image=self.photo)

        # Agregar los textos
        self.canvas.create_text(200, 150, text="BIENVENIDOS AL REGISTRO DE ASISTENCIA", font=("Helvetica", 13), fill="black")
        self.canvas.create_text(200, 180, text="Ingrese su usuario y contraseña, por favor", font=("Helvetica", 11), fill="white")

        # Crear entradas de texto y botón de login en el canvas
        self.username_entry = ttk.Entry(self.root)
        self.password_entry = ttk.Entry(self.root, show="*")
        self.login_button = ttk.Button(self.root, text="Login", command=self.login)

        self.canvas.create_window(200, 220, window=self.username_entry, width=200, height=30)
        self.canvas.create_window(200, 260, window=self.password_entry, width=200, height=30)
        self.canvas.create_window(200, 300, window=self.login_button, width=100, height=30)

    def create_gradient(self, canvas, color1, color2):
        width = 400
        height = 400
        limit = 256

        r1, g1, b1 = canvas.winfo_rgb(color1)
        r2, g2, b2 = canvas.winfo_rgb(color2)

        r_ratio = (r2 - r1) / limit
        g_ratio = (g2 - g1) / limit
        b_ratio = (b2 - b1) / limit

        for i in range(limit):
            nr = int(r1 + (r_ratio * i))
            ng = int(g1 + (g_ratio * i))
            nb = int(b1 + (b_ratio * i))
            color = f'#{nr:04x}{ng:04x}{nb:04x}'
            canvas.create_line(0, i * height // limit, width, i * height // limit, fill=color)

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        self.system.cursor.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        result = self.system.cursor.fetchone()
        
        if result:
            role = result[0]
            if role == "admin":
                self.show_welcome_message()
            elif role == "auxiliar":
                self.create_auxiliar_tabs()
        else:
            messagebox.showerror("Error", "Invalid username or password")
    
    def show_welcome_message(self):
        messagebox.showinfo("Bienvenido", "Bienvenido admin")
        self.create_admin_tabs()
    
    def create_admin_tabs(self):
        self.clear_screen()
        
        tab_control = ttk.Notebook(self.root)
        
        self.register_tab = ttk.Frame(tab_control, style='My.TFrame')
        self.view_tab = ttk.Frame(tab_control, style='My.TFrame')
        self.report_tab = ttk.Frame(tab_control, style='My.TFrame')
        
        tab_control.add(self.register_tab, text='Registrar Asistencia')
        tab_control.add(self.view_tab, text='Registros del Día')
        tab_control.add(self.report_tab, text='Ver Asistencias')
        
        tab_control.pack(expand=1, fill='both')
        
        self.create_register_tab()
        self.create_view_tab()
        self.create_report_tab()
    
    def create_auxiliar_tabs(self):
        self.clear_screen()
        
        tab_control = ttk.Notebook(self.root)
        
        self.register_tab = ttk.Frame(tab_control, style='My.TFrame')
        self.view_tab = ttk.Frame(tab_control, style='My.TFrame')
        
        tab_control.add(self.register_tab, text='Registrar Asistencia')
        tab_control.add(self.view_tab, text='Registros del Día')
        
        tab_control.pack(expand=1, fill='both')
        
        self.create_register_tab()
        self.create_view_tab()
    
    def create_register_tab(self):
        tk.Label(self.register_tab, text="Ingrese DNI:").grid(row=0, column=0, padx=10, pady=10)
        self.dni_entry = tk.Entry(self.register_tab)
        self.dni_entry.grid(row=0, column=1, padx=10, pady=10)
        
        self.consult_button = tk.Button(self.register_tab, text="Consultar", command=lambda: asyncio.run(self.consultar_dni()))
        self.consult_button.grid(row=1, columnspan=2, pady=10)
        
        self.details_frame = tk.Frame(self.register_tab)
        self.details_frame.grid(row=2, columnspan=2, pady=10)
        
        self.dni_entry.bind('<Return>', lambda event: asyncio.run(self.consultar_dni()))
        self.dni_entry.focus_set()  # Establecer el foco en el campo de entrada del DNI
    
    async def consultar_dni(self, event=None):
        dni = self.dni_entry.get()
        record = self.system.is_registered_today(dni)
        
        if record:
            entry_time, exit_time = record
            if exit_time is None:
                self.show_exit_screen(dni)
                self.system.register_exit(dni)
                messagebox.showinfo("Registro", "Hora de salida registrada correctamente.")
            else:
                messagebox.showinfo("Registro", "La asistencia ya ha sido registrada por completo hoy.")
        else:
            data, error = await self.system.consultar_dni(dni)
            if error:
                messagebox.showerror("Error", error)
            else:
                self.show_user_data(data) if data else self.show_manual_entry_form(dni)
                self.dni_entry.delete(0, tk.END)  # Borrar el campo de entrada del DNI después de consultar
                self.dni_entry.focus_set()  # Establecer el foco nuevamente en el campo de entrada del DNI
    
    def show_user_data(self, data):
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.details_frame, text="DNI:").grid(row=0, column=0, padx=10, pady=10)
        self.dni_display_entry = tk.Entry(self.details_frame)
        self.dni_display_entry.grid(row=0, column=1, padx=10, pady=10)
        self.dni_display_entry.insert(0, data.get('dni', ''))
        
        tk.Label(self.details_frame, text="Nombres:").grid(row=1, column=0, padx=10, pady=10)
        self.first_name_entry = tk.Entry(self.details_frame)
        self.first_name_entry.grid(row=1, column=1, padx=10, pady=10)
        self.first_name_entry.insert(0, data.get('nombres', ''))
        
        tk.Label(self.details_frame, text="Apellido Paterno:").grid(row=2, column=0, padx=10, pady=10)
        self.paternal_surname_entry = tk.Entry(self.details_frame)
        self.paternal_surname_entry.grid(row=2, column=1, padx=10, pady=10)
        self.paternal_surname_entry.insert(0, data.get('apellido_paterno', ''))
        
        tk.Label(self.details_frame, text="Apellido Materno:").grid(row=3, column=0, padx=10, pady=10)
        self.maternal_surname_entry = tk.Entry(self.details_frame)
        self.maternal_surname_entry.grid(row=3, column=1, padx=10, pady=10)
        self.maternal_surname_entry.insert(0, data.get('apellido_materno', ''))
        
        tk.Button(self.details_frame, text="Registrar Hora de Entrada", command=self.register_entry).grid(row=4, columnspan=2, pady=10)
    
        if all([self.dni_display_entry.get(), self.first_name_entry.get(), self.paternal_surname_entry.get(), self.maternal_surname_entry.get()]):
            self.register_entry()
    
    def show_manual_entry_form(self, dni):
        for widget in self.details_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.details_frame, text="DNI:").grid(row=0, column=0, padx=10, pady=10)
        self.dni_display_entry = tk.Entry(self.details_frame)
        self.dni_display_entry.grid(row=0, column=1, padx=10, pady=10)
        self.dni_display_entry.insert(0, dni)
        
        tk.Label(self.details_frame, text="Nombres:").grid(row=1, column=0, padx=10, pady=10)
        self.first_name_entry = tk.Entry(self.details_frame)
        self.first_name_entry.grid(row=1, column=1, padx=10, pady=10)
        
        tk.Label(self.details_frame, text="Apellido Paterno:").grid(row=2, column=0, padx=10, pady=10)
        self.paternal_surname_entry = tk.Entry(self.details_frame)
        self.paternal_surname_entry.grid(row=2, column=1, padx=10, pady=10)
        
        tk.Label(self.details_frame, text="Apellido Materno:").grid(row=3, column=0, padx=10, pady=10)
        self.maternal_surname_entry = tk.Entry(self.details_frame)
        self.maternal_surname_entry.grid(row=3, column=1, padx=10, pady=10)
        
        tk.Button(self.details_frame, text="Registrar Hora de Entrada", command=self.register_entry).grid(row=4, columnspan=2, pady=10)
    
    def register_entry(self):
        dni = self.dni_display_entry.get()
        first_name = self.first_name_entry.get()
        paternal_surname = self.paternal_surname_entry.get()
        maternal_surname = self.maternal_surname_entry.get()
        
        self.system.register_entry(dni, first_name, paternal_surname, maternal_surname)
        messagebox.showinfo("Registro", "Hora de entrada registrada correctamente.")
        self.load_daily_records()
        self.dni_entry.delete(0, tk.END)  # Borrar el campo de entrada del DNI principal después de registrar la entrada
        self.dni_entry.focus_set()  # Establecer el foco nuevamente en el campo de entrada del DNI principal
    
    def show_exit_screen(self, dni):
        exit_window = tk.Toplevel(self.root)
        exit_window.title("Registrar Hora de Salida")
        exit_window.geometry("300x200")
        
        tk.Label(exit_window, text="Registrar Hora de Salida").pack(pady=20)
        
        tk.Label(exit_window, text=f"DNI: {dni}").pack(pady=10)
        
        tk.Button(exit_window, text="Registrar Salida", command=lambda: self.confirm_exit(dni, exit_window)).pack(pady=20)
        
        exit_window.bind('<Return>', lambda event: self.confirm_exit(dni, exit_window))
    
    def confirm_exit(self, dni, window):
        self.system.register_exit(dni)
        messagebox.showinfo("Registro", "Hora de salida registrada correctamente.")
        window.destroy()
        self.load_daily_records()

    def create_view_tab(self):
        tk.Label(self.view_tab, text="DNI:").grid(row=0, column=0, padx=10, pady=10)
        self.dni_view_entry = tk.Entry(self.view_tab)
        self.dni_view_entry.grid(row=0, column=1, padx=10, pady=10)
        
        tk.Button(self.view_tab, text="Registrar Hora de Salida", command=self.register_exit).grid(row=1, columnspan=2, pady=10)
        
        self.canvas = tk.Canvas(self.view_tab)
        self.scrollbar = ttk.Scrollbar(self.view_tab, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.scrollbar.grid(row=2, column=2, sticky="ns")
        
        self.view_tab.grid_rowconfigure(2, weight=1)
        self.view_tab.grid_columnconfigure(1, weight=1)
        
        self.scrollable_frame.bind("<Button-3>", self.show_context_menu)
        
        self.load_daily_records()

    def show_context_menu(self, event):
        menu = tk.Menu(self.scrollable_frame, tearoff=0)
        menu.add_command(label="Registrar Hora de Salida", command=lambda: self.context_register_exit(event))
        menu.tk_popup(event.x_root, event.y_root)

    def context_register_exit(self, event):
        widget = self.scrollable_frame.winfo_containing(event.x_root, event.y_root)
        if widget:
            grid_info = widget.grid_info()
            if 'row' in grid_info:
                row = grid_info['row'] - 1  # Adjusting for header row
                dni = self.dni_map.get(row)
                if dni:
                    self.system.register_exit(dni)
                    messagebox.showinfo("Registro", f"Hora de salida registrada para DNI: {dni}")
                    self.load_daily_records()
    
    def register_exit(self):
        dni = self.dni_view_entry.get()
        self.system.register_exit(dni)
        messagebox.showinfo("Registro", "Hora de salida registrada correctamente.")
        self.load_daily_records()
        self.dni_view_entry.delete(0, tk.END)  # Borrar el campo de entrada del DNI después de registrar la salida
        self.dni_view_entry.focus_set()  # Establecer el foco nuevamente en el campo de entrada del DNI
    
    def load_daily_records(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        tk.Label(self.scrollable_frame, text="DNI").grid(row=0, column=0, padx=10, pady=10)
        tk.Label(self.scrollable_frame, text="Nombres").grid(row=0, column=1, padx=10, pady=10)
        tk.Label(self.scrollable_frame, text="Apellido Paterno").grid(row=0, column=2, padx=10, pady=10)
        tk.Label(self.scrollable_frame, text="Apellido Materno").grid(row=0, column=3, padx=10, pady=10)
        tk.Label(self.scrollable_frame, text="Hora de Entrada").grid(row=0, column=4, padx=10, pady=10)
        tk.Label(self.scrollable_frame, text="Hora de Salida").grid(row=0, column=5, padx=10, pady=10)
        
        records = self.system.get_daily_records()
        self.dni_map.clear()
        
        for i, record in enumerate(records):
            self.dni_map[i] = record[0]  # Map row number to DNI
            for j, value in enumerate(record):
                label = tk.Label(self.scrollable_frame, text=value)
                label.grid(row=i+1, column=j, padx=10, pady=10)
                if j == 0:  # Bind right-click only on DNI column
                    label.bind("<Button-3>", self.show_context_menu)
    
    def create_report_tab(self):
        tk.Label(self.report_tab, text="Ver Asistencias").grid(row=0, column=0, padx=10, pady=10)
        
        self.report_type = tk.StringVar(value="Día")
        tk.Radiobutton(self.report_tab, text="Día", variable=self.report_type, value="Día", command=self.load_reports).grid(row=1, column=0, padx=10, pady=10)
        tk.Radiobutton(self.report_tab, text="Semana", variable=self.report_type, value="Semana", command=self.load_reports).grid(row=1, column=1, padx=10, pady=10)
        tk.Radiobutton(self.report_tab, text="Mes", variable=self.report_type, value="Mes", command=self.load_reports).grid(row=1, column=2, padx=10, pady=10)
        
        self.month_var = tk.StringVar()
        month_combobox = ttk.Combobox(self.report_tab, textvariable=self.month_var)
        month_combobox['values'] = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
        month_combobox.grid(row=1, column=3, padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.report_tab)
        self.scrollbar = ttk.Scrollbar(self.report_tab, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.grid(row=2, column=0, columnspan=4, sticky="nsew")
        self.scrollbar.grid(row=2, column=4, sticky="ns")
        
        self.report_tab.grid_rowconfigure(2, weight=1)
        self.report_tab.grid_columnconfigure(1, weight=1)
        
        self.export_buttons_frame = ttk.Frame(self.report_tab)
        self.export_buttons_frame.grid(row=3, column=0, columnspan=4, pady=10)
        
        pdf_button = ttk.Button(self.export_buttons_frame, text="Exportar PDF", command=self.export_pdf)
        pdf_button.grid(row=0, column=0, padx=10)
        pdf_button.config(style="Red.TButton")
        
        excel_button = ttk.Button(self.export_buttons_frame, text="Exportar Excel", command=self.export_excel)
        excel_button.grid(row=0, column=1, padx=10)
        excel_button.config(style="Green.TButton")
        
        self.load_reports()

    def load_reports(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        
        report_type = self.report_type.get()
        
        if report_type == "Día":
            records = self.system.get_daily_records()
            tk.Label(self.scrollable_frame, text="DNI").grid(row=0, column=0, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Nombres").grid(row=0, column=1, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Apellido Paterno").grid(row=0, column=2, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Apellido Materno").grid(row=0, column=3, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Hora de Entrada").grid(row=0, column=4, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Hora de Salida").grid(row=0, column=5, padx=10, pady=10)
            
            for i, record in enumerate(records):
                for j, value in enumerate(record):
                    tk.Label(self.scrollable_frame, text=value).grid(row=i+1, column=j, padx=10, pady=10)
        
        elif report_type == "Semana":
            records = self.system.get_weekly_records()
            tk.Label(self.scrollable_frame, text="DNI").grid(row=0, column=0, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Nombres Completos").grid(row=0, column=1, padx=10, pady=10)
            for i, day in enumerate(["LU", "MA", "MI", "JU", "VI", "SA", "DO"]):
                tk.Label(self.scrollable_frame, text=day, fg="red" if i >= 5 else "black").grid(row=0, column=2+i, padx=10, pady=10)
            
            for i, record in enumerate(records):
                tk.Label(self.scrollable_frame, text=record[0]).grid(row=i+1, column=0, padx=10, pady=10)
                tk.Label(self.scrollable_frame, text=record[1]).grid(row=i+1, column=1, padx=10, pady=10)
                for j in range(7):
                    tk.Label(self.scrollable_frame, text=record[2+j], fg="red" if j >= 5 else "black").grid(row=i+1, column=2+j, padx=10, pady=10)
        
        elif report_type == "Mes":
            month = self.month_var.get()
            if not month:
                messagebox.showerror("Error", "Seleccione un mes")
                return
            
            month = f"2024-{month.strip()}"
            records = self.system.get_monthly_records(month)
            tk.Label(self.scrollable_frame, text="DNI").grid(row=0, column=0, padx=10, pady=10)
            tk.Label(self.scrollable_frame, text="Nombres Completos").grid(row=0, column=1, padx=10, pady=10)
            
            days_in_month = calendar.monthrange(2024, int(month.split('-')[1].strip()))[1]
            feriados = [
                "2024-01-01", "2024-04-01", "2024-05-01", "2024-06-29",
                "2024-07-28", "2024-07-29", "2024-08-30", "2024-10-08",
                "2024-11-01", "2024-12-08", "2024-12-25"
            ]
            
            for i, day in enumerate(range(1, days_in_month + 1)):
                current_date = date(2024, int(month.split('-')[1].strip()), day)
                day_of_week = current_date.weekday()
                fg_color = "red" if day_of_week >= 5 or current_date.strftime('%Y-%m-%d') in feriados else "blue"
                tk.Label(self.scrollable_frame, text=str(day), fg=fg_color).grid(row=0, column=2+i, padx=10, pady=10)
            
            for i, record in enumerate(records):
                tk.Label(self.scrollable_frame, text=record[0]).grid(row=i+1, column=0, padx=10, pady=10)
                tk.Label(self.scrollable_frame, text=record[1]).grid(row=i+1, column=1, padx=10, pady=10)
                for j, day in enumerate(range(1, days_in_month + 1)):
                    current_date = date(2024, int(month.split('-')[1].strip()), day)
                    day_of_week = current_date.weekday()
                    fg_color = "red" if day_of_week >= 5 or current_date.strftime('%Y-%m-%d') in feriados else "blue"
                    tk.Label(self.scrollable_frame, text=record[2+j], fg=fg_color).grid(row=i+1, column=2+j, padx=10, pady=10)

    def export_pdf(self):
        report_type = self.report_type.get()
        pdf_file = f"reporte_{report_type.lower()}.pdf"
        c = canvas.Canvas(pdf_file, pagesize=landscape(letter) if report_type == "Mes" else letter)
        
        if report_type == "Día":
            records = self.system.get_daily_records()
            headers = ["DNI", "Nombres", "Apellido Paterno", "Apellido Materno", "Hora de Entrada", "Hora de Salida"]
        elif report_type == "Semana":
            records = self.system.get_weekly_records()
            headers = ["DNI", "Nombres Completos", "LU", "MA", "MI", "JU", "VI", "SA", "DO"]
        elif report_type == "Mes":
            month = self.month_var.get()
            if not month:
                messagebox.showerror("Error", "Seleccione un mes")
                return
            
            month = f"2024-{month.strip()}"
            records = self.system.get_monthly_records(month)
            days_in_month = calendar.monthrange(2024, int(month.split('-')[1].strip()))[1]
            headers = ["DNI", "Nombres Completos"] + [str(day) for day in range(1, days_in_month + 1)]
        
        c.drawString(30, 750, f"Reporte de Asistencias ({report_type})")
        x_offset = 30
        y_offset = 700
        for header in headers:
            c.drawString(x_offset, y_offset, header)
            x_offset += 100
        
        y_offset -= 30
        for record in records:
            x_offset = 30
            for value in record:
                c.drawString(x_offset, y_offset, str(value))
                x_offset += 100
            y_offset -= 30
        
        c.save()
        messagebox.showinfo("Exportación", f"Reporte exportado a PDF: {pdf_file}")
    
    def export_excel(self):
        report_type = self.report_type.get()
        excel_file = f"reporte_{report_type.lower()}.xlsx"
        
        if report_type == "Día":
            records = self.system.get_daily_records()
            headers = ["DNI", "Nombres", "Apellido Paterno", "Apellido Materno", "Hora de Entrada", "Hora de Salida"]
        elif report_type == "Semana":
            records = self.system.get_weekly_records()
            headers = ["DNI", "Nombres Completos", "LU", "MA", "MI", "JU", "VI", "SA", "DO"]
        elif report_type == "Mes":
            month = self.month_var.get()
            if not month:
                messagebox.showerror("Error", "Seleccione un mes")
                return
            
            month = f"2024-{month.strip()}"
            records = self.system.get_monthly_records(month)
            days_in_month = calendar.monthrange(2024, int(month.split('-')[1].strip()))[1]
            headers = ["DNI", "Nombres Completos"] + [str(day) for day in range(1, days_in_month + 1)]
        
        df = pd.DataFrame(records, columns=headers)
        df.to_excel(excel_file, index=False)
        messagebox.showinfo("Exportación", f"Reporte exportado a Excel: {excel_file}")

if __name__ == '__main__':
    create_tables()
    root = tk.Tk()
    style = ttk.Style()
    style.configure("My.TFrame", background="gray")
    style.configure("Red.TButton", background="red", foreground="black")
    style.configure("Green.TButton", background="green", foreground="black")
    app = AttendanceApp(root)
    root.mainloop()
