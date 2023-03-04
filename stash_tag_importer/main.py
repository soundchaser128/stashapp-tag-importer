from pprint import pprint
from stashapi.stashbox import StashBoxInterface
from stashapi.stashapp import StashInterface
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse
import os
import time
import json
import markers


def fetch_tags():
    stash_box = StashBoxInterface(
        {
            "endpoint": os.environ["STASHBOX_ENDPOINT"],
            "api_key": os.environ["STASHBOX_API_KEY"],
        }
    )

    tag_query = """
        query Tags($input: TagQueryInput!){
            queryTags(input: $input){
                count
                tags {
                    id
                    name
                    aliases
                    description
                }
            }
        }
    """
    variables = {
        "input": {"page": 1, "per_page": 100, "sort": "NAME", "direction": "DESC"}
    }

    initial_request = stash_box.callGQL(tag_query, variables)["queryTags"]
    total_count = int(initial_request["count"])

    all_tags = initial_request["tags"]

    while len(all_tags) < total_count:
        variables["input"]["page"] += 1
        print("getting tags from page", variables["input"]["page"])
        print(f"found {len(all_tags)} tags so far")
        next_page = stash_box.callGQL(tag_query, variables)["queryTags"]
        all_tags.extend(next_page["tags"])
        time.sleep(0.75)

    return all_tags


# cache tags in a tags.json file so we don't need to repeat the requests every time
def load_tags():
    all_tags = None
    tags_file = Path("tags.json")
    if tags_file.is_file():
        with open(tags_file) as fp:
            all_tags = json.load(fp)
    else:
        all_tags = fetch_tags()
        with open("tags.json", "w") as fp:
            json.dump(all_tags, fp)
    return all_tags


def create_stash_api():
    stash_url = urlparse(os.environ["STASHAPP_URL"])
    return StashInterface(
        {
            "scheme": stash_url.scheme,
            "domain": stash_url.hostname,
            "port": stash_url.port,
            "ApiKey": os.environ["STASHAPP_API_KEY"],
        }
    )


def persist_tags(stash_api, tags):
    for tag in tags:
        try:
            stash_api.create_tag(
                {
                    "name": tag["name"],
                    "description": tag["description"],
                    "aliases": tag["aliases"],
                }
            )
        except Exception as e:
            print(f"failed to persist tag {tag}: {e}")


def main():
    load_dotenv()
    stash = create_stash_api()
    marker_list = markers.fetch_markers(stash)
    markers.build_compilation(marker_list, 10)


if __name__ == "__main__":
    main()
