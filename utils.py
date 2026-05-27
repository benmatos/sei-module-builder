import re

def to_pascal_case(s: str) -> str:
    if not s: return ""
    return "".join(word[0].upper() + word[1:] for word in re.split(r"[_-]", s) if word)

def to_camel_case(s: str) -> str:
    parts = re.split(r"[_-]", s)
    return parts[0].lower() + "".join(w.capitalize() for w in parts[1:])

TIPO_INFRABANCO_MAP = {
    "varchar(100)":  "InfraBanco::TIPO_TEXTO_CURTO",
    "varchar(255)":  "InfraBanco::TIPO_TEXTO_CURTO",
    "text":          "InfraBanco::TIPO_TEXTO_LONGO",
    "int":           "InfraBanco::TIPO_INTEIRO",
    "bigint":        "InfraBanco::TIPO_INTEIRO",
    "decimal(15,2)": "InfraBanco::TIPO_DECIMAL",
    "date":          "InfraBanco::TIPO_DATA",
    "datetime":      "InfraBanco::TIPO_DATA_HORA",
    "char(1)":       "InfraBanco::TIPO_TEXTO_FIXO",
}

def tipo_infrabanco(tipo: str) -> str:
    return TIPO_INFRABANCO_MAP.get(tipo, "InfraBanco::TIPO_TEXTO_CURTO")

def get_jinja_env(template_dir: str):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    env.filters["pascalcase"] = to_pascal_case
    env.filters["camelcase"] = to_camel_case
    env.filters["tipo_infrabanco"] = tipo_infrabanco
    return env
