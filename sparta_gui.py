#!/usr/bin/env python3
"""
Top-level launcher: python sparta_gui.py
(or double-click the built .app)
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from gui.__main__ import main

if __name__ == "__main__":
    main()
