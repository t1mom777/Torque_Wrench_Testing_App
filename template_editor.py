import webview
import tkinter.filedialog as fd

class EditorAPI:
    def open_file(self):
        path = fd.askopenfilename(filetypes=[("HTML files", "*.html"), ("All files", "*.*")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""
    
    def save_template(self, content):
        with open("template_saved.html", "w", encoding="utf-8") as f:
            f.write(content)
        return "Template saved successfully."
    
    def save_template_as(self, content):
        path = fd.asksaveasfilename(filetypes=[("HTML files", "*.html"), ("All files", "*.*")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Template saved as {path}"
        return "Save cancelled."

def main():
    api = EditorAPI()
    window = webview.create_window("Template Editor", "editor.html", width=800, height=600, js_api=api)
    webview.start(debug=False)
    content = window.evaluate_js("getContent();")
    if content:
        with open("template_saved.html", "w", encoding="utf-8") as f:
            f.write(content)

if __name__ == '__main__':
    main()
