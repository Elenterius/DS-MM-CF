# Dataset DB
> ATM the resulting database is created with the dataset library (https://dataset.readthedocs.io/en/latest/) which does not create a proper relational DB.

# Tables

table: `tracked_project`

desc: helper table that stores the projects that are tracked

column | data type | desc |
----- | ---------- | ---- |
id | int | project id
slug | str | project slug
date_checked | int | when was the last time the project was checked for updates

---

table: `project` 

column | data type | Constraint | desc |      |
----- | ---------- | ------- | ---- | ----
id | int | primary key | CurseForge project id
slug | string | | slug of the project, used for the url
name | string | | project name
summary | string | | project summary
type | string | | project type | e.g. "mc-mods" or "modpacks"
logo | string | | url of the logo thumbnail
mc_version | string | | supported minecraft versions, comma separated | e.g. "1.16.5, Forge"
date_created | int | | when was the project was created | in epoch seconds
date_modified | int | | when was the project last updated | in epoch seconds
date_collected | int | | when was the mod info collected/updated | in epoch seconds

---

table: `project_authors` 

column | data type | desc |
----- | ---------- | ---- |
project_id | int | CurseForge project id
author_id | int | CurseForge author id
timestamp | int | if not up-to-date with newest project timestamp the member was removed

---

table: `author` 

column | data type | Constraint | desc |
----- | ---------- | ------- | ---- |
id | int | primary key | CurseForge author id
name | string  |  | author name

---

table: `project_downloads`

desc: total download count for project

column | data type | desc |
----- | ---------- | ---- |
project_id | int | CurseForge project id
download_count | int |total download count of the project
timestamp | int | when was the download count retrieved

---

table: `file`

desc: only contains files that are available (CF Core API doesn't provide archived/deleted file info)

column | data type | desc |
----- | ---------- | ---- |
project_id | int | CurseForge project id
file_id | int | id of the file associated with the project
display_name | string | display name
file_name | string | file name
release_type | int | 1 = Release, 2 = Beta, 3 = Alpha
mc_version | string | supported minecraft versions, comma separated
date_created | int | when was the file created
size | int | file size in bytes

---

table: `file_downloads`

desc: download count for files that are available (not archived/deleted)

column | data type | desc |
----- | ---------- | ---- |
project_id | int | CurseForge project id
file_id | int | id of the file associated with the project
download_count | int | download count of the file
timestamp | int | when was the download count retrieved

---

table: `file_dependencies`

desc: dependencies included by the file

column | data type | desc |
----- | ---------- | ---- |
project_id | int | CurseForge project id
file_id | int | id of the file associated with the project
dependency_project_id | int | project id of the dependency
dependency_file_id | int | id of the file the project depends on

# Views

view: `dependant_downloads`

column | data type | desc |
----- | ---------- | ---- |
project_id | int | CurseForge project id
name | str | dependant name
dependency_project_id | int | project id of the dependency
download_count | int | total download count of dependant including the dependency
timestamp | int | when was the download count retrieved
