from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np
import uiautomator2 as u2
import re
import time
from xml.etree import ElementTree as ET
import logging

logger = logging.getLogger(__name__)

class UIDetector(ABC):
    @abstractmethod
    def detect_clickable_elements(self, image: np.ndarray) -> List[Tuple[Tuple[int, int, int, int], str]]:
        """Detects clickable elements on the given screen image and returns their bounds and text."""
        pass

class Uiautomator2Detector(UIDetector):
    def __init__(self, u2_device: u2.Device):
        self.d = u2_device

    def detect_clickable_elements(self, image: np.ndarray, max_retries=2) -> List[Tuple[Tuple[int, int, int, int], str]]:
        for attempt in range(max_retries):
            try:
                xml = self.d.dump_hierarchy()
                if not xml:
                    raise ValueError("dump_hierarchy returned empty XML")
                root = ET.fromstring(xml)
                elements = []
                for elem in root.iterfind('.//node[@clickable="true"][@enabled="true"][@visible-to-user="true"]'):
                    bounds = elem.get("bounds")
                    if not bounds: continue
                    match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds)
                    if match:
                        x1, y1, x2, y2 = map(int, match.groups())
                        if (x2 - x1) > 0 and (y2 - y1) > 0:
                            text = elem.get("text", "") or elem.get("content-desc", "")
                            elements.append(((x1, y1, x2, y2), text.lower()))
                return elements
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} to get clickable elements failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(0.5)
        
        logger.error(f"Failed to get clickable elements after {max_retries} attempts.")
        return []
