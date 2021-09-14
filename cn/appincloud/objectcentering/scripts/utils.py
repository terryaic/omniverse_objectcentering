import re
import posixpath

import omni.client
from omni.physx import get_physx_scene_query_interface
from pxr import UsdGeom


def asset_exists(asset_path):
    if asset_path is None:
        return False
    return omni.client.stat(asset_path)[0] == omni.client.Result.OK


def check_is_scene_empty(stage):
    """ Check if scene is empty
    Scene is empty if no meshes are detected
    """
    for p in stage.Traverse():
        if UsdGeom.Mesh(p):
            return False
    return True


def check_raycast(stage, origin, direction, distance):
    # Projects a raycast from 'origin', in the direction of 'rayDir', for a length of 'distance' cm
    # Parameters can be replaced with real-time position and orientation data  (e.g. of a camera)
    # physX query to detect closest hit
    hit = get_physx_scene_query_interface().raycast_closest(origin, direction, distance)
    if hit["hit"]:
        # Change object colour to yellow and record distance from origin
        usdGeom = UsdGeom.Mesh.Get(stage, hit["rigidBody"])
        distance = hit["distance"]
        hit_point = origin + distance * direction
        return usdGeom.GetPath().pathString, hit_point
    return None, origin


def detect_valid_collisions(origin, direction, distance, exclusion_list):
    global valid_hit
    valid_hit = None

    def report_hit(hit):
        global valid_hit
        for exclusion in exclusion_list:
            # Valid exclusion if collision prim matches or is child of excluded prim
            if re.search(f"^{exclusion}", hit.collision):
                return True  # Continue traversal
        valid_hit = hit
        return False  # Stop traversal

    get_physx_scene_query_interface().raycast_all(origin, direction, distance, report_hit)

    return valid_hit


def get_usd_files(path, recursive=False):
    ext_filter = "^.*\.(usd|usda|usdc|USD|USDA|USDC)$"
    children = [path]
    all_files = []
    depth = 0
    while children:
        path = children.pop()
        result, entries = omni.client.list(path)
        if result == omni.client.Result.OK:
            children += [posixpath.join(path, e.relative_path) for e in entries]
        else:
            if re.search(ext_filter, path):
                all_files.append(path)
        if recursive and depth > 0:
            break
        depth += 1
    return all_files


def get_next_available_filename(directory, filename):
    existing_usd_files = get_usd_files(directory)
    suffix = 0
    new_filename = filename
    path = posixpath.join(directory, f"{new_filename}.usd")
    while path in existing_usd_files:
        new_filename = f"{filename}_{suffix}"
        path = posixpath.join(directory, f"{new_filename}.usd")
        suffix += 1
    return new_filename
