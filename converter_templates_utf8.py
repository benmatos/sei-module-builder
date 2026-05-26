from pathlib import Path

dir_templates = Path(__file__).parent / 'templates' / 'modulo'

for f in dir_templates.glob('*.j2'):
    try:
        raw = f.read_bytes()
        try:
            # Tenta decodificar como UTF-8
            raw.decode('utf-8')
        except UnicodeDecodeError:
            # Se falhar, decodifica como latin1 e salva como UTF-8
            txt = raw.decode('latin1')
            f.write_text(txt, encoding='utf-8')
            print(f'Convertido: {f.name}')
    except Exception as e:
        print(f'Erro em {f.name}: {e}')
