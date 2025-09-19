import time
import json
import logging
from typing import Tuple, Dict
import numpy as np

from adb_utils import get_device_resolution, get_device_orientation, get_stable_insets, get_device_property
from config import DEVICE_PROFILES_FILE

logger = logging.getLogger(__name__)

class DisplayTransform:
    def __init__(self, serial: str):
        self.serial = serial
        self.profile_key = self._get_profile_key()
        self.profiles = self._load_profiles()
        self.last_update_time = 0
        self.update()

    def _get_profile_key(self) -> str:
        brand = get_device_property(self.serial, "ro.product.brand").lower()
        model = get_device_property(self.serial, "ro.product.model").lower().replace(" ", "_")
        sdk = get_device_property(self.serial, "ro.build.version.sdk")
        return f"{brand}_{model}_sdk{sdk}"

    def _load_profiles(self) -> Dict:
        if not DEVICE_PROFILES_FILE.exists():
            return {}
        with open(DEVICE_PROFILES_FILE, "r") as f:
            return json.load(f)

    def _save_profiles(self):
        with open(DEVICE_PROFILES_FILE, "w") as f:
            json.dump(self.profiles, f, indent=4)

    def update(self, force=False):
        now = time.time()
        if not force and (now - self.last_update_time) < 0.5: # Cooldown of 0.5s
            return

        res = get_device_resolution(self.serial)
        if not res:
            raise RuntimeError("Could not get device resolution for DisplayTransform")
        self.current_w, self.current_h = res
        self.orientation = get_device_orientation(self.serial)

        orientation_key = str(self.orientation)
        profile = self.profiles.get(self.profile_key, {}).get(orientation_key, {})

        if profile.get('stable_insets') and not force:
            self.stable_insets = tuple(profile['stable_insets'])
        else:
            self.stable_insets = get_stable_insets(self.serial)
            logger.info(f"Queried new insets for orientation {self.orientation}: {self.stable_insets}")
            self.profiles.setdefault(self.profile_key, {}).setdefault(orientation_key, {})['stable_insets'] = self.stable_insets
            self._save_profiles()

        l, t, r, b = self.stable_insets
        self.safe_area_x = l
        self.safe_area_y = t
        self.safe_area_w = self.current_w - l - r
        self.safe_area_h = self.current_h - t - b

        self.natural_w = min(self.current_w, self.current_h)
        self.natural_h = max(self.current_w, self.current_h)
        self.last_update_time = now

    def to_natural_normalized(self, px: int, py: int) -> Tuple[float, float]:
        safe_px = np.clip(px - self.safe_area_x, 0, self.safe_area_w)
        safe_py = np.clip(py - self.safe_area_y, 0, self.safe_area_h)

        u_current = safe_px / self.safe_area_w if self.safe_area_w > 0 else 0
        v_current = safe_py / self.safe_area_h if self.safe_area_h > 0 else 0

        if self.orientation == 0: u_natural, v_natural = u_current, v_current
        elif self.orientation == 1: u_natural, v_natural = v_current, 1.0 - u_current
        elif self.orientation == 2: u_natural, v_natural = 1.0 - u_current, 1.0 - v_current
        elif self.orientation == 3: u_natural, v_natural = 1.0 - v_current, u_current
        else: u_natural, v_natural = u_current, v_current
        return u_natural, v_natural

    def from_natural_normalized(self, u: float, v: float) -> Tuple[int, int]:
        if self.orientation == 0: u_current, v_current = u, v
        elif self.orientation == 1: u_current, v_current = 1.0 - v, u
        elif self.orientation == 2: u_current, v_current = 1.0 - u, 1.0 - v
        elif self.orientation == 3: u_current, v_current = v, 1.0 - u
        else: u_current, v_current = u, v

        px = self.safe_area_x + int(u_current * self.safe_area_w)
        py = self.safe_area_y + int(v_current * self.safe_area_h)
        return px, py
