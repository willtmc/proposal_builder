import tkinter as tk
from tkinter import filedialog
import os

def select_data_folder():
    # Create a root window but hide it
    root = tk.Tk()
    root.withdraw()
    
    folder_path = filedialog.askdirectory(
        title='Select Data Folder',
        initialdir=os.path.expanduser('~')  # Start in home directory
    )
    root.destroy()
    return folder_path 