import re
from datetime import datetime


def log_info(msg: str):
    agora = datetime.now().strftime("%H:%M:%S")
    print(f"[{agora}] {msg}")


def parse_percentual_br(valor) -> float:
    if valor is None:
        return 0.0

    s = str(valor).strip().replace("%", "").replace(" ", "")
    if not s:
        return 0.0

    s = (
        s.replace(".", "").replace(",", ".")
        if s.count(",") == 1 and s.count(".") > 1
        else s.replace(",", ".")
    )

    try:
        return float(s)
    except ValueError:
        return 0.0


def normalizar_parc_atual(valor) -> str:
    """
    Normaliza 'Parc. Atual' para comparação e identidade:
    - "120" -> "120"
    - "120-120" -> "120"
    - "120 A 120" -> "120"
    - "120/120" -> "120"
    - "96-120" -> "96-120"
    """
    if valor is None:
        return ""

    s = str(valor).strip().upper()
    if not s:
        return ""

    nums = re.findall(r"\d+", s)
    if not nums:
        return ""

    if len(nums) == 1:
        return nums[0]

    ini, fim = nums[0], nums[1]
    if ini == fim:
        return ini

    return f"{ini}-{fim}"
