# FlexAniDBSuite (FADBS)
## [![Codacy Badge](https://api.codacy.com/project/badge/Grade/4aafbe20b9e64f9f94987c92301940b1)](https://www.codacy.com/app/XVSS/FlexAniDBSuite?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=XVicarious/FlexAniDBSuite&amp;utm_campaign=Badge_Grade)

### *NOTE*
At the current point, this plugin suite is ***NOT*** suitable for everyday use. Things are changing all the time, including the database schema. And I am ***NOT*** updating the schema version as I work on it at this point. So if you want to use this, please understand you might have to do a `flexget database reset-plugin fadbs_lookup` between updates to master's HEAD. I am currently working on the first stable version [v0.1](https://github.com/XVicarious/FlexAniDBSuite/projects/1), so if you can wait, wait until that comes out.

### Introduction
AniDB is the premire data source for all things anime, largely thanks to it's dedicated userbase. If you want metadata for anime, this is where you want to go.

FADBS aims to enable as full of an automated workflow as possible with AniDB and your watching of anime. Use Flexget's `anidb_list` plugin to start yourself off.

### Planned Features
* Add files to your mylist
* Mediainfo plugin
* CReq missing files on AniDB
* Generate nfo for episodes, etc
* Hide tags that are marked as spoilers
* Exclude tags that are not marked as verified
* Choose the permanent or mean rating for series (mean is the mean of permanent and temporary votes)
* **You tell me**. I want to pack this suite as full of features as I can

### What Works
* The `anidb_list` plugin included in the base Flexget package works, and I suggest to use that to get this party started.
* Fetch AniDB anime entry, and parse the information into an object with `fadbs_lookup`
* Metadata by AniDB ID for anime
* Find anime by name
* Custom thresholds for separating genres vs tags (0-600, in increments of 100)
* Generate nfo files for series
