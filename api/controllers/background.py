# api/controllers/background.py
from __future__ import annotations

import threading
from typing import Callable, Any


def executar_em_background(fn: Callable[..., Any], *args, **kwargs) -> None:
    """
    Dispara uma função em uma thread daemon (background).
    """
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
    t.start()
