# DS-MM-CF
Get Download Stats for Minecraft Mods hosted on CurseForge

## How to get the Data
> You need a CurseForge Core API Key!

You can get the API key from https://core.curseforge.com/. 
Just login with a Google account and name your organisation with an arbitrary name, and you will automatically
get an API Key that can query mod and file data from the CFCoreAPI.

### Example
```Python
db_path = "sqlite:///db/mod_stats.db"  # SQLite, PostgreSQL or MySQL
cf_api_key = "YOUR_CURSE_FORGE_CORE_API_KEY"
mod_id = 420_420  # CF Project Id (you can find it on the cf mod page)

import mod_data_collector
# produces a database containing the data
mod_data_collector.collect_data(mod_id, db_path, cf_api_key, force=True)
```
> **NOTE**
> <br>
> ATM the resulting database is created with the dataset library (https://dataset.readthedocs.io/en/latest/) which does not create a proper relational DB.
> <br>It's a derpy db that is more akin to a nosql-db and has no proper primary/foreign key relationships, constraints, etc. setup. 
> This doesn't impede the ability to query the db.

## Database Structure
https://github.com/Elenterius/DS-MM-CF/blob/main/db_schema.md

## Dashboard
To view the data you can run `dashboard_app.py` for a simple dashboard app server (built with plotly dash and tailwindcss)
which displays some simple download stats.
