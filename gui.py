import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import json
import serial.tools.list_ports
import tempfile
import os
import webbrowser
import subprocess
import sys

import pdfkit

# For OCR extraction:
try:
    from PIL import Image
    import pytesseract
except ImportError:
    pass

from db_handler import (
    get_torque_table,
    insert_torque_table_entry,
    update_torque_table_entry,
    insert_raw_data,
    insert_summary,
    get_all_types,
    get_all_units
)
from serial_reader import read_from_serial, find_fits_in_selected_row, parse_torque_value

BAUD_RATE = 9600

def auto_calculate_allowances(applied_list, tolerance=0.04):
    """Given a list of floats, returns a list of strings formatted as 'low - high'."""
    allowances = []
    for val in applied_list:
        low = val * (1 - tolerance)
        high = val * (1 + tolerance)
        allowances.append(f"{low:.1f} - {high:.1f}")
    return allowances

def suggest_applied_torques(max_torque: float, type_str: str) -> tuple:
    """Returns suggested applied torque values based on max torque and type."""
    if type_str.lower() == "torque multiplier":
        applied1 = max_torque * 0.3
        applied2 = max_torque * 0.2
        applied3 = max_torque * 0.1
    else:
        applied1 = max_torque * 0.95
        applied2 = max_torque * 0.65
        applied3 = max_torque * 0.40
    return round(applied1, 1), round(applied2, 1), round(applied3, 1)

class PlaceholderEntry(tk.Entry):
    """A custom Entry widget that displays placeholder text in grey."""
    def __init__(self, master=None, placeholder="", color="grey", *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = color
        self.default_fg_color = self["fg"] if "fg" in kwargs else "black"
        self.bind("<FocusIn>", self.foc_in)
        self.bind("<FocusOut>", self.foc_out)
        self.put_placeholder()

    def put_placeholder(self):
        if not self.get():
            self.insert(0, self.placeholder)
            self["fg"] = self.placeholder_color

    def foc_in(self, *args):
        if self["fg"] == self.placeholder_color:
            self.delete(0, "end")
            self["fg"] = self.default_fg_color

    def foc_out(self, *args):
        if not self.get():
            self.put_placeholder()

    def set_placeholder(self, text):
        self.placeholder = text
        if not self.get() or self.get() == self.placeholder:
            self.delete(0, "end")
            self.put_placeholder()

class TorqueAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Torque Testing App")
        self.setup_styles()
        self.create_menu()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Test tab
        self.test_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.test_frame, text="Test")
        self.setup_test_tab()

        # Manage tab
        self.manage_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.manage_frame, text="Manage Torque Table")
        self.setup_manage_tab()

        # Export/Template Editor tab
        self.export_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.export_frame, text="Export/Template Editor")
        self.setup_export_tab()

        # Status bar at bottom
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", side="bottom")

        # State and threading
        self.running = False
        self.thread = None
        self.stop_event = threading.Event()
        self.result_queue = queue.Queue()
        self.root.after(100, self.process_queue)
        self.selected_row = None
        self.allowance_counts = {"allowance1": 0, "allowance2": 0, "allowance3": 0}
        self.results_by_range = {}
        self.customer_info = {}

    def setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TButton", font=("Helvetica", 10, "bold"))
        style.configure("TLabel", font=("Helvetica", 10))
        style.configure("Treeview", rowheight=25, font=("Helvetica", 10))
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"))

    def create_menu(self):
        # Create a simple menu bar for the main window.
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu_bar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", "Torque Testing App\nVersion 1.0"))
        menu_bar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu_bar)

    # ---------------- Test Tab ----------------
    def setup_test_tab(self):
        # Use a grid layout for the selection frame.
        selection_frame = ttk.Frame(self.test_frame)
        selection_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        selection_frame.columnconfigure(1, weight=1)

        ttk.Label(selection_frame, text="Select Max Torque:").grid(row=0, column=0, sticky="w")
        self.torque_var = tk.StringVar()
        self.torque_combo = ttk.Combobox(selection_frame, textvariable=self.torque_var, state="readonly")
        self.torque_combo.grid(row=0, column=1, padx=5, sticky="ew")

        ttk.Label(selection_frame, text="Select Serial Port:").grid(row=1, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(selection_frame, textvariable=self.port_var, state="readonly")
        self.port_combo['values'] = self.get_serial_ports()
        self.port_combo.grid(row=1, column=1, padx=5, sticky="ew")

        # Place the Upload Customer Info button here
        upload_info_btn = ttk.Button(selection_frame, text="Upload Customer Info", command=self.upload_customer_info)
        upload_info_btn.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        self.start_button = ttk.Button(selection_frame, text="Start Test", command=self.start_test)
        self.start_button.grid(row=3, column=0, pady=10, padx=5)
        self.stop_button = ttk.Button(selection_frame, text="Stop Test", command=self.stop_test, state="disabled")
        self.stop_button.grid(row=3, column=1, pady=10, padx=5)

        summary_frame = ttk.Frame(self.test_frame)
        summary_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.test_frame.rowconfigure(1, weight=1)
        self.test_frame.columnconfigure(0, weight=1)

        columns = ("AppliedTorque", "Allowance", "Test1", "Test2", "Test3", "Test4", "Test5")
        self.tree = ttk.Treeview(summary_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
        self.tree.pack(fill="both", expand=True)
        self.refresh_torque_dropdown()
        self.torque_combo.bind("<<ComboboxSelected>>", self.on_torque_combo_selected)

    def upload_customer_info(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.bmp"), ("All files", "*.*")])
        if not file_path:
            return
        try:
            image = Image.open(file_path)
            ocr_text = pytesseract.image_to_string(image)
        except Exception as e:
            messagebox.showerror("OCR Error", f"Error processing image: {e}")
            return
        self.customer_info = {}
        for line in ocr_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) == 2:
                key = parts[0].strip().lower()
                value = parts[1].strip()
                if "customer" in key:
                    self.customer_info["customer"] = value
                elif "email" in key:
                    self.customer_info["email"] = value
                elif "contact" in key:
                    self.customer_info["contact"] = value
                elif "brand" in key:
                    self.customer_info["brand"] = value
                elif "model" in key:
                    self.customer_info["model"] = value
                elif "unit" in key:
                    self.customer_info["unit"] = value
                elif "serial" in key:
                    self.customer_info["serial"] = value
        if self.customer_info:
            self.status_var.set("Customer info uploaded.")
        else:
            self.status_var.set("No recognizable customer info found.")

    def on_torque_combo_selected(self, event):
        idx = self.torque_combo.current()
        if idx < 0:
            return
        self.selected_row = self.torque_table[idx]
        self.allowance_counts = {"allowance1": 0, "allowance2": 0, "allowance3": 0}
        self.results_by_range = {}
        self.display_pre_test_rows()

    def display_pre_test_rows(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.selected_row:
            return
        try:
            arr = json.loads(self.selected_row["applied_torq"])
        except (json.JSONDecodeError, TypeError):
            arr = [0, 0, 0]
        for i in range(1, 4):
            allow_str = self.selected_row[f"allowance{i}"]
            applied_val = arr[i-1] if i-1 < len(arr) else 0
            row_values = [applied_val, allow_str, "", "", "", "", ""]
            self.tree.insert("", "end", values=row_values)

    def refresh_torque_dropdown(self):
        self.torque_table = get_torque_table()
        self.torque_combo['values'] = [
            f"{row['max_torque']} {row['unit']} - {row['type']}" for row in self.torque_table
        ]
        if self.torque_combo['values']:
            self.torque_combo.current(0)
            self.selected_row = self.torque_table[0]
            self.display_pre_test_rows()

    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def start_test(self):
        if not self.port_var.get():
            messagebox.showerror("Error", "No serial port selected.")
            return
        if not self.torque_combo.get():
            messagebox.showerror("Error", "No torque entry selected.")
            return
        idx = self.torque_combo.current()
        if idx >= 0:
            self.selected_row = self.torque_table[idx]
        self.display_pre_test_rows()
        self.running = True
        self.stop_event.clear()
        self.allowance_counts = {"allowance1": 0, "allowance2": 0, "allowance3": 0}
        self.results_by_range = {}
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.thread = threading.Thread(target=self.run_serial, daemon=True)
        self.thread.start()
        self.status_var.set("Test started.")

    def stop_test(self):
        self.stop_event.set()
        self.running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        if self.thread is not None:
            self.thread.join(timeout=2)
        self.update_summary_tree()
        self.status_var.set("Test stopped and summary updated.")
        messagebox.showinfo("Test Stopped", "Test stopped and summary updated.")

    def run_serial(self):
        port = self.port_var.get()
        try:
            read_from_serial(port, BAUD_RATE, self.serial_callback, self.stop_event)
        except Exception as e:
            print("Error in serial reading:", e)

    def serial_callback(self, target_torque):
        if not self.running or not self.selected_row:
            return
        fits = find_fits_in_selected_row(target_torque, self.selected_row)
        if fits:
            self.result_queue.put((target_torque, fits))

    def process_queue(self):
        try:
            while True:
                target_torque, fits = self.result_queue.get_nowait()
                for fit in fits:
                    allowance_key = f"allowance{fit['allowance_index']}"
                    if self.allowance_counts[allowance_key] < 5:
                        insert_raw_data(target_torque, self.selected_row["id"], allowance_key, fit['range_str'])
                        self.allowance_counts[allowance_key] += 1
                        if fit['range_str'] not in self.results_by_range:
                            self.results_by_range[fit['range_str']] = []
                        self.results_by_range[fit['range_str']].append(target_torque)
                self.update_summary_tree()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def update_summary_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.selected_row:
            return
        try:
            arr = json.loads(self.selected_row["applied_torq"])
        except (json.JSONDecodeError, TypeError):
            arr = [0, 0, 0]
        for i in range(1, 4):
            allow_str = self.selected_row[f"allowance{i}"]
            applied_val = arr[i-1] if i-1 < len(arr) else 0.0
            test_values = self.results_by_range.get(allow_str, [])
            while len(test_values) < 5:
                test_values.append("")
            row_values = [
                applied_val, allow_str,
                test_values[0],
                test_values[1],
                test_values[2],
                test_values[3],
                test_values[4]
            ]
            self.tree.insert("", "end", values=row_values)
            actual_numbers = [v for v in test_values if isinstance(v, float)]
            insert_summary(allow_str, actual_numbers)

    # ---------------- Manage Tab ----------------
    def setup_manage_tab(self):
        bottom_frame = ttk.Frame(self.manage_frame)
        bottom_frame.pack(fill="both", expand=True, padx=5, pady=5)
        ttk.Label(bottom_frame, text="Max Torque:").grid(row=0, column=0, sticky="w")
        self.entry_max_torque = ttk.Entry(bottom_frame, width=10)
        self.entry_max_torque.grid(row=0, column=1, padx=5, pady=5)
        self.entry_max_torque.bind("<KeyRelease>", self.update_applied_suggestions)
        ttk.Label(bottom_frame, text="Type:").grid(row=0, column=2, sticky="w")
        self.type_var = tk.StringVar()
        self.type_combo = ttk.Combobox(bottom_frame, textvariable=self.type_var, state="readonly", width=15)
        self.type_combo.grid(row=0, column=3, padx=5, pady=5)
        self.type_combo.bind("<<ComboboxSelected>>", self.update_applied_suggestions)
        ttk.Label(bottom_frame, text="Unit:").grid(row=0, column=4, sticky="w")
        self.unit_var = tk.StringVar()
        self.unit_combo = ttk.Combobox(bottom_frame, textvariable=self.unit_var, state="readonly", width=10)
        self.unit_combo.grid(row=0, column=5, padx=5, pady=5)
        self.refresh_type_and_unit_lists()
        ttk.Label(bottom_frame, text="Applied Torq #1:").grid(row=1, column=0, sticky="w")
        self.entry_applied_1 = PlaceholderEntry(bottom_frame, placeholder="", width=10)
        self.entry_applied_1.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(bottom_frame, text="Applied Torq #2:").grid(row=1, column=2, sticky="w")
        self.entry_applied_2 = PlaceholderEntry(bottom_frame, placeholder="", width=10)
        self.entry_applied_2.grid(row=1, column=3, padx=5, pady=5)
        ttk.Label(bottom_frame, text="Applied Torq #3:").grid(row=1, column=4, sticky="w")
        self.entry_applied_3 = PlaceholderEntry(bottom_frame, placeholder="", width=10)
        self.entry_applied_3.grid(row=1, column=5, padx=5, pady=5)
        self.add_button = ttk.Button(bottom_frame, text="Add Entry", command=self.add_torque_entry)
        self.add_button.grid(row=2, column=0, pady=10, padx=5)
        self.edit_button = ttk.Button(bottom_frame, text="Edit Selected", command=self.load_selected_entry)
        self.edit_button.grid(row=2, column=1, pady=10, padx=5)
        self.update_button = ttk.Button(bottom_frame, text="Update Entry", command=self.update_torque_entry)
        self.update_button.grid(row=2, column=2, pady=10, padx=5)
        top_frame = ttk.Frame(self.manage_frame)
        top_frame.pack(fill="both", expand=True, padx=5, pady=5)
        columns = ("ID", "Max Torque", "Type", "Unit", "Applied Torq", "Allowance1", "Allowance2", "Allowance3")
        self.manage_tree = ttk.Treeview(top_frame, columns=columns, show="headings")
        for col in columns:
            self.manage_tree.heading(col, text=col)
            self.manage_tree.column(col, width=100)
        self.manage_tree.pack(fill="both", expand=True)
        self.refresh_manage_tree()

    def update_applied_suggestions(self, event):
        try:
            max_torque = float(self.entry_max_torque.get())
        except ValueError:
            return
        type_str = self.type_var.get().strip() if self.type_var.get() else "Wrench"
        applied1, applied2, applied3 = suggest_applied_torques(max_torque, type_str)
        if not self.entry_applied_1.get() or self.entry_applied_1.get() == self.entry_applied_1.placeholder:
            self.entry_applied_1.set_placeholder(str(applied1))
        if not self.entry_applied_2.get() or self.entry_applied_2.get() == self.entry_applied_2.placeholder:
            self.entry_applied_2.set_placeholder(str(applied2))
        if not self.entry_applied_3.get() or self.entry_applied_3.get() == self.entry_applied_3.placeholder:
            self.entry_applied_3.set_placeholder(str(applied3))

    def refresh_type_and_unit_lists(self):
        self.type_combo['values'] = get_all_types()
        self.unit_combo['values'] = get_all_units()
        if self.type_combo['values']:
            self.type_combo.current(0)
        if self.unit_combo['values']:
            self.unit_combo.current(0)

    def refresh_manage_tree(self):
        for item in self.manage_tree.get_children():
            self.manage_tree.delete(item)
        table_data = get_torque_table()
        for row in table_data:
            self.manage_tree.insert("", "end", values=(
                row["id"],
                row["max_torque"],
                row["type"],
                row["unit"],
                row["applied_torq"],
                row["allowance1"],
                row["allowance2"],
                row["allowance3"]
            ))

    def add_torque_entry(self):
        try:
            max_torque = float(self.entry_max_torque.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid Max Torque value.")
            return
        type_str = self.type_var.get().strip()
        unit_str = self.unit_var.get().strip()
        if not type_str or not unit_str:
            messagebox.showerror("Error", "Please select a Type and Unit.")
            return
        try:
            val1 = float(self.entry_applied_1.get())
            val2 = float(self.entry_applied_2.get())
            val3 = float(self.entry_applied_3.get())
        except ValueError:
            messagebox.showerror("Error", "Applied Torq fields must be numeric.")
            return
        applied_list = [val1, val2, val3]
        allowance_vals = auto_calculate_allowances(applied_list, tolerance=0.04)
        allowance1, allowance2, allowance3 = allowance_vals
        applied_str = json.dumps(applied_list)
        insert_torque_table_entry(max_torque, type_str, unit_str, applied_str, allowance1, allowance2, allowance3)
        messagebox.showinfo("Success", "New entry added to torque table.")
        self.refresh_manage_tree()
        self.refresh_torque_dropdown()
        self.refresh_type_and_unit_lists()

    def load_selected_entry(self):
        selection = self.manage_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a row to edit.")
            return
        item_id = selection[0]
        row_values = self.manage_tree.item(item_id, "values")
        self.current_edit_id = int(row_values[0])
        self.entry_max_torque.delete(0, tk.END)
        self.entry_max_torque.insert(0, row_values[1])
        self.type_var.set(row_values[2])
        self.unit_var.set(row_values[3])
        applied_str = row_values[4]
        try:
            arr = json.loads(applied_str)
            if len(arr) == 3:
                self.entry_applied_1.delete(0, tk.END)
                self.entry_applied_1.insert(0, arr[0])
                self.entry_applied_2.delete(0, tk.END)
                self.entry_applied_2.insert(0, arr[1])
                self.entry_applied_3.delete(0, tk.END)
                self.entry_applied_3.insert(0, arr[2])
            else:
                raise ValueError
        except Exception:
            self.entry_applied_1.delete(0, tk.END)
            self.entry_applied_2.delete(0, tk.END)
            self.entry_applied_3.delete(0, tk.END)

    def update_torque_entry(self):
        if not hasattr(self, "current_edit_id"):
            messagebox.showerror("Error", "No entry is loaded for editing. Use 'Edit Selected' first.")
            return
        try:
            max_torque = float(self.entry_max_torque.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid Max Torque value.")
            return
        type_str = self.type_var.get().strip()
        unit_str = self.unit_var.get().strip()
        if not type_str or not unit_str:
            messagebox.showerror("Error", "Please select a Type and Unit.")
            return
        try:
            val1 = float(self.entry_applied_1.get())
            val2 = float(self.entry_applied_2.get())
            val3 = float(self.entry_applied_3.get())
        except ValueError:
            messagebox.showerror("Error", "Applied Torq fields must be numeric.")
            return
        applied_list = [val1, val2, val3]
        allowance_vals = auto_calculate_allowances(applied_list, tolerance=0.04)
        allowance1, allowance2, allowance3 = allowance_vals
        applied_str = json.dumps(applied_list)
        update_torque_table_entry(
            entry_id=self.current_edit_id,
            max_torque=max_torque,
            type_str=type_str,
            unit=unit_str,
            applied_torq=applied_str,
            allowance1=allowance1,
            allowance2=allowance2,
            allowance3=allowance3
        )
        messagebox.showinfo("Success", "Entry updated successfully.")
        self.refresh_manage_tree()
        self.refresh_torque_dropdown()
        self.refresh_type_and_unit_lists()

    # ---------------- Export/Template Editor Tab ----------------
    def setup_export_tab(self):
        editor_frame = ttk.Frame(self.export_frame)
        editor_frame.pack(fill="x", padx=5, pady=5)
        open_editor_btn = ttk.Button(editor_frame, text="Open Template Editor", command=self.open_template_editor)
        open_editor_btn.grid(row=0, column=0, padx=5, pady=5)
        preview_pdf_btn = ttk.Button(editor_frame, text="Preview PDF", command=self.preview_pdf)
        preview_pdf_btn.grid(row=0, column=1, padx=5, pady=5)
        export_pdf_btn = ttk.Button(editor_frame, text="Export PDF", command=self.export_pdf)
        export_pdf_btn.grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(self.export_frame, text="The Template Editor will open in a separate window.").pack(pady=5)

    def open_template_editor(self):
        subprocess.Popen([sys.executable, "template_editor.py"])

    def get_template_content(self):
        try:
            with open("template_saved.html", "r", encoding="utf-8") as f:
                content = f.read()
                return content
        except FileNotFoundError:
            messagebox.showwarning("Template Not Found", "No template file found. Please open the Template Editor and save your template.")
            return None

    def generate_rows_html(self):
        rows_html = ""
        for child in self.tree.get_children():
            values = self.tree.item(child, "values")
            row_html = "<tr>" + "".join(f"<td>{v}</td>" for v in values) + "</tr>"
            rows_html += row_html
        return rows_html

    def export_pdf(self):
        template_content = self.get_template_content()
        if template_content is None:
            return
        rows_html = self.generate_rows_html()
        final_html = template_content.replace("{{ rows }}", rows_html)
        if self.customer_info:
            for key, value in self.customer_info.items():
                final_html = final_html.replace("{{ " + key + " }}", value)
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if not file_path:
            return
        try:
            pdfkit.from_string(final_html, file_path)
            messagebox.showinfo("Export PDF", f"PDF exported successfully to {file_path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred while exporting PDF:\n{e}")

    def preview_pdf(self):
        template_content = self.get_template_content()
        if template_content is None:
            return
        rows_html = self.generate_rows_html()
        final_html = template_content.replace("{{ rows }}", rows_html)
        if self.customer_info:
            for key, value in self.customer_info.items():
                final_html = final_html.replace("{{ " + key + " }}", value)
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.close()
            pdfkit.from_string(final_html, tmp.name)
            webbrowser.open_new(tmp.name)
        except Exception as e:
            messagebox.showerror("Preview Error", f"An error occurred while previewing PDF:\n{e}")

def run_app():
    root = tk.Tk()
    app = TorqueAppGUI(root)
    root.mainloop()
