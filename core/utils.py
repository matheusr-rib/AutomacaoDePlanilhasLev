def parse_percentual_br(valor) -> float:
    """
    Converte '8,50', '8.50', '8,50%' → 8.5 (float).
    """
    if valor is None:
        return 0.0

    s = str(valor).strip().replace("%", "").replace(" ", "")
    if not s:
        return 0.0

    s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") > 1 else s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0
