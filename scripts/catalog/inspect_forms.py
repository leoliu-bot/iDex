"""Cache pinned form tables and inspect source coverage before implementation."""
import concurrent.futures
import csv
import io
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_national_catalog import download, CACHE, ROOT

lock = json.loads((ROOT / 'scripts/catalog/upstream-lock.json').read_text())
files = ['pokemon_forms.csv', 'pokemon_form_names.csv', 'pokemon_form_generations.csv',
         'pokemon_form_types.csv', 'version_groups.csv', 'pokemon_form_pokeathlon_stats.csv']

def table(name):
    url = f'https://raw.githubusercontent.com/PokeAPI/pokeapi/{lock["data"]}/data/v2/csv/{name}'
    return name, list(csv.DictReader(io.StringIO(download(url, CACHE / lock['data'] / name).decode())))

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        tables = dict(pool.map(table, files))
    pokemon = list(csv.DictReader((CACHE / lock['data'] / 'pokemon.csv').open()))
    forms = tables['pokemon_forms.csv']
    ids = {int(p['id']): p for p in pokemon}
    output = ROOT / 'artifacts/forms'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'tables.json').write_text(json.dumps(tables), encoding='utf-8')
    print(json.dumps({'pokemon': len(pokemon), 'forms': len(forms), 'alternateForms': sum(1 for f in forms if ids[int(f['pokemon_id'])]['is_default'] != '1' or f['is_default'] != '1'),
                      'examples': [f for f in forms if any(s in f['identifier'] for s in ['ninetales', 'kyurem', 'necrozma', 'calyrex'])]}, indent=2))
