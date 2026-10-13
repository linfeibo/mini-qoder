import tkinter as tk
from tkinter import font

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("简易计算器")
        self.root.geometry("320x450")
        self.root.resizable(False, False)
        
        # 字体
        self.display_font = font.Font(family="Arial", size=20, weight="bold")
        self.button_font = font.Font(family="Arial", size=14)
        
        # 显示屏
        self.display = tk.Entry(
            root, font=self.display_font, justify="right", 
            bd=10, relief="sunken", state="readonly"
        )
        self.display.grid(row=0, column=0, columnspan=4, sticky="ew", padx=10, pady=10)
        
        # 内部状态
        self.current = "0"
        self.previous = ""
        self.operator = ""
        self.should_reset_display = False
        
        # 按钮布局
        buttons = [
            ('C', 1, 0), ('←', 1, 1), ('%', 1, 2), ('÷', 1, 3),
            ('7', 2, 0), ('8', 2, 1), ('9', 2, 2), ('×', 2, 3),
            ('4', 3, 0), ('5', 3, 1), ('6', 3, 2), ('−', 3, 3),
            ('1', 4, 0), ('2', 4, 1), ('3', 4, 2), ('+', 4, 3),
            ('±', 5, 0), ('0', 5, 1), ('.', 5, 2), ('=', 5, 3),
        ]
        
        for (text, row, col) in buttons:
            btn = tk.Button(
                root, text=text, font=self.button_font,
                command=lambda t=text: self.on_button_click(t),
                width=5, height=2, bd=3
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            
        # 配置网格权重，使按钮均匀拉伸
        for i in range(4):
            root.grid_columnconfigure(i, weight=1)
        for i in range(1, 6):
            root.grid_rowconfigure(i, weight=1)

    def on_button_click(self, char):
        if char == 'C':
            self.current = "0"
            self.previous = ""
            self.operator = ""
            self.should_reset_display = False
        elif char == '←':
            if len(self.current) > 1:
                self.current = self.current[:-1]
            else:
                self.current = "0"
        elif char == '±':
            if self.current != "0":
                if self.current.startswith("-"):
                    self.current = self.current[1:]
                else:
                    self.current = "-" + self.current
        elif char == '%':
            try:
                val = float(self.current)
                self.current = str(val / 100)
                if self.current.endswith(".0"):
                    self.current = self.current[:-2]
            except:
                self.current = "Error"
        elif char in ['+', '−', '×', '÷']:
            if self.operator and not self.should_reset_display:
                self.calculate()
            self.previous = self.current
            self.operator = char
            self.should_reset_display = True
        elif char == '=':
            self.calculate()
        elif char == '.':
            if '.' not in self.current:
                self.current += '.'
        else:  # 数字
            if self.should_reset_display:
                self.current = "0"
                self.should_reset_display = False
            if self.current == "0":
                self.current = char
            else:
                self.current += char

        self.update_display()

    def calculate(self):
        try:
            prev = float(self.previous)
            curr = float(self.current)
            result = 0
            if self.operator == '+':
                result = prev + curr
            elif self.operator == '−':
                result = prev - curr
            elif self.operator == '×':
                result = prev * curr
            elif self.operator == '÷':
                if curr == 0:
                    self.current = "Error"
                    return
                result = prev / curr
            
            # 格式化结果：去除不必要的 .0
            self.current = str(result)
            if '.' in self.current:
                self.current = self.current.rstrip('0').rstrip('.')
            if self.current == "":
                self.current = "0"
                
        except Exception:
            self.current = "Error"
        finally:
            self.operator = ""
            self.previous = ""

    def update_display(self):
        # 限制显示长度，避免溢出
        display_text = self.current
        if len(display_text) > 14:
            display_text = display_text[:11] + "..."
        self.display.config(state="normal")
        self.display.delete(0, tk.END)
        self.display.insert(0, display_text)
        self.display.config(state="readonly")


if __name__ == "__main__":
    root = tk.Tk()
    app = Calculator(root)
    root.mainloop()
