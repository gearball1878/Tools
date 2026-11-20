import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from symbol_wizard.app import main

if __name__ == '__main__':
    main()
