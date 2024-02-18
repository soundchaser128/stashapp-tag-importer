from stashapi.stashbox import StashBoxInterface
from stashapi.stashapp import StashInterface
from stashapi.stash_types import OnMultipleMatch
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from urllib.parse import urlparse
import os
import time
import json
import traceback
import logging


def init_logging():
    """Logging for console and output log file.

    1. Logs INFO messages to console.
    2. Logs DEBUG messages to stashdb_tag_importer.log.
    """
    global logger

    # Logging
    # Create a custom logger
    logger = logging.getLogger("logger")

    # Set general logging level.
    logger.setLevel(logging.DEBUG)

    # Create handlers.
    consoleHandler = logging.StreamHandler()
    fileHandler = logging.FileHandler(
        "stashdb_tag_importer.log".format(datetime.now()), "a", "utf-8"
    )

    # Set logging level for handlers.
    consoleHandler.setLevel(logging.INFO)
    fileHandler.setLevel(logging.DEBUG)

    # Create formatter and add it to handlers.
    loggerFormat = logging.Formatter(
        "%(asctime)s %(levelname)s: %(message)s", "%y-%m-%d %H:%M:%S"
    )
    consoleHandler.setFormatter(loggerFormat)
    fileHandler.setFormatter(loggerFormat)

    # Add handlers to the logger
    logger.addHandler(consoleHandler)
    logger.addHandler(fileHandler)


def get_stashdb_tags():
    """Get tags from StashDB.

    1. Cache tags from StashDB in a local JSON file.
    2. Update the cache if the local tag count is different from the StashDB tag count.
    """
    global total_stashdb_tags
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
        "input": {"page": 1, "per_page": 100, "sort": "NAME", "direction": "ASC"}
    }

    def fetch_tags():
        """Fetches tags from StashDB and stores to variable."""
        logger.info(
            f"Fetching page {variables['input']['page']}, found {len(stashdb_tags)} of {total_stashdb_tags} tags."
        )
        while len(stashdb_tags) < total_stashdb_tags:
            variables["input"]["page"] += 1
            next_page = stash_box.callGQL(tag_query, variables)["queryTags"]
            stashdb_tags.extend(next_page["tags"])
            logger.info(
                f"Fetching page {variables['input']['page']}, found {len(stashdb_tags)} of {total_stashdb_tags} tags."
            )
            time.sleep(0.75)
        logger.info(f"Fetched {len(stashdb_tags)} tags.")
        return stashdb_tags

    logger.info(f"Checking for latest tags on StashDB.")
    initial_request = stash_box.callGQL(tag_query, variables)["queryTags"]
    total_stashdb_tags = int(initial_request["count"])
    stashdb_tags = initial_request["tags"]
    cached_tags_file = Path("tags.json")
    if cached_tags_file.is_file():
        with open(cached_tags_file) as fp:
            cached_tags = json.load(fp)
        if len(cached_tags) == total_stashdb_tags:
            logger.info(f"StashDB tag cache is up to date.")
            return cached_tags
        elif len(cached_tags) != total_stashdb_tags:
            logger.info(f"cached_tags {len(cached_tags)}")
            logger.info(f"total_stashdb_tags {total_stashdb_tags}")
            logger.info(f"StashDB tag cache is out of date, updating.")
            fetch_tags()
            with open(cached_tags_file, "w") as fp:
                json.dump(stashdb_tags, fp)
            return stashdb_tags
    else:
        logger.info(f"Creating StashDB tag cache.")
        stashdb_tags = fetch_tags()
        with open(cached_tags_file, "w") as fp:
            json.dump(stashdb_tags, fp)
        return stashdb_tags


def search_for_tag(tag, search_type="name"):
    """Find current StashDB tag in local Stash instance."""

    if isinstance(tag, dict):
        # If the tag is a dict, pull the name from it.
        tag = tag["name"]

    tag_search_results = stash_api_call("find_tag", {"name": tag})

    if isinstance(tag_search_results, dict):
        # If the tag result is a dict, only a single tag was matched.
        return tag_search_results
    elif isinstance(tag_search_results, list):
        # If the tag result is a list, multiple tags were matched.
        for tag_result in tag_search_results:
            if search_type == "name":
                if tag.lower() == tag_result["name"].lower():
                    # Match a tag by name.
                    logger.info(f'Found multiple tags, using exact tag match "{tag}".')
                    return tag_result
            elif search_type == "alias":
                if tag.lower() in list(map(str.lower, tag_result["aliases"])):
                    # Match a tag to an alias in the list of aliases.
                    logger.info(
                        f'Found multiple tags, using exact alias match "{tag}".'
                    )
                    return tag_result
    elif tag_search_results == None:
        # No result found.
        if search_type == "name":
            logger.info(f'No exact match found for tag "{tag}".')
        elif search_type == "alias":
            logger.info(f'No exact match found for alias "{tag}".')

        return tag_search_results
    else:
        logging_heading()
        logger.error(f'\nScript failed on tag "{tag_search_results}".\n')
        logger.error(traceback.format_exc())
        stats["error"] += 1


def logging_heading():
    """Print a heading to the logger."""
    logger.info(f"")
    logger.info(f"--------------------------------------------------------")


def logging_footer():
    """Print a footing to the logger."""
    logger.info(f"--------------------------------------------------------")


def stash_api_call(api_call, payload, sorting=None):
    """Make Stash API calls and handle errors."""
    api_fail_bit = 0
    api_fail_count = 0

    while True:
        try:
            if api_call == "find_tag":
                return stash_api.find_tag(
                    payload, on_multiple=OnMultipleMatch.RETURN_LIST
                )
            elif api_call == "find_scenes":
                return stash_api.find_scenes(payload, sorting)
            elif api_call == "find_galleries":
                return stash_api.find_galleries(payload, sorting)
            elif api_call == "find_performers":
                return stash_api.find_performers(payload, sorting)
            elif api_call == "find_scene_markers_filter":
                return stash_api.find_scene_markers_filter(payload)
            elif api_call == "create_tag":
                return stash_api.create_tag(payload)
            elif api_call == "update_tag":
                return stash_api.update_tag(payload)
            elif api_call == "merge_tag":
                return stash_api.merge_tags(payload["source"], payload["destination"])
            elif api_call == "update_scene":
                return stash_api.update_scene(payload)
            elif api_call == "update_gallery":
                return stash_api.update_gallery(payload)
            elif api_call == "update_performer":
                return stash_api.update_performer(payload)
            elif api_call == "update_scene_marker":
                return stash_api.update_scene_marker(payload)

            if api_fail_bit == 1:
                logger.info("Recovered from API failure.")
                stats["api_recovery"] += 1
                stats["api_fail"] += 1

            break
        except:
            api_fail_bit = 1
            api_fail_count += 1
            logger.error(f"API Failure on Payload:")
            logger.error(f"{payload}")
            logger.error(traceback.format_exc())
            if api_fail_count > 5:
                stats["api_fail"] += 1
                logger.error("API call failed 5 times.")
                report_stats()
                os._exit(1)
            logger.info("Sleeping for 10 seconds, then trying API call again.")
            time.sleep(10)


def create_new_tags(tags):
    """Create tags.

    1. Create new tags if they do not exist in the database.
    2. If a tag should exist, but already exists as an alias, promote the alias from an old tag
       to a new tag, then apply the new tag to everything with the old tag applied.
    """
    logging_heading()
    logger.info(f"Create Tags")
    logging_footer()

    for stashdb_tag in tags:
        # Loop over tags fetched from StashDB.
        try:
            local_tag = search_for_tag(stashdb_tag)

            if not local_tag:
                # Create tag if it does not exist.
                logger.info(f"Creating tag \"{stashdb_tag['name']}\".")
                tag_dict = {
                    "name": stashdb_tag["name"],
                    "description": stashdb_tag["description"],
                }
                stash_api_call("create_tag", tag_dict)
                stats["tag_created"] += 1
            elif stashdb_tag["name"].lower() in list(
                map(str.lower, local_tag["aliases"])
            ):
                # If the tag exists as an alias, promote it from alias to tag.
                promote_alias(local_tag, stashdb_tag, stashdb_tag["name"])
                stats["alias_promoted"] += 1
            elif local_tag:
                logger.info(f"Tag \"{stashdb_tag['name']}\" already exists.")

        except:
            logging_heading()
            logger.error(f'\nScript failed on tag "{stashdb_tag}".\n')
            logger.error(traceback.format_exc())
            stats["error"] += 1
    report_stats()


def promote_alias(old_tag, new_tag, alias):
    """Promote alias from an old tag to a new standalone tag.

    This function does the following, in this order.
    1. Promotes the alias from an old tag to a new tag.
    2. Finds scenes, markers, galleries, and performers with the old tag, and
    ADDS the new tag to them.

    Data loss can occur if the proces is interrupted after step 1 is complete but step 2 has not finished.
    """
    # Get fresh data from the old tag.
    old_tag = search_for_tag(old_tag)

    # Store old tag ID in a dict for us to filter search against.
    old_tag_dict = {
        # This dict is a HierarchicalMultiCriterionInput.
        # CriterionModifier and HierarchicalMultiCriterionInput Documentation:
        # https://github.com/stashapp/stash/blob/develop/pkg/models/filter.go
        "value": old_tag["id"],
        "modifier": "INCLUDES",  # "modifier" accepts CriterionModifier values.
    }

    # Search filter dict, containing our old tag ID to filter search against.
    search_filter = {
        # This dict is a SceneFilterType.
        # SceneFilterType Documentation:
        # https://github.com/stashapp/stash/blob/develop/pkg/models/scene.go
        # Tags must be in their own dict.
        # Add multiple "tags" entries with their own unique dict to add tags to search.
        "tags": old_tag_dict,
    }

    # Remove alias from old tag.
    for element in old_tag["aliases"]:
        # Loop through the aliases on the old tag and remove the matching alias in a case insensitive way.
        if element.lower() == alias.lower():
            old_tag["aliases"].remove(element)
    old_tag_update_dict = {
        "id": old_tag["id"],
        "aliases": old_tag["aliases"],
    }
    stash_api_call("update_tag", old_tag_update_dict)

    if old_tag["name"].lower() == alias.lower():
        logger.info(
            f"Removing duplicate alias \"{alias}\" from tag \"{old_tag['name']}\"."
        )
        # This was done in the previous code block.
    else:
        logger.info(
            f"Promoting alias \"{alias}\" from \"{old_tag['name']}\" to standalone tag."
        )

        # Create new tag.
        new_tag_dict = {
            "name": new_tag["name"],
            "description": new_tag["description"],
        }
        stash_api_call("create_tag", new_tag_dict)

        # Get fresh data from the new tag that was just created.
        new_tag = search_for_tag(new_tag)

        # Search for scenes with our search_filter > old_tag_dict combo.
        logger.info(
            f"Migrating tag \"{new_tag['name']}\" to scenes tagged with \"{old_tag['name']}\"."
        )
        scenes_to_migrate = stash_api_call(
            "find_scenes",
            search_filter,
            {"per_page": -1, "sort": "title", "direction": "ASC"},
        )
        migrate_alias_update_stashdb("scene", scenes_to_migrate, new_tag)

        logger.info(
            f"Migrating tag \"{new_tag['name']}\" to galleries tagged with \"{old_tag['name']}\"."
        )
        galleries_to_migrate = stash_api_call(
            "find_galleries",
            search_filter,
            {"per_page": -1, "sort": "title", "direction": "ASC"},
        )
        migrate_alias_update_stashdb("gallery", galleries_to_migrate, new_tag)

        logger.info(
            f"Migrating tag \"{new_tag['name']}\" to performers tagged with \"{old_tag['name']}\"."
        )
        performers_to_migrate = stash_api_call(
            "find_performers",
            search_filter,
            {"per_page": -1, "sort": "name", "direction": "ASC"},
        )
        migrate_alias_update_stashdb("performer", performers_to_migrate, new_tag)

        logger.info(
            f"Migrating tag \"{new_tag['name']}\" to markers tagged with \"{old_tag['name']}\"."
        )
        markers_to_migrate = stash_api_call("find_scene_markers_filter", search_filter)
        migrate_alias_update_stashdb("marker", markers_to_migrate, new_tag)


def create_aliases(tags):
    """Create and migrate aliases.

    1. If the alias does not exist, create it for the correct tag.
    2. If the alias exists as an alias for a different tag, migrate it to the correct tag.
    """
    logging_heading()
    logger.info(f"Create and Migrate Aliases")
    logging_footer()

    for stashdb_tag in tags:
        # Loop over tags scraped from StashDB.
        try:
            local_tag = search_for_tag(stashdb_tag)

            # If a local tag exists...
            if local_tag:
                # Loop through each alias associated with the current StashDB tag.
                for alias in stashdb_tag["aliases"]:
                    # Loop through each alias associated with the current StashDB tag.

                    # Find alias in local Stash instance.
                    alias_tag_search = search_for_tag(alias, search_type="alias")

                    if alias_tag_search == None or alias.lower() not in list(
                        map(str.lower, alias_tag_search["aliases"])
                    ):
                        # Attempt to merge the tag first.
                        if merge_tags([stashdb_tag], single_tag=True) == True:
                            # If there is a tag to merge, add the alias to the
                            # local tag's aliases in case it needs to updated later.
                            local_tag["aliases"].append(alias)
                        else:
                            # If there is no tag to merge, and the StashDB alias
                            # does not exist as a local alias, create it.
                            logger.info(
                                f"Aliasing \"{alias}\" to parent tag \"{local_tag['name']}\"."
                            )
                            local_tag["aliases"].append(alias)
                            alias_update_dict = {
                                "id": local_tag["id"],
                                "aliases": local_tag["aliases"],
                            }
                            stash_api_call("update_tag", alias_update_dict)
                            stats["alias_created"] += 1
                    elif alias.lower() in list(
                        map(str.lower, alias_tag_search["aliases"])
                    ):
                        # If the StashDB alias is found as an alias for an existing local tag,
                        # we need to migrate it.
                        if alias_tag_search["id"] != local_tag["id"]:
                            # Make sure we don't attempt to migrate aliases to the same tag.
                            migrate_alias(alias_tag_search, local_tag, alias)
                            stats["alias_migrated"] += 1
                            # Refresh local_tag with migrated tag so it doesn't get overwritten in a subsequent loop.
                            local_tag = search_for_tag(stashdb_tag)
                        elif alias_tag_search["id"] == local_tag["id"]:
                            logger.info(
                                f"Tag \"{alias_tag_search['name']}\" already has alias \"{alias}\"."
                            )
        except:
            logging_heading()
            logger.error(f'\nScript failed on tag "{stashdb_tag}".\n')
            logger.error(traceback.format_exc())
            stats["error"] += 1
    report_stats()


def migrate_alias(old_tag, new_tag, alias):
    """Migrate alias from an old tag, to a new tag.

    This function does the following, in this order.
    1. Finds scenes, markers, galleries, and performers with the old tag, and
    ADDS the new tag to them.
    2. Migrates the alias from the old tag to the new tag.

    Step 2 is explicitly performed after step 1 in the event that the
    process needs to be interrupted, it can be restarted without
    data loss.
    """
    # Get fresh data from the old tag and new tag.
    old_tag = search_for_tag(old_tag)
    new_tag = search_for_tag(new_tag)
    logger.info(
        f"Migrating alias \"{alias}\" from \"{old_tag['name']}\" to \"{new_tag['name']}\"."
    )

    # Store old tag ID in a dict for us to filter search against.
    old_tag_dict = {
        # This dict is a HierarchicalMultiCriterionInput.
        # CriterionModifier and HierarchicalMultiCriterionInput Documentation:
        # https://github.com/stashapp/stash/blob/develop/pkg/models/filter.go
        "value": old_tag["id"],
        "modifier": "INCLUDES",  # "modifier" accepts CriterionModifier values.
    }

    # Search filter dict, containing our old tag ID to filter search against.
    search_filter = {
        # This dict is a SceneFilterType.
        # SceneFilterType Documentation:
        # https://github.com/stashapp/stash/blob/develop/pkg/models/scene.go
        # Tags must be in their own dict.
        # Add multiple "tags" entries with their own unique dict to add tags to search.
        "tags": old_tag_dict,
    }

    # Search for scenes with our search_filter > old_tag_dict combo.
    logger.info(
        f"Migrating tag \"{new_tag['name']}\" to scenes tagged with \"{old_tag['name']}\"."
    )
    scenes_to_migrate = stash_api_call(
        "find_scenes",
        search_filter,
        {"per_page": -1, "sort": "title", "direction": "ASC"},
    )
    migrate_alias_update_stashdb("scene", scenes_to_migrate, new_tag)

    logger.info(
        f"Migrating tag \"{new_tag['name']}\" to galleries tagged with \"{old_tag['name']}\"."
    )
    galleries_to_migrate = stash_api_call(
        "find_galleries",
        search_filter,
        {"per_page": -1, "sort": "title", "direction": "ASC"},
    )
    migrate_alias_update_stashdb("gallery", galleries_to_migrate, new_tag)

    logger.info(
        f"Migrating tag \"{new_tag['name']}\" to performers tagged with \"{old_tag['name']}\"."
    )
    performers_to_migrate = stash_api_call(
        "find_performers",
        search_filter,
        {"per_page": -1, "sort": "name", "direction": "ASC"},
    )
    migrate_alias_update_stashdb("performer", performers_to_migrate, new_tag)

    logger.info(
        f"Migrating tag \"{new_tag['name']}\" to markers tagged with \"{old_tag['name']}\"."
    )
    markers_to_migrate = stash_api_call("find_scene_markers_filter", search_filter)
    migrate_alias_update_stashdb("marker", markers_to_migrate, new_tag)

    # Remove alias from old tag.
    for element in old_tag["aliases"]:
        # Loop through the aliases on the old tag and remove the matching alias in a case insensitive way.
        if element.lower() == alias.lower():
            old_tag["aliases"].remove(element)
    old_tag_update_dict = {
        "id": old_tag["id"],
        "aliases": old_tag["aliases"],
    }
    stash_api_call("update_tag", old_tag_update_dict)

    # Add alias to new tag.
    new_tag["aliases"].append(alias)
    new_tag_update_dict = {
        "id": new_tag["id"],
        "aliases": new_tag["aliases"],
    }
    stash_api_call("update_tag", new_tag_update_dict)


def migrate_alias_update_stashdb(update_type, migration_list, migrate_tag):
    """Find scenes, markers, galleries, and performers with the old tag, and ADD the new tag to them."""
    for item in migration_list:
        # migration_list is the list of scenes, markers, galleries, and performers to be updated.
        tags_to_migrate = []
        for tag in item["tags"]:
            # Add each existing tag to a list so we can add it back to the original
            # ID, plus the tag we are migrating.
            tags_to_migrate.append(tag["id"])

        if not migrate_tag["id"] in tags_to_migrate:
            # If the tag already exists in the place we're migrating to, skip migration.
            tags_to_migrate.append(migrate_tag["id"])

            update_dict = {
                # Documentation for "tag_ids" here under func scenePartialFromInput:
                # https://github.com/stashapp/stash/blob/develop/internal/api/resolver_mutation_scene.go
                "id": item["id"],
                "tag_ids": tags_to_migrate,
            }

            if update_type == "scene":
                logger.info(
                    f"Migrating tag \"{migrate_tag['name']}\" to scene \"{item['title']}\"."
                )
                stash_api_call("update_scene", update_dict)
                stats["scene_tag_migrated"] += 1
            elif update_type == "gallery":
                logger.info(
                    f"Migrating tag \"{migrate_tag['name']}\" to gallery \"{item['title']}\"."
                )
                stash_api_call("update_gallery", update_dict)
                stats["gallery_tag_migrated"] += 1
            elif update_type == "performer":
                logger.info(
                    f"Migrating tag \"{migrate_tag['name']}\" to performer \"{item['name']}\"."
                )
                stash_api_call("update_performer", update_dict)
                stats["performer_tag_migrated"] += 1
            elif update_type == "marker":
                logger.info(
                    f"Migrating tag \"{migrate_tag['name']}\" to marker ID \"{item['id']}\"."
                )
                # These additional items are required to update a scene marker
                # so we're just redirecting them from the existing marker to
                # the update_dict.
                update_dict["title"] = item["title"]
                update_dict["seconds"] = item["seconds"]
                update_dict["scene_id"] = item["scene"]["id"]
                update_dict["primary_tag_id"] = item["primary_tag"]["id"]
                stash_api_call("update_scene_marker", update_dict)
                stats["marker_tag_migrated"] += 1


def merge_tags(tags, single_tag=False):
    """Merge tags where the source tag has an alias that should be associated with the destination tag."""

    if single_tag == False:
        # Show heading when merging all tags.
        logging_heading()
        logger.info(f"Merge Tags")
        logging_footer()

    for stashdb_tag in tags:
        # Loop over tags fetched from StashDB.
        try:
            local_tag = search_for_tag(stashdb_tag)

            if local_tag:
                # Destination tag ID that source tag will be merged into.
                destination_tag_id = local_tag["id"]
                destination_tag_name = local_tag["name"]

                for alias in stashdb_tag["aliases"]:
                    # Loop through each alias associated with the current StashDB tag.

                    # Find alias matching tag name in local Stash instance.
                    alias_tag_search = search_for_tag(alias, search_type="name")

                    if alias_tag_search == None:
                        # No matching tag name for this alias.

                        if single_tag == True:
                            # If a single tag was not merged, return False so other functions can validate.
                            return False

                        # Find alias matching alias name in local Stash instance.
                        alias_tag_search = search_for_tag(alias, search_type="alias")
                        if alias.lower() in list(
                            map(str.lower, alias_tag_search["aliases"])
                        ):
                            logger.info(
                                f"Tag \"{alias_tag_search['name']}\" already has alias \"{alias}\"."
                            )
                            # No need to return True or False for this result since there is nothing else to do.
                    elif (
                        alias.lower() == alias_tag_search["name"].lower()
                        and alias.lower() != destination_tag_name.lower()
                    ):
                        # If the StashDB Tag alias matches a Local Tag name, merge it into the StashDB Tag.
                        # Make sure the alias is not the same as the destination tag name in the event of redundant tags.

                        # Source tag ID of tag that will be merged.
                        source_tag_id = alias_tag_search["id"]

                        logger.info(
                            f"Merging alias \"{alias_tag_search['name']}\" into tag \"{local_tag['name']}\"."
                        )
                        merge_dict = {
                            "source": source_tag_id,
                            "destination": destination_tag_id,
                        }
                        stash_api_call("merge_tag", merge_dict)
                        stats["tag_merged"] += 1

                        if single_tag == True:
                            # If a single tag was merged, return True so other functions can validate.
                            return True
                    else:
                        # Prevent duplicate prints on single tag calls.
                        if single_tag == False:
                            # Find alias matching alias name in local Stash instance.
                            alias_tag_search = search_for_tag(
                                alias, search_type="alias"
                            )
                            if alias.lower() in list(
                                map(str.lower, alias_tag_search["aliases"])
                            ):
                                logger.info(
                                    f"Tag \"{alias_tag_search['name']}\" already has alias \"{alias}\"."
                                )
                                # No need to return True or False for this result since there is nothing else to do.

        except:
            logging_heading()
            logger.error(f'\nScript failed on tag "{stashdb_tag}".\n')
            logger.error(traceback.format_exc())
            stats["error"] += 1

    if single_tag == False:
        # Report stats when merging all tags.
        report_stats()


def update_tags(tags):
    """Update tag names and descriptions."""

    logging_heading()
    logger.info(f"Update Tags")
    logging_footer()

    for stashdb_tag in tags:
        # Loop over tags fetched from StashDB.
        try:
            local_tag = search_for_tag(stashdb_tag)

            if local_tag:
                # Only continue if the local tag is found.
                if (
                    stashdb_tag["name"] != local_tag["name"]
                    and stashdb_tag["description"] != local_tag["description"]
                ):
                    # Update tag if name and description varies.
                    logger.info(
                        f"Updating tag \"{local_tag['name']}\" name and description."
                    )
                    tag_update_dict = {
                        "id": local_tag["id"],
                        "name": stashdb_tag["name"],
                        "description": stashdb_tag["description"],
                    }
                    stash_api_call("update_tag", tag_update_dict)
                    stats["tag_name_updated"] += 1
                    stats["tag_description_updated"] += 1
                elif stashdb_tag["name"] != local_tag["name"]:
                    # Update tag if name varies.
                    logger.info(f"Updating tag \"{local_tag['name']}\" name.")
                    tag_update_dict = {
                        "id": local_tag["id"],
                        "name": stashdb_tag["name"],
                    }
                    stash_api_call("update_tag", tag_update_dict)
                    stats["tag_name_updated"] += 1
                elif stashdb_tag["description"] != local_tag["description"]:
                    # Update tag if name and description varies.
                    logger.info(f"Updating tag \"{local_tag['name']}\" description.")
                    tag_update_dict = {
                        "id": local_tag["id"],
                        "description": stashdb_tag["description"],
                    }
                    stash_api_call("update_tag", tag_update_dict)
                    stats["tag_description_updated"] += 1
                elif (
                    stashdb_tag["name"] == local_tag["name"]
                    and stashdb_tag["description"] == local_tag["description"]
                ):
                    logger.info(f"Tag \"{local_tag['name']}\" already up to date.")
        except:
            logging_heading()
            logger.error(f'\nScript failed on tag "{stashdb_tag}".\n')
            logger.error(traceback.format_exc())
            stats["error"] += 1
    report_stats()


def init_stats():
    """Initialize stats dict."""
    global stats
    stats = {
        "tag_created": 0,
        "alias_created": 0,
        "alias_promoted": 0,
        "tag_merged": 0,
        "alias_migrated": 0,
        "scene_tag_migrated": 0,
        "gallery_tag_migrated": 0,
        "performer_tag_migrated": 0,
        "marker_tag_migrated": 0,
        "tag_name_updated": 0,
        "tag_description_updated": 0,
        "error": 0,
        "api_fail": 0,
        "api_recovery": 0,
    }


def report_stats():
    """Print out stats."""
    logger.info(f"")
    logger.info(f"Final Stats")
    logger.info(f"-------------------------:")
    logger.info(f"Tags Created             : {stats['tag_created']}")
    logger.info(f"Tags Merged              : {stats['tag_merged']}")
    logger.info(f"Aliases Created          : {stats['alias_created']}")
    logger.info(f"Aliases Promoted         : {stats['alias_promoted']}")
    logger.info(f"-------------------------:")
    logger.info(f"Aliases Migrated         : {stats['alias_migrated']}")
    logger.info(f"Scene Tags Migrated      : {stats['scene_tag_migrated']}")
    logger.info(f"Marker Tags Migrated     : {stats['marker_tag_migrated']}")
    logger.info(f"Gallery Tags Migrated    : {stats['gallery_tag_migrated']}")
    logger.info(f"Performer Tags Migrated  : {stats['performer_tag_migrated']}")
    logger.info(f"-------------------------:")
    logger.info(f"Tag Names Updated        : {stats['tag_name_updated']}")
    logger.info(f"Tag Descriptions Updated : {stats['tag_description_updated']}")
    logger.info(f"-------------------------:")
    logger.info(f"API Call Failures        : {stats['api_fail']}")
    logger.info(f"API Call Recoveries      : {stats['api_recovery']}")
    logger.info(f"Script Errors            : {stats['error']}")
    logger.info(f"-------------------------:")
    logger.info(f"")


def main():
    """Main logic loop."""
    global stash_url, stash_api
    load_dotenv()
    stash_url = urlparse(os.environ["STASHAPP_URL"])
    stash_api = StashInterface(
        {
            "scheme": stash_url.scheme,
            "domain": stash_url.hostname,
            "port": stash_url.port,
            "ApiKey": os.environ["STASHAPP_API_KEY"],
        }
    )

    init_logging()
    init_stats()
    tags = get_stashdb_tags()

    # Work Block
    create_new_tags(tags)
    create_aliases(tags)
    merge_tags(tags)
    update_tags(tags)


if __name__ == "__main__":
    main()
