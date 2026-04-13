import os
import subprocess
import sys
from pathlib import Path

try:
    from smolagents import Tool
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "smolagents"])
    from smolagents import Tool

try:
    import cv2
except ImportError:
    cv2 = None


DEFAULT_TEMPLATES_DIRECTORY = (Path(__file__).resolve().parent.parent / "Templates").resolve()
DEFAULT_PROJECTS_DIRECTORY = (Path(__file__).resolve().parent.parent / "Projects").resolve()
MAX_LOCATED_PY_FILES = 40
MAX_PARSED_LINES_PER_FILE = 300
MAX_PARSED_LINE_LENGTH = 240
MAX_REGIONS_RETURNED = 10


class LocateInTemplatesDirectory(Tool):
    name = "locate_in_templates_directory"
    description = """
    Locate PNG files inside the active Templates directory.
    The active Templates directory is read from TEXTEDITOR_TEMPLATE_DIR; if unset,
    it defaults to ../Templates relative to this file.
    """

    inputs = {
        "query": {
            "type": "string",
            "description": "Optional subdirectory filter. Use an empty string to scan all template PNGs.",
        }
    }
    output_type = "array"

    def __init__(self):
        super().__init__()
        configured_root = os.getenv("TEXTEDITOR_TEMPLATE_DIR", "").strip()
        if configured_root:
            self.working_dir = Path(configured_root).expanduser().resolve()
        else:
            self.working_dir = DEFAULT_TEMPLATES_DIRECTORY

    def forward(self, query: str) -> list:
        template_root = self.working_dir
        if not template_root.exists() or not template_root.is_dir():
            return []

        normalized_query = (query or "").strip().lower()
        pngs = []

        for root, _dirs, files in os.walk(template_root):
            root_path = Path(root)
            relative_root = root_path.relative_to(template_root).as_posix().lower()

            if normalized_query and normalized_query not in (".", "*"):
                if normalized_query not in relative_root and normalized_query not in root_path.name.lower():
                    continue

            for file_name in files:
                if file_name.lower().endswith(".png"):
                    pngs.append(str((root_path / file_name).resolve()))

        return sorted(dict.fromkeys(pngs))


class ReadPNGs(Tool):
    name = "read_pngs"
    description = """
    Read PNG files and return lightweight visual metadata that can guide GUI generation.
    """
    inputs = {
        "query": {
            "type": "array",
            "items": {"type": "string"},
            "description": "A list of PNG file locations.",
        }
    }
    output_type = "array"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _iou(region_a: dict, region_b: dict) -> float:
        ax1, ay1 = int(region_a["x"]), int(region_a["y"])
        ax2 = ax1 + int(region_a["width"])
        ay2 = ay1 + int(region_a["height"])
        bx1, by1 = int(region_b["x"]), int(region_b["y"])
        bx2 = bx1 + int(region_b["width"])
        by2 = by1 + int(region_b["height"])

        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        intersection = float(inter_w * inter_h)
        if intersection <= 0.0:
            return 0.0

        area_a = float(max(1, (ax2 - ax1) * (ay2 - ay1)))
        area_b = float(max(1, (bx2 - bx1) * (by2 - by1)))
        union = area_a + area_b - intersection
        if union <= 0.0:
            return 0.0
        return intersection / union

    @staticmethod
    def _predict_region_role(x: int, y: int, w: int, h: int, image_w: int, image_h: int) -> str:
        width_ratio = float(w) / float(image_w) if image_w else 0.0
        height_ratio = float(h) / float(image_h) if image_h else 0.0
        area_ratio = float(w * h) / float(image_w * image_h) if image_w and image_h else 0.0
        aspect_ratio = float(w) / float(h) if h else 0.0
        top_ratio = float(y) / float(image_h) if image_h else 0.0
        left_ratio = float(x) / float(image_w) if image_w else 0.0

        if top_ratio <= 0.16 and width_ratio >= 0.55 and height_ratio <= 0.22:
            return "header"
        if top_ratio >= 0.72 and width_ratio >= 0.45 and height_ratio <= 0.22:
            return "footer"
        if left_ratio <= 0.20 and width_ratio <= 0.35 and height_ratio >= 0.45:
            return "sidebar"
        if aspect_ratio >= 1.7 and area_ratio <= 0.16 and top_ratio >= 0.40:
            return "button"
        if aspect_ratio >= 1.7 and area_ratio <= 0.20:
            return "input"
        if area_ratio >= 0.25:
            return "content"
        if aspect_ratio <= 1.2 and area_ratio <= 0.06 and top_ratio <= 0.35:
            return "icon"
        return "panel"

    def _extract_regions(self, image) -> list:
        height, width = image.shape[:2]
        image_area = float(max(1, width * height))

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 45, 140)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=1)

        contours_data = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = contours_data[0] if len(contours_data) == 2 else contours_data[1]

        min_region_area = max(225.0, image_area * 0.0045)
        raw_regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = float(w * h)
            if area < min_region_area:
                continue

            area_ratio = area / image_area
            if area_ratio > 0.90:
                continue

            if w < 16 or h < 12:
                continue

            role = self._predict_region_role(x, y, w, h, width, height)
            raw_regions.append(
                {
                    "x": int(x),
                    "y": int(y),
                    "width": int(w),
                    "height": int(h),
                    "area_ratio": round(area_ratio, 6),
                    "aspect_ratio": round(float(w) / float(h), 5) if h else None,
                    "role": role,
                }
            )

        if not raw_regions:
            return []

        raw_regions.sort(key=lambda region: (region["area_ratio"], region["height"]), reverse=True)
        filtered_regions = []
        for candidate in raw_regions:
            overlaps = any(self._iou(candidate, existing) >= 0.78 for existing in filtered_regions)
            if overlaps:
                continue
            filtered_regions.append(candidate)
            if len(filtered_regions) >= MAX_REGIONS_RETURNED:
                break

        filtered_regions.sort(key=lambda region: (region["y"], region["x"]))
        return filtered_regions

    @staticmethod
    def _read_png_dimensions(path: Path):
        try:
            with open(path, "rb") as png_file:
                header = png_file.read(24)
        except OSError:
            return None, None

        if len(header) < 24:
            return None, None

        if header[:8] != b"\x89PNG\r\n\x1a\n":
            return None, None

        width = int.from_bytes(header[16:20], "big")
        height = int.from_bytes(header[20:24], "big")
        return width, height

    def forward(self, query: list) -> list:
        if not isinstance(query, list):
            return []

        processed_images = []
        for image_path in query:
            path = Path(str(image_path)).expanduser()
            entry = {
                "path": str(path),
                "exists": path.exists() and path.is_file(),
            }

            if not entry["exists"]:
                entry["error"] = "File does not exist."
                processed_images.append(entry)
                continue

            if cv2 is None:
                width, height = self._read_png_dimensions(path)
                if width is None or height is None:
                    entry["error"] = "Unable to parse PNG metadata without opencv."
                else:
                    entry["width"] = int(width)
                    entry["height"] = int(height)
                    entry["channels"] = "unknown"
                    entry["aspect_ratio"] = round(float(width) / float(height), 4) if height else None
                    entry["analysis_mode"] = "metadata_only"
                processed_images.append(entry)
                continue

            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                entry["error"] = "opencv failed to decode this PNG."
                processed_images.append(entry)
                continue

            height, width = image.shape[:2]
            channels = int(image.shape[2]) if len(image.shape) > 2 else 1
            edges = cv2.Canny(image, 100, 200)
            edge_density = float((edges > 0).sum()) / float(edges.size) if edges.size else 0.0
            mean_bgr = cv2.mean(image)[:3]
            regions = self._extract_regions(image)

            entry["width"] = int(width)
            entry["height"] = int(height)
            entry["channels"] = channels
            entry["aspect_ratio"] = round(float(width) / float(height), 4) if height else None
            entry["mean_bgr"] = [round(float(channel), 3) for channel in mean_bgr]
            entry["edge_density"] = round(edge_density, 6)
            entry["regions"] = regions
            entry["region_count"] = len(regions)
            entry["analysis_mode"] = "opencv_layout_v1"

            processed_images.append(entry)

        return processed_images


class ReadOriginalPNGs(Tool):
    name = "read_original_pngs"
    description = """
    Read original PNG files and return direct visual metadata from the source images.
    This should be treated as the primary design source.
    """

    inputs = {
        "query": {
            "type": "array",
            "items": {"type": "string"},
            "description": "A list of PNG file locations.",
        }
    }
    output_type = "array"

    def __init__(self):
        super().__init__()

    def forward(self, query: list) -> list:
        if not isinstance(query, list):
            return []

        originals = []
        for image_path in query:
            path = Path(str(image_path)).expanduser()
            entry = {
                "path": str(path),
                "exists": path.exists() and path.is_file(),
            }

            if not entry["exists"]:
                entry["error"] = "File does not exist."
                originals.append(entry)
                continue

            if cv2 is None:
                width, height = ReadPNGs._read_png_dimensions(path)
                if width is None or height is None:
                    entry["error"] = "Unable to parse PNG metadata without opencv."
                else:
                    entry["width"] = int(width)
                    entry["height"] = int(height)
                    entry["aspect_ratio"] = round(float(width) / float(height), 4) if height else None
                    entry["analysis_mode"] = "original_metadata_only"
                originals.append(entry)
                continue

            image = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if image is None:
                entry["error"] = "opencv failed to decode this PNG."
                originals.append(entry)
                continue

            height, width = image.shape[:2]
            mean_bgr = cv2.mean(image)[:3]

            entry["width"] = int(width)
            entry["height"] = int(height)
            entry["aspect_ratio"] = round(float(width) / float(height), 4) if height else None
            entry["mean_bgr"] = [round(float(channel), 3) for channel in mean_bgr]
            entry["analysis_mode"] = "original_primary"
            originals.append(entry)

        return originals


class LocatePythonFiles(Tool):
    name = "locate_python_files"
    description = """
    Locate Python files in a subdirectory inside the Projects directory.
    """

    inputs = {
        "query": {
            "type": "string",
            "description": "Optional subdirectory filter. Use an empty string to scan all project files.",
        }
    }
    output_type = "array"

    def __init__(self):
        super().__init__()
        configured_root = os.getenv("TEXTEDITOR_PROJECTS_DIR", "").strip()
        if configured_root:
            self.working_dir = Path(configured_root).expanduser().resolve()
        else:
            self.working_dir = DEFAULT_PROJECTS_DIRECTORY

    def forward(self, query: str) -> list:
        project_root = self.working_dir
        if not project_root.exists() or not project_root.is_dir():
            return []

        normalized_query = (query or "").strip().lower()
        py_files = []

        for root, _dirs, files in os.walk(project_root):
            root_path = Path(root)
            relative_root = root_path.relative_to(project_root).as_posix().lower()

            if normalized_query and normalized_query not in relative_root and normalized_query not in root_path.name.lower():
                continue

            for file_name in files:
                if file_name.lower().endswith(".py"):
                    py_files.append(str((root_path / file_name).resolve()))

        unique_files = sorted(dict.fromkeys(py_files))
        return unique_files[:MAX_LOCATED_PY_FILES]


class ParsePythonFiles(Tool):
    name = "parse_python_files"
    description = """
    Receive a list of Python file paths and return each file as a list of lines.
    """

    inputs = {
        "query": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of Python file paths.",
        }
    }
    output_type = "array"

    def __init__(self):
        super().__init__()

    def forward(self, query: list) -> list:
        if not isinstance(query, list):
            return []

        file_data = []
        for path in query:
            parsed_data = []
            try:
                with open(path, "r", encoding="utf-8") as file:
                    for index, line in enumerate(file.readlines()):
                        if index >= MAX_PARSED_LINES_PER_FILE:
                            parsed_data.append("... truncated ...")
                            break
                        clipped = line.rstrip("\n")
                        if len(clipped) > MAX_PARSED_LINE_LENGTH:
                            clipped = clipped[:MAX_PARSED_LINE_LENGTH] + " ...[truncated]"
                        parsed_data.append(clipped)
            except (OSError, UnicodeDecodeError):
                continue

            file_data.append(parsed_data)

        return file_data


class ProcessParsedData(Tool):
    name = "process_parsed_data"
    description = """
    Receive parsed file data and return indices of lines that start with decorators.
    """

    inputs = {
        "query": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
            "description": "2D list of parsed data.",
        }
    }
    output_type = "array"

    def __init__(self):
        super().__init__()

    def forward(self, query: list) -> list:
        if not isinstance(query, list):
            return []

        decorator_line_indices = []

        for parsed_file in query:
            if not isinstance(parsed_file, list):
                continue

            for index, line in enumerate(parsed_file):
                if isinstance(line, str) and line.lstrip().startswith("@"):
                    decorator_line_indices.append(index)

        return decorator_line_indices


def get_tools():
    return [
        LocateInTemplatesDirectory(),
        ReadOriginalPNGs(),
        ReadPNGs(),
        LocatePythonFiles(),
        ParsePythonFiles(),
        ProcessParsedData(),
    ]
