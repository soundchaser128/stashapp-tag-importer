# stashapp-tag-importer
Bulk imports all the tags on Stashbox (usually stashdb.org) into your Stash application.

## Usage instructions
* Make sure you have Python 3.10 or higher installed.
* Install [poetry](https://duckduckgo.com/?q=python+poetry&ia=web).
* Clone or download the ZIP file of this repository
* Adapt the `.env.example` file to your needs and rename it to `.env`
* Then, run the following commands:
```
# inside the repository
poetry install
poetry run python stash_tag_importer/main.py
```
