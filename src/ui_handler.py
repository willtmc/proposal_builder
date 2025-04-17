import tkinter as tk
from tkinter import filedialog
import os

def select_data_folder():
    # Create a root window but hide it
    root = tk.Tk()
    root.withdraw()
    
    folder_path = filedialog.askdirectory(
        title='Select Data Folder',
        initialdir='/Users/willmclemore/McLemore Auction Dropbox/MAC Deals'  # Default folder for user
    )
    root.destroy()
    return folder_path 