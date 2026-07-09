import sys
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.ui.pet_window import PetWindow

def test():
    app = QApplication(sys.argv)
    
    start = time.time()
    w = PetWindow(opencode_enabled=False, initial_state={"first_run_done": True})
    print(f"Init took {time.time() - start:.2f}s")
    
    start = time.time()
    del w
    print(f"Del took {time.time() - start:.2f}s")

if __name__ == "__main__":
    test()
