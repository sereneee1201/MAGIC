import json
import math
import os
from collections import deque
from typing import Dict, Any, List, Tuple
import matplotlib.pyplot as plt

import numpy as np
from scipy.ndimage import binary_erosion


def load_scene(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_portal_regions(scene: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Return list of (region_name, portal_object_name) for all objects with is_portal==True."""
    regions = scene.get('scene', {}).get('regions', {})
    connections = scene.get('scene', {}).get('connections', {})
    res = []
    for rname, rdata in regions.items():
        objs = rdata.get('objects', {})
        for oname, o in objs.items():
            if isinstance(o, dict) and o.get('is_portal', False):
                res.append((rname, oname))

    for cname, conn in connections.items():
        if isinstance(conn, dict) and 'obj' in conn and (cname.startswith('door') or conn['obj'].get('is_portal', False)):
            obj = conn['obj']
            if not isinstance(obj, dict):
                continue
            region_a = conn.get('region_a')
            region_b = conn.get('region_b')
            if region_b == "__outside__" or cname.startswith('window'):
                res.append((region_a, cname))
    return res

def region_bounds(region: Dict[str, Any]) -> Tuple[float, float, float, float]:
    shape = region['shape']
    min_x = float(shape['min_vertex']['x'])
    min_z = float(shape['min_vertex']['y'])
    max_x = float(shape['max_vertex']['x'])
    max_z = float(shape['max_vertex']['y'])
    return min_x, min_z, max_x, max_z

def extract_objects(region: Dict[str, Any]) -> List[Dict[str, Any]]:
    objs_out = []
    for oname, o in region.get('objects', {}).items():
        if not isinstance(o, dict):
            continue
        cat = (o.get('category') or '').lower()
        dims = o.get('dimensions', {})
        pos = o.get('position')

        if isinstance(pos, list) and pos:
            pos0 = pos[0]
        elif isinstance(pos, dict):
            pos0 = pos
        else:
            pos0 = {'x': None, 'y': None, 'z': None}
        objs_out.append({
            'name': oname,
            'category': cat,
            'is_portal': bool(o.get('is_portal', False)),
            'hanged_on_wall': bool(o.get('hanged_on_wall', False)),
            'hanged_from_ceiling': bool(o.get('hanged_from_ceiling', False)),
            'width': float(dims.get('width', 0.0)),
            'depth': float(dims.get('depth', 0.0)),
            'px': pos0.get('x', None),
            'pz': pos0.get('z', None),
        })
    return objs_out

def extract_connections(connections: Dict[str, Any], objs_out) -> List[Dict[str, Any]]:

    # door objects from connections
    for cname, conn in connections.items():
        obj = conn.get('obj', {})
        dims = obj.get('dimensions', {})
        pos = obj.get('position', [{}])[0]
        cat = (obj.get('category') or '').lower()

        objs_out.append({
            'name': cname,
            'category': cat,
            'is_portal': bool(obj.get('is_portal', False)),
            'hanged_on_wall': bool(obj.get('hanged_on_wall', False)),
            'hanged_from_ceiling': bool(obj.get('hanged_from_ceiling', False)),
            'width': float(dims.get('width', 0.0)),
            'depth': float(dims.get('depth', 0.0)),
            'px': pos.get('x'),
            'pz': pos.get('z'),
        })

    return objs_out

def build_grid(min_x: float, min_z: float, max_x: float, max_z: float, cell_size: float) -> Tuple[int, int]:
    cols = max(1, math.ceil((max_x - min_x)/cell_size))
    rows = max(1, math.ceil((max_z - min_z)/cell_size))
    return rows, cols

def mark_blocked(walkable: List[List[bool]], objects: List[Dict[str, Any]],
                 min_x: float, min_z: float, cell_size: float) -> None:
    # rugs/mats as walkable surfaces, ignore ceiling-hanged objects for blocking
    def is_walkable_surface(cat: str) -> bool:
        cat = cat.lower()
        return (
            'floor' in cat or
            'flooring' in cat or
            cat in {'rug', 'carpet', 'mat', 'tile', 'tiles'}
        )
    
    rows = len(walkable)
    cols = len(walkable[0])

    for o in objects:
        if o['hanged_from_ceiling']:
            continue
        if is_walkable_surface(o['category']):
            continue
        if o['is_portal']:
            continue
        w = o['width']; d = o['depth']
        cx = o['px']; cz = o['pz']
        if (w <= 0 or d <= 0 or cx is None or cz is None):
            continue
        fx0 = cx - w/2.0; fx1 = cx + w/2.0
        fz0 = cz - d/2.0; fz1 = cz + d/2.0
        c0 = max(0, int(math.floor((fx0 - min_x)/cell_size)))
        c1 = min(cols, int(math.ceil((fx1 - min_x)/cell_size)))
        r0 = max(0, int(math.floor((fz0 - min_z)/cell_size)))
        r1 = min(rows, int(math.ceil((fz1 - min_z)/cell_size)))
        for r in range(r0, r1):
            for c in range(c0, c1):
                walkable[r][c] = False

def to_grid(x: float, z: float, min_x: float, min_z: float, cell_size: float) -> Tuple[int, int]:
    gx = int(math.floor((x - min_x)/cell_size)) # row
    gz = int(math.floor((z - min_z)/cell_size)) # col
    return gz, gx

def flood_fill(walkable: List[List[bool]], start_rc: Tuple[int, int]):
    rows, cols = len(walkable), len(walkable[0])
    r0, c0 = start_rc
    visited = [[False for _ in range(cols)] for __ in range(rows)]
    q = deque()
    visited_count = 0
    if 0 <= r0 < rows and 0 <= c0 < cols and walkable[r0][c0]:
        visited[r0][c0] = True
        q.append((r0, c0))
        visited_count = 1
    while q:
        r, c = q.popleft()
        for dr, dc in ((1,0),(-1,0),(0,1),(0,-1)):
            rr, cc = r+dr, c+dc
            if 0 <= rr < rows and 0 <= cc < cols and not visited[rr][cc] and walkable[rr][cc]:
                visited[rr][cc] = True
                q.append((rr, cc))
                visited_count += 1
    total_walkable = sum(1 for rr in range(rows) for cc in range(cols) if walkable[rr][cc])
    return visited_count, total_walkable, visited

def nudge_to_walkable(start_r: int, start_c: int, walkable: List[List[bool]]) -> Tuple[int, int]:
    rows, cols = len(walkable), len(walkable[0])
    if 0 <= start_r < rows and 0 <= start_c < cols and walkable[start_r][start_c]:
        return start_r, start_c

    for rad in range(1, max(rows, cols)):
        for dr in range(-rad, rad+1):
            for dc in range(-rad, rad+1):
                rr = start_r + dr; cc = start_c + dc
                if 0 <= rr < rows and 0 <= cc < cols and walkable[rr][cc]:
                    return rr, cc
    return start_r, start_c

def visualize_occupancy_png(out_path: str, walkable: List[List[bool]],
                             min_x: float, min_z: float, max_x: float, max_z: float,
                             cell_size: float, objects: List[Dict[str, Any]]) -> None:
    rows, cols = len(walkable), len(walkable[0])
    # 0 = blocked, 1 = walkable
    import numpy as np
    occ = np.zeros((rows, cols), dtype=int)
    for r in range(rows):
        for c in range(cols):
            occ[r, c] = 1 if walkable[r][c] else 0

    fig, ax = plt.subplots()
    ax.imshow(occ, origin='lower', cmap='Greys', interpolation='nearest')
    ax.set_title('Occupancy')
    ax.set_xlabel('col')
    ax.set_ylabel('row')
    
    # overlay object footprints as rectangles in grid coordinates
    import matplotlib.patches as patches
    for o in objects:
        if o['hanged_from_ceiling']:
            continue
        w = o['width']; d = o['depth']; cx = o['px']; cz = o['pz']
        if w <= 0 or d <= 0 or cx is None or cz is None:
            continue
        fx0 = cx - w/2.0; fx1 = cx + w/2.0
        fz0 = cz - d/2.0; fz1 = cz + d/2.0
        c0 = (fx0 - min_x)/cell_size
        r0 = (fz0 - min_z)/cell_size
        width_cells = (fx1 - fx0)/cell_size
        height_cells = (fz1 - fz0)/cell_size
        rect = patches.Rectangle((c0, r0), width_cells, height_cells,
                                 linewidth=1.5,
                                 edgecolor='cyan' if not (o['is_portal'] or o['name'].startswith('door')) else 'magenta',
                                 facecolor='none')
        ax.add_patch(rect)
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

def visualize_visited_png(out_path: str, walkable: List[List[bool]], visited: List[List[bool]]) -> None:
    import numpy as np
    rows, cols = len(walkable), len(walkable[0])
    # 0 = blocked, 1 = unvisited walkable, 2 = visited
    mat = np.zeros((rows, cols), dtype=int)
    for r in range(rows):
        for c in range(cols):
            if not walkable[r][c]:
                mat[r, c] = 0
            elif visited[r][c]:
                mat[r, c] = 2
            else:
                mat[r, c] = 1

    from matplotlib.colors import ListedColormap
    cmap = ListedColormap([
        '#1f1f1f',  # 0 blocked
        '#cfcfcf',  # 1 walkable not visited
        '#2ecc71'   # 2 visited
    ])
    fig, ax = plt.subplots()

    ax.imshow(mat, origin='lower', cmap=cmap, interpolation='nearest')
    ax.set_title('Visited vs Walkable (green = visited)')
    ax.set_xlabel('col')
    ax.set_ylabel('row')
    plt.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

def process_file(input_json_path: str, out_dir: str = 'flood_fill_outputs', cell_size: float = 0.05) -> List[Dict[str, Any]]:
    os.makedirs(out_dir, exist_ok=True)
    data = load_scene(input_json_path)
    scene = data.get('scene', {})

    portal_regions = find_portal_regions(data)
    if not portal_regions:
        print("No portals found.")
        
        result = [{
            'region': None,
            'portal_object': None,
            'is_connected': True,
            'visited_cells': None,
            'walkable_cells': None,
        }]
    
        output = []
        output.append(result)
        connectivity = 1

        output.append({"connectivity": connectivity})

        out_json_path = os.path.join(out_dir, f"scene_result.json")
        with open(out_json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2)

        return connectivity, result

    results = []
    for region_name, portal_object_name in portal_regions:
        region = scene['regions'][region_name]
        min_x, min_z, max_x, max_z = region_bounds(region)
        rows, cols = build_grid(min_x, min_z, max_x, max_z, cell_size)
        walkable = [[True for _ in range(cols)] for __ in range(rows)]
        objects = extract_objects(region)
        objects = extract_connections(scene["connections"], objects)

        for o in objects:
            if o['px'] is None:
                o['px'] = min_x
            if o['pz'] is None:
                o['pz'] = min_z
        mark_blocked(walkable, objects, min_x, min_z, cell_size)

        walkable_np = np.array(walkable, dtype=bool)
        # adjust structure or iterations for more/less strict erosion
        walkable_np = binary_erosion(walkable_np, iterations=1)
        walkable = walkable_np.tolist()

        # start at portal
        portal_obj = next(obj for obj in objects if obj['name'] == portal_object_name)
        start_r, start_c = to_grid(portal_obj['px'], portal_obj['pz'], min_x, min_z, cell_size)
        start_r, start_c = nudge_to_walkable(start_r, start_c, walkable)
        visited_cells, walkable_cells, visited = flood_fill(walkable, (start_r, start_c))
        if walkable != 0:
            is_connected = (visited_cells/walkable_cells >= 0.9)
        else:
            is_connected = True

        # visualizations
        occ_png = os.path.join(out_dir, f"{region_name}_occupancy.png")
        vis_png = os.path.join(out_dir, f"{region_name}_visited.png")
        visualize_occupancy_png(occ_png, walkable, min_x, min_z, max_x, max_z, cell_size, objects)
        visualize_visited_png(vis_png, walkable, visited)

        # JSON
        result_json = {
            'region': region_name,
            'portal_object': portal_object_name,
            'is_connected': is_connected,
            'visited_cells': visited_cells,
            'walkable_cells': walkable_cells,
        }
        results.append(result_json)
    
    output = []
    output.append(results)
    visited = 0
    walkable = 0
    for result in results:
        visited += int(result["visited_cells"])
        walkable += int(result["walkable_cells"])
    if walkable != 0:
        connectivity = visited / walkable
    else:
        connectivity = 1.0

    output.append({"connectivity": connectivity})

    out_json_path = os.path.join(out_dir, f"scene_result.json")
    with open(out_json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)

    return connectivity, results

def blockage_eval(log='output_0.json', output_dir="magic-outputs") -> bool:
    connectivity, results = process_file(log, out_dir=os.path.join(output_dir, "flood_fill_outputs"), cell_size=0.05)
    return connectivity, all(item.get('is_connected', False) for item in results)