# stashapp-tag-importer
Creates tags and aliases, resolves tag conflicts, and updates tag titles and descriptions from Stashbox (StashDB) to your local Stash instance. It can be run periodically to perform a one-sided "sync" from Stashbox (StashDB) to your Stash instance.

## Warning - Back Up Stash Instance Before Use
* This script is **very** invasive and makes thousands of changes to your database.
* Before using this script, [back up your Stash instance](https://docs.stashapp.cc/beginner-guides/backup-and-restore-database/).
  * Go to Settings > Tasks > Backup, then perform both Backup and Download Backup actions.
  * Make sure you are familiar with the [restore process](https://docs.stashapp.cc/beginner-guides/backup-and-restore-database/).
  * I would recommend testing out a restore before using this script.
* This was developed and tested against Stash v0.20.2 and v0.21.0.
  * If you are on something older, please update.
  * If you are on something newer, I cannot stress enough, **please perform a backup** before using this script.

## Known Issues
* Tags on Stashbox (StashDB) can have alias collisions if the same alias is associated with two or more tags. stashapp-tag-importer will ping pong aliases between tags on your local Stash instance when this occurs.
	* The only way to solve this is to submit an edit on Stashbox (StashDB) to remove the the duplicate aliases until only one remains on the correct tag.

## Features
* Stat logging and log output of changes to file ./stashdb_tag_importer.log.
* Caches tags from StashDB to local .json file for offline processing.
	* Automatically redownloads tags from StashDB if the StashDB tag count differs from local .json cache.
* Error handling for Stash API so operations aren't missed due to random Stash Database locks or other issues.
* Smart resolution of the following cases.
	* Local Tag does not exist.
		* Create tag.
	* Local Tag has alias that matches a StashDB tag.
		* Remove alias from old local tag.
		* Create tag.
		* Add new tag to all scenes, markers, galleries, and performers with old tag applied.
	* Local Tag exists, but should be alias of StashDB Tag.
		* Merge tag into main tag.
	* Alias for existing Local Tag does not exist.
		* Add alias to existing tag.
	* Alias already associated with different Local Tag.
		* Remove alias from incorrect local tag.
		* Add alias to correct local tag.
		* Add correct tag to all scenes, markers, galleries, and performers with incorrect tag applied.
	* Local Tag Name and / or Description is out of date.
		* Update Tag Name and / or Description.

## Installation
* Make sure you have Python 3.10 or higher installed.
* Install [poetry](https://python-poetry.org/docs/).
```
curl -sSL https://install.python-poetry.org | python3 -
```
* Clone or download this repository.
* In the repo, rename the `.env.example` file to `.env`, then edit it to include your Stashbox endpoint and API key, and your local Stash instance URL and API key.
* In the repo, run the following command to install required dependencies.
```
poetry install
```

## Usage
* In the repo, run the following command to execute the script.
```
poetry run python stash_tag_importer/main.py
```
