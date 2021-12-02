# DS-MM-CF
Get better Download Stats for Minecraft Mods hosted on CurseForge.

When you have a mod on CurseForge (CF) you will eventually realize that the download stats only show you the total download count. You won't know how many people directly downloaded your mod from the website and how many downloads are from modpacks.

This script utilizes the `CFCore API` and `ModpackIndex API` in order to figure out which modpacks include your mod. 
Then Each modpack file is checked to determine the download compositon of all of your public available mod files (archived files can't be querried using the CFCore api).

## Warning! ATM the Donwload Count is not in sync with the CF website
Currently the donwload count returned by the `CFCore API` is only updated if there are any changes detected to the mod info. That means the resulting download stats are a bit skewed.

**Workaround:**
You can update the description of your mod to manually trigger the update of the download count.

## How to get the Data
> You need a CurseForge Core API Key!

You can get the API key from https://core.curseforge.com/. 
Just login with a Google account and name your organisation with an arbitrary name, and you will automatically
get an API Key that can query mod and file data from the CFCore API.

### Example
```Python
import mod_data_collector
from dependency_resolver import DependencyResolver
from save_handlers import DatasetSaveHandler
from web_apis import ApiHelper

...

cf_api_key = "YOUR_CF_CORE_API_KEY"
mod_id = 492939  # Project Id (you can find it on the cf mod page) or use the CFCoreAPI to search for the mod by name

api_helper = ApiHelper(cf_api_key)
with DependencyResolver(api_helper, logger) as dependency_resolver:
  with DatasetSaveHandler("sqlite:///mod_stats.db", int(time.time())) as save_handler:
    mod_data_collector.collect_data(logger, save_handler, dependency_resolver, api_helper, mod_id)
```

## Structure of Database created by DatasetSaveHandler
https://github.com/Elenterius/DS-MM-CF/blob/main/db_schema.md

## Dashboard
To view the data you can run `python dashboard_app.py` for a simple dashboard web app (built with plotly dash and tailwindcss)
which displays some simple download stats.

<img alt="screenshot of the dashboard web app" src="dashboard_screenshot.png" title="Dashboard Screenshot" width="80%"/>
