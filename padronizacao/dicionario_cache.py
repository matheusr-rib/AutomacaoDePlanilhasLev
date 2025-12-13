# padronizacao/dicionario_cache.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class DicionarioCache:
    """Cache persistido em JSON + dict em memória.

    - Carrega 1x no início
    - Lookup O(1)
    - Escrita rara (apenas quando adicionamos novas chaves)
    - Por padrão, NÃO sobrescreve chaves existentes (append-only)
      * para sobrescrever (ex.: correção via 'promover_padroes'), use overwrite=True no set()
    """

    def __init__(self, path_json: Path):
        self.path = path_json
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = self._carregar()

    def _carregar(self) -> Dict[str, Any]:
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception:
                # Se o JSON estiver corrompido, não explode a automação.
                return {}
        return {}

    def __contains__(self, chave: str) -> bool:
        return chave in self._cache

    def get(self, chave: str) -> Optional[Any]:
        return self._cache.get(chave)

    def set(self, chave: str, valor: Any, overwrite: bool = False) -> None:
        if not chave:
            return
        if overwrite or chave not in self._cache:
            self._cache[chave] = valor

    def salvar(self) -> None:
        # escrita atômica: evita corromper o JSON se cair energia/crash no meio
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    @property
    def tamanho(self) -> int:
        return len(self._cache)
