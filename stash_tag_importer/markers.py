from dataclasses import dataclass
from pathlib import Path
import random
from typing import List
from stashapi.stashapp import StashInterface
import subprocess


@dataclass
class Marker:
    primary_tag: str
    performers: List[str]
    seconds: int
    stream_url: str
    scene_id: str


class CompilationBuilder:
    stash: StashInterface

    def __init__(self, stash: StashInterface) -> None:
        self.stash = stash

    def fetch_markers(self, tags: List[str]):
        query = """
        query FindSceneMarkers($filter: FindFilterType, $scene_marker_filter: SceneMarkerFilterType) {
            findSceneMarkers(filter: $filter, scene_marker_filter: $scene_marker_filter) {
                count
                scene_markers {
                    seconds
                    primary_tag {
                        name
                }
                scene {
                    id
                    performers {
                        name
                    }
                    sceneStreams {
                        url
                        label
                    }
                }
                }
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
                    "value": tags,
                    "modifier": "INCLUDES",
                    "depth": 0,
                }
            },
        }

        data = self.stash.call_gql(query, variables)
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

    def build_compilation(
        self,
        markers: List[Marker],
        clip_duration: int,
        force_new: bool,
        shuffle_clips: bool,
        clip_dir: str,
    ):
        clips: List[Path] = []
        if shuffle_clips:
            random.shuffle(markers)
        base_path = Path(clip_dir)
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
                    "-loglevel",
                    "warning",
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
                    "-acodec",
                    "aac",
                    "-vf",
                    "scale=1920:-2,fps=30",
                    "-ar",
                    "48000",
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
                "compilation.mp4",
            ],
            cwd=clip_dir,
        )
        print("finished creating compilation")
