"""Ponto de entrada do executável (o pacote usa imports relativos, então o EXE chama main daqui)."""
import sys

from redblack.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
