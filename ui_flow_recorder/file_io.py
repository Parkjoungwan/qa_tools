import json
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict
import cv2
from pathlib import Path

from config import DATA_FILE, DEVICE_PROFILES_FILE
from models import FlowData, Screen, Transition, TouchEvent, TransitionStats

logger = logging.getLogger(__name__)

def load_profiles() -> Dict:
    if not DEVICE_PROFILES_FILE.exists():
        return {}
    with open(DEVICE_PROFILES_FILE, "r") as f:
        return json.load(f)

def save_profiles(profiles: Dict):
    with open(DEVICE_PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=4)

def load_flow_data() -> FlowData:
    if DATA_FILE.exists() and DATA_FILE.stat().st_size > 0:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
        if raw.get("version") != "2.0":
            raw = migrate_v1_to_v2(raw)

        screens = {sid: Screen(**s) for sid, s in raw.get("screens", {}).items()}
        transitions = []
        for t in raw.get("transitions", []):
            events = [TouchEvent(**e) for e in t.get("touch_events", [])]
            stats = TransitionStats(**t.get("stats", {}))
            transitions.append(Transition(from_id=t["from_id"], to_id=t["to_id"], touch_events=events,
                                          stats=stats,
                                          legacy=t.get("__legacy__", False)))
        return FlowData(version=raw.get("version","2.0"),
                        created_at=raw.get("created_at",""),
                        screens=screens, transitions=transitions)
    return FlowData()

def save_flow_data(flow_data: FlowData):
    data = flow_data.__dict__
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4, default=lambda o: o.__dict__)

def migrate_v1_to_v2(data: Dict) -> Dict:
    logger.info("Migrating data from v1 to v2 schema...")
    backup_path = DATA_FILE.with_suffix(".json.v1.bak")
    if Path(DATA_FILE).exists():
        shutil.copy(DATA_FILE, backup_path)
        logger.info(f"Backed up v1 data to {backup_path}")

    data["version"] = "2.0"
    data["created_at"] = datetime.now(timezone.utc).isoformat()

    screens = data.get("screens", {})
    for sid, info in screens.items():
        if 'path' in info and 'paths' not in info:
            info['paths'] = [info.pop('path')] if info.get('path') else []
        info.setdefault('meta', {})
        info.setdefault('signature', None) # Add signature field

    image_dims_cache = {}
    for t in data.get("transitions", []):
        t.pop("coords", None)
        t.setdefault("stats", {})
        t["from_id"] = t.pop("from")
        t["to_id"] = t.pop("to")

        if not t.get("touch_events"): continue

        is_already_normalized = all(0.0 <= e.get('u', -1) <= 1.0 for e in t['touch_events'])
        if is_already_normalized: continue

        from_id = t.get("from_id")
        if not from_id or from_id not in screens:
            t["__legacy__"] = True; continue

        if from_id not in image_dims_cache:
            ref_paths = screens[from_id].get("paths", [])
            if not ref_paths:
                t["__legacy__"] = True; continue
            w, h = -1, -1
            for p_str in ref_paths:
                p = Path(p_str)
                if p.exists():
                    img = cv2.imread(str(p))
                    if img is not None:
                        h_img, w_img, _ = img.shape
                        image_dims_cache[from_id] = (w_img, h_img)
                        w, h = w_img, h_img
                        break
            if w == -1:
                t["__legacy__"] = True; continue

        W, H = image_dims_cache[from_id]
        if W == 0 or H == 0:
            t["__legacy__"] = True; continue

        logger.info(f"Normalizing transition from screen {from_id} using resolution {W}x{H}")
        for event in t["touch_events"]:
            if event.get("type") == "tap" and "x" in event:
                u_nat = event.pop("x") / W
                v_nat = event.pop("y") / H
                event['u'] = round(u_nat, 4)
                event['v'] = round(v_nat, 4)
            elif event.get("type") == "swipe" and "x1" in event:
                u1_nat = event.pop("x1") / W
                v1_nat = event.pop("y1") / H
                u2_nat = event.pop("x2") / W
                v2_nat = event.pop("y2") / H
                event['u1'] = round(u1_nat, 4)
                event['v1'] = round(v1_nat, 4)
                event['u2'] = round(u2_nat, 4)
                event['v2'] = round(v2_nat, 4)
        
        t["touch_events"] = sorted(t["touch_events"], key=lambda e: e.get('time', 0))

    return data
