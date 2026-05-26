#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Uso: python forca_utf8.py [diretorio]
# Converte todos os arquivos .py do diretório para UTF-8, mesmo que estejam em latin1/cp1252

def convert_file(path):
    try:
        raw = path.read_bytes()
        try:
            # Tenta decodificar como UTF-8
            raw.decode('utf-8')
            # Já está ok
            return False
        except UnicodeDecodeError:
            # Se falhar, decodifica como latin1/cp1252 e salva como UTF-8
            txt = raw.decode('latin1')
            path.write_text(txt, encoding='utf-8')
            print(f'Convertido: {path}')
            return True
    except Exception as e:
        print(f'Erro ao processar {path}: {e}')
        return False

def main():
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('.')
    for f in pasta.rglob('*.py'):
        convert_file(f)

if __name__ == '__main__':
    main()
