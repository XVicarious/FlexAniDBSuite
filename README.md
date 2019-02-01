# FlexAniDBSuite (FADBS)
## [![Codacy Badge](https://api.codacy.com/project/badge/Grade/4aafbe20b9e64f9f94987c92301940b1)](https://www.codacy.com/app/XVSS/FlexAniDBSuite?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=XVicarious/FlexAniDBSuite&amp;utm_campaign=Badge_Grade)

### Introduction
AniDB is the premire data source for all things anime, largely thanks to it's dedicated userbase. If you want metadata for anime, this is where you want to go.

FADBS aims to enable as full of an automated workflow as possible with AniDB and your watching of anime. Use Flexget's `anidb_list` plugin to start yourself off.

### Planned Features
* Add files to your mylist
* Mediainfo plugin
* CReq missing files on AniDB
* Generate nfo for series, episodes, etc
* Custom thresholds for separating genres vs tags (0-600, in increments of 100)
* Hide tags that are marked as spoilers
* Exclude tags that are not marked as verified
* Choose the permanent or mean rating for series (mean is the mean of permanent and temporary votes)
* **You tell me**. I want to pack this suite as full of features as I can

### What Works
* The `anidb_list` plugin included in the base Flexget package has an open pull request to fix it. This plugin, despite it's name is to fetch your wishlist
* Fetch AniDB anime entry, and parse the information into an object with `fadbs_lookup`
* Metadata by AniDB ID for anime
* Find anime by name
