"""Look up the May 9 puzzle content."""
import json, os

for fname in sorted(os.listdir('relink/save-data')):
    if not fname.startswith('l') or not fname.endswith('.json'):
        continue
    with open(os.path.join('relink/save-data', fname)) as f:
        data = json.load(f)
    if data.get('canonicalId') == 'mouaw3d1-g9ugg95':
        print(f"File: {fname}")
        print(f"Date: {data.get('date', 'no date')}")
        board = data.get('board', {})
        print(f"Phase 2 tile count: {board.get('phase2TileCount', '?')}")
        print()
        for i, row in enumerate(data.get('rows', [])):
            tiles = [t['text'] for t in row['tiles']]
            impostor_idx = [j for j, t in enumerate(row['tiles']) if t.get('isImpostor')]
            group_name = row.get('group', {}).get('name', '?')
            print(f"  Row {i}: {tiles}")
            print(f"    Connection: {group_name}, Impostor at index: {impostor_idx}")
        print()
        relink = data.get('relink', {})
        print(f"  Relink connection: {relink.get('connection', '?')}")
        print(f"  Relink answer tiles: {relink.get('answer', '?')}")
        break
