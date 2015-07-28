__version__ = '0.0.1'
__all__ = ['parser']
try:
    from . import *
except ImportError:
    pass  # imports will fail during dependency collection
