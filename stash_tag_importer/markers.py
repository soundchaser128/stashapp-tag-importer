from dataclasses import dataclass
import itertools
import json
from pathlib import Path
import random
from typing import Dict, List
from stashapi.stashapp import StashInterface
import httpx
import subprocess


@dataclass
class Marker:
    primary_tag: str
    performers: List[str]
    seconds: int
    stream_url: str
    scene_id: str


def fetch_markers(stash: StashInterface):
    query = """
    query FindSceneMarkers($filter: FindFilterType, $scene_marker_filter: SceneMarkerFilterType) {
        findSceneMarkers(filter: $filter, scene_marker_filter: $scene_marker_filter) {
            count
            scene_markers {
            ...SceneMarkerData
            __typename
            }
            __typename
        }
        }

        fragment SceneMarkerData on SceneMarker {
        seconds
        scene {
            id
            title
            performers {
            name
            }
            sceneStreams {
            url
            mime_type
            label
            }
        }
        primary_tag {
            id
            name
        }
        tags {
            id
            name
        }
    }
    """

    variables = {
        "filter": {
            "q": "",
            "page": 1,
            "per_page": 100,
            "sort": "created_at",
            "direction": "DESC",
        },
        "scene_marker_filter": {
            "tags": {
                "value": ["11", "1880", "1573"],
                "modifier": "INCLUDES",
                "depth": 0,
            }
        },
    }

    data = stash.call_gql(query, variables)
    with open("markers.json", "w") as fp:
        json.dump(data, fp)

    data = data["findSceneMarkers"]["scene_markers"]
    markers = []
    for marker in data:
        streams = marker["scene"]["sceneStreams"]
        stream_url = [s["url"] for s in streams if s["label"] == "Direct stream"][0]

        markers.append(
            Marker(
                marker["primary_tag"]["name"],
                [p["name"] for p in marker["scene"]["performers"]],
                marker["seconds"],
                stream_url,
                marker["scene"]["id"],
            )
        )

    return markers


def group_markers_by_scene(markers: List[Marker]) -> Dict[str, List[Marker]]:
    grouped = itertools.groupby(markers, lambda m: m.scene_id)
    map = {}
    for key, group in grouped:
        map[key] = list(group)
    return map


def download_scenes(markers: List[Marker]):
    base_path = Path("./videos")
    base_path.mkdir(exist_ok=True)

    for marker in markers:
        url = marker.stream_url
        filename = base_path / f"{marker.scene_id}.mp4"
        if filename.exists():
            print(f"file {filename} exists, skipping")
            continue

        with open(filename, "wb") as fp:
            with httpx.stream("GET", url) as response:
                print(f"downloading {url}")
                for chunk in response.iter_bytes():
                    fp.write(chunk)


def build_compilation(markers: List[Marker], clip_duration: int, force_new=False):
    clips: List[Path] = []
    random.shuffle(markers)
    base_path = Path("./videos")
    idx = 0
    total = len(markers)
    for marker in markers:
        out_file = (
            base_path
            / f"{marker.scene_id}_{marker.seconds}-{marker.seconds + clip_duration}.mp4"
        )

        if force_new:
            out_file.unlink()

        if not out_file.exists():
            command = [
                "ffmpeg",
                "-hide_banner",
                # "-loglevel",
                # "warning",
                "-ss",
                str(marker.seconds),
                "-i",
                marker.stream_url,
                "-t",
                str(clip_duration),
                "-c:v",
                "libx264",
                "-preset",
                "slow",
                "-crf",
                "22",
                "-c:a",
                "copy",
                # "-acodec",
                # "aac",
                "-vf",
                "scale=1920:-2,fps=30",
                # "-ar",
                # "48000",
                str(out_file),
            ]
            process = subprocess.run(command)
            print(" ".join(command))
            process.check_returncode()
            print(f"created clip {out_file} ({idx + 1} / {total})")
            idx += 1

        clips.append(out_file)

    with open(base_path / "clips.txt", "w") as fp:
        lines = []
        for clip in clips:
            lines.append(f"file '{clip.name}'")
        lines = "\n".join(lines)
        print(lines)
        fp.write(lines)

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-f",
            "concat",
            "-i",
            "clips.txt",
            "-c",
            "copy",
            # "-c:v",
            # "libx264",
            # "-preset",
            # "slow",
            # "-crf",
            # "22",
            "compilation.mp4",
        ],
        cwd="./videos",
    )
    print("finished creating compilation")
