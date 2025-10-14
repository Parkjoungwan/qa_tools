import glob
import json
from pathlib import Path

def generate_graph_data():
    MERGE_RADIUS = 50 # If different buttons are merged, reduce this value.

    log_dir = Path(__file__).parent / 'log'
    samples_dir = Path(__file__).parent / 'samples'
    output_dir = Path(__file__).parent / 'visualization'
    output_dir.mkdir(exist_ok=True)

    log_files = sorted(glob.glob(str(log_dir / 'adb_*.log')))
    if not log_files:
        print("No log files found.")
        output_path = output_dir / 'graph.json'
        with open(output_path, 'w') as f:
            json.dump({"nodes": [], "edges": []}, f)
        print("Generated an empty graph.")
        return

    print(f"Processing {len(log_files)} log file(s)வுகளில்...")

    nodes = []
    node_ids = set()
    edges = []
    page_tap_coords = {}

    # --- Ensure mainPage exists & mark as root ---
    root_label = "mainPage"
    root_page_id = f"page_{root_label}_1" # Always treat the root as page 1
    if root_page_id not in node_ids:
        nodes.append({"id": root_page_id, "label": root_label, "type": "page", "size": 15, "is_root": True})
        node_ids.add(root_page_id)
        page_tap_coords[root_page_id] = []

    all_lines = []
    for log_file in log_files:
        with open(log_file, 'r', encoding='utf-8') as f:
            for line_str in f.readlines()[1:]:
                if line_str.strip():
                    all_lines.append(line_str.strip().split('\t'))

    # --- Single Pass to build graph ---
    for i, parts in enumerate(all_lines):
        try:
            event_type = parts[0]
            page = parts[3].strip() if len(parts) > 3 and parts[3].strip() else 'unidentified'
            if page == "mainPage": page = "mainPage_1" # Ensure consistency
            page_id = f"page_{page.replace(' ', '_')}"
        except IndexError:
            continue # Skip malformed lines

        if page_id not in node_ids:
            nodes.append({"id": page_id, "label": page, "type": "page", "size": 15})
            node_ids.add(page_id)
            page_tap_coords[page_id] = []

        current_tap_id = None
        if event_type == 'tap':
            try:
                serial, x, y = parts[2], int(parts[5]), int(parts[6])
            except (IndexError, ValueError):
                continue

            found_duplicate = False
            for existing_tap in page_tap_coords.get(page_id, []):
                if ((existing_tap['x'] - x)**2 + (existing_tap['y'] - y)**2)**0.5 < MERGE_RADIUS:
                    current_tap_id = existing_tap['id']
                    found_duplicate = True
                    break
            
            if not found_duplicate:
                new_tap_id = f"tap_{page.replace(' ', '_')}_{x}_{y}"
                current_tap_id = new_tap_id
                if new_tap_id not in node_ids:
                    sample_path = None
                    page_sample_dir = samples_dir / page.replace(' ', '_')
                    if page_sample_dir.exists():
                        found_samples = list(page_sample_dir.glob(f"*_{serial}_{x}_{y}.png"))
                        if found_samples:
                            sample_path = str(Path("..") / found_samples[0].relative_to(Path(__file__).parent))
                    nodes.append({
                        "id": new_tap_id, "label": f"({x},{y})", "type": "tap",
                        "size": 6, "image": sample_path, "parent_page": page_id,
                        "logLine": "\t".join(parts)
                    })
                    node_ids.add(new_tap_id)
                    page_tap_coords[page_id].append({"id": new_tap_id, "x": x, "y": y})
            
            if current_tap_id:
                 edges.append({"source": page_id, "target": current_tap_id, "type": "containment"})

        if current_tap_id and i + 1 < len(all_lines):
            next_parts = all_lines[i+1]
            if len(next_parts) > 3:
                next_page = next_parts[3].strip() if next_parts[3].strip() else 'unidentified'
                if next_page != page:
                    next_page_id = f"page_{next_page.replace(' ', '_')}"
                    if next_page_id not in node_ids:
                        nodes.append({"id": next_page_id, "label": next_page, "type": "page", "size": 15})
                        node_ids.add(next_page_id)
                        page_tap_coords[next_page_id] = []
                    edges.append({"source": current_tap_id, "target": next_page_id, "type": "transition"})

    # --- Connect all mainPage nodes to each other ---
    main_page_nodes = [n for n in nodes if n['id'].startswith('page_mainPage')]
    for i in range(len(main_page_nodes)): 
        for j in range(i + 1, len(main_page_nodes)): 
            node_a = main_page_nodes[i]
            node_b = main_page_nodes[j]
            edges.append({"source": node_a['id'], "target": node_b['id'], "type": "pagination"})
            edges.append({"source": node_b['id'], "target": node_a['id'], "type": "pagination"})

    # Deduplicate edges using the suggested robust method
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e.get("source"), e.get("target"), e.get("type"))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    output_path = output_dir / 'graph.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"nodes": nodes, "edges": unique_edges}, f, indent=2)
    
    print(f"Graph data from all logs generated at: {output_path}")

if __name__ == '__main__':
    generate_graph_data()
