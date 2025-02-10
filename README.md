# 🛠 Torque Wrench Testing App

## 📌 Overview
The **Torque Wrench Testing App** is a Python-based GUI application designed for testing and managing torque wrench calibration data. It enables users to:
- Collect and store torque test data
- Manage a database of torque wrenches and their applied torques
- Process and analyze serial input from torque measurement devices
- Generate and export test reports in **PDF format** using customizable templates

---

## 🛠 Installation
### **1. Clone the Repository**
```sh
git clone https://github.com/your-username/Torque_Wrench_Testing_App.git
cd Torque_Wrench_Testing_App
```

### **2. Install Dependencies**
Ensure Python is installed (`3.7+` recommended). Then run:
```sh
pip install -r requirements.txt
```

### **3. Run the Application**
```sh
python main.py
```

---

## 📡 Serial Device Setup
Ensure your **torque wrench** is connected to the **serial port**.
- Select the correct **COM port** in the GUI.
- Click **Start Test** to begin data collection.

---

## 📄 Report Customization
- Open the **Template Editor** from the GUI.
- Edit the report template (`editor.html`).
- Save and use it to generate PDFs.

---

## 📜 Example Output (Test Report)
```html
<h1>Torque Test Report</h1>
<p>Customer: {{ customer }}</p>
<p>Model: {{ model }}</p>
<table>
  <tr>
    <th>Applied Torque</th>
    <th>Allowance</th>
    <th>Test #1</th>
    <th>Test #2</th>
    <th>Test #3</th>
  </tr>
  {{ rows }}
</table>
```

---

## 🛠 Dependencies
This project requires the following Python packages:
- `tkinter` (for the GUI)
- `sqlite3` (for the database)
- `pyserial` (for reading torque data)
- `pdfkit` (for exporting reports)
- `pytesseract` & `PIL` (for optional OCR functionality)

Install missing dependencies with:
```sh
pip install tk sqlite3 pyserial pdfkit pillow pytesseract
```

---

## 📜 License
This project is licensed under the **MIT License**. Feel free to modify and improve it.

## 💡 Future Improvements
- Implement **real-time graphical visualization** of torque test data.
- Add **user authentication** for restricted access.
- Improve **OCR accuracy** for customer data extraction.
