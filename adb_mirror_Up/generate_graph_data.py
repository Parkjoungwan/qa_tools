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
        # ... (create empty graph) ...
        return

    print(f"Processing {len(log_files)} log file(s)வுகளில்...")

    nodes = []
    node_ids = set()
    edges = []
    page_tap_coords = {} 

    # --- Ensure mainPage exists & mark as root ---
    root_label = "mainPage"
    root_page_id = f"page_{root_label.replace(' ', '_')}"
    if root_page_id not in node_ids:
        nodes.append({"id": root_page_id, "label": root_label, "type": "page", "size": 15, "is_root": True})
        node_ids.add(root_page_id)
        page_tap_coords[root_page_id] = []
    else:
        for n in nodes:
            if n["id"] == root_page_id:
                n["is_root"] = True
                break

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
                continue # Skip if tap event is malformed

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
                            sample_path = str(Path(".." ) / found_samples[0].relative_to(Path(__file__).parent))
                    nodes.append({
                        "id": new_tap_id, "label": f"({x},{y})", "type": "tap",
                        "size": 6, "image": sample_path, "parent_page": page_id
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
                    # CRITICAL FIX: If next page node doesn't exist, create it now.
                    if next_page_id not in node_ids:
                        nodes.append({"id": next_page_id, "label": next_page, "type": "page", "size": 15})
                        node_ids.add(next_page_id)
                        page_tap_coords[next_page_id] = []
                    edges.append({"source": current_tap_id, "target": next_page_id, "type": "transition"})

    # Deduplicate edges using the suggested robust method
    seen = set()
    unique_edges = []
    for e in edges:
        key = (e.get("source"), e.get("target"), e.get("type"))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)

    # --- Verification Step ---
    print("\n--- Verifying Transitions ---")
    expected = [
        ("tap_mainPage_1681_230", "page_2,3"),
        ("tap_mainPage_120_102", "page_profileSelect"),
        ("tap_mainPage_1814_92", "page_mainMenu"),
        ("tap_mainPage_352_584", "page_studyReport"),
        ("tap_mainPage_1628_94", "page_adventureCourse"),
        ("tap_mainPage_1721_86", "page_adventureOverview"),
    ]
    present = {(e["source"], e["target"]) for e in unique_edges if e["type"]=="transition"}
    missing = [pair for pair in expected if pair not in present]
    if not missing:
        print("All expected transitions are present.")
    else:
        print("Missing transitions:", missing)
    print("---------------------------\n")

    output_path = output_dir / 'graph.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({"nodes": nodes, "edges": unique_edges}, f, indent=2)
    
    print(f"Graph data from all logs generated at: {output_path}")

if __name__ == '__main__':
    generate_graph_data()