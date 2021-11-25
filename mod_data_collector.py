import json
import logging
import os
import time
import zipfile
from datetime import datetime
from typing import Optional

import dataset
import requests
from dataset import Database, Table

import db_util
from web_apis import ApiHelper

# configure logger
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s]:: %(message)s'))
logger = logging.getLogger("ModDataCollector")
logger.setLevel(logging.DEBUG)
logger.addHandler(console_handler)


def parse_datetime_string(datetime_str: str) -> float:
	datetime_object = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%fZ')
	return datetime_object.timestamp()


def store_project_info(db: Database, data: dict, timestamp: int):
	db['project'].upsert(dict(
		id=data['id'],  # primary key
		slug=data['slug'],
		name=data['name'],
		summary=data['summary'],
		type=data['links']['websiteUrl'].split("/")[-2],
		logo=data['logo']['thumbnailUrl'],
		mc_version=", ".join([lfi['gameVersion'] for lfi in data['latestFilesIndexes']]),  # data['latestFilesIndexes'][0]['gameVersion']
		date_created=parse_datetime_string(data['dateCreated']),
		date_modified=parse_datetime_string(data['dateModified']),
		# license=project_license,
		date_collected=timestamp  # when was the mod info collected/updated
	), ['id'])


def store_authors(db: Database, data: dict, timestamp: int):
	for author in data['authors']:
		db['project_authors'].upsert(dict(
			project_id=data['id'],
			author_id=author['id'],
			timestamp=timestamp  # if not up-to-date with newest project timestamp the member was removed
		), ['project_id', 'author_id'])

		# upsert because the name could change
		db['author'].upsert(dict(
			id=author['id'],  # primary key
			name=author['name']
		), ['id'])


def store_download_count(db: Database, data: dict, timestamp: int):
	db['project_downloads'].insert(dict(
		project_id=data['id'],
		download_count=int(data['downloadCount']),
		timestamp=timestamp
	))


def store_files(db: Database, data: dict, timestamp: int):
	for file in data:
		store_file(db, file, timestamp)


def store_file(db: Database, data: dict, timestamp: int):
	table: Table = db['file']
	table.upsert(dict(
		project_id=data['modId'], file_id=data['id'], # both ids are needed to uniquely identified a file
		display_name=data['displayName'],
		file_name=data['fileName'],
		release_type=data['releaseType'],
		mc_version=" ".join(data['gameVersions']),
		date_created=data['fileDate'],
		size=data['fileLength']
	), ['project_id', 'file_id'])

	db['file_downloads'].insert(dict(
		project_id=data['modId'], file_id=data['id'],
		download_count=int(data['downloadCount']),
		timestamp=timestamp
	))


def store_file_dependency(db: Database, data: dict, dependency: dict):
	db['file_dependencies'].insert_ignore(dict(
		project_id=data['modId'], file_id=data['id'],
		dependency_id=dependency['project_id'], file_dependency_id=dependency['file_id']
	), ['id', 'project_id', 'dependency_id', 'file_dependency_id'])


def update_project_tracker(db: Database, project: dict, timestamp: int):
	logger.debug("Updating Project Tracker")
	table: Table = db['tracked_project']
	table.upsert(dict(
		id=project['id'], slug=project['slug'],
		date_checked=timestamp
	), ['id'])


def is_stored_data_outdated(db: Database, project: dict) -> bool:
	if db.has_table('project'):
		result = db['project'].find_one(id=project['id'])
		if result and parse_datetime_string(project['dateModified']) > result['date_modified']:
			return True

	if db.has_table('project_downloads'):
		for row in db_util.get_project_download_count_latest(db, project['id']):
			return row['download_count'] != int(project['downloadCount'])

	return True


def collect_data(mod_id: int, db_path: str, cf_api_key: str, max_file_length: float = 4e7, force=False):
	"""
	Note: ATM the resulting database is created with the dataset lib which does not create a proper relational DB.\n
	It's a derpy db that is more akin to a nosql-db and has no proper primary/foreign key relationships, constraints, etc. setup.\n

	:param mod_id: CurseForge mod id
	:param db_path: SQLite, PostgreSQL or MySQL
	:param cf_api_key: CurseForge CoreAPI key
	:param max_file_length: the max file size that is allowed to be downloaded (e.g. 4e7 = 40MB)
	:param force: force the script to anyways collect the data even if the download count hasn't changed
	:return:
	"""
	timestamp = int(time.time())
	api_helper: ApiHelper = ApiHelper(cf_api_key)

	# TODO: use transactions? e.g. transaction can be used through context manager, db changes will be thrown away when an exception occurs
	db: Database = dataset.connect(db_path)

	if 'dependant_downloads' not in db.views:
		db_util.create_view_dependant_downloads(db)

	response = api_helper.cf_api.get_mod(mod_id)  # TODO: proper exception handling
	if response:
		project = response.json()["data"]
		update_project_tracker(db, project, timestamp)

		if force or is_stored_data_outdated(db, project):
			logger.info("Storing Project Info...")
			store_project_info(db, project, timestamp)
			store_authors(db, project, timestamp)
			store_download_count(db, project, timestamp)

			logger.info("Fetching Project Files Info...")
			response = api_helper.cf_api.get_mod_files(mod_id)  # TODO: handle pagination
			if response:
				files = response.json()["data"]
				if len(files) > 0:
					store_files(db, files, timestamp)
				else:
					logger.warning("No Project Files Found")

				_collect_dependents_data(db, api_helper, project, timestamp, max_file_length)
			else:
				logger.error(f"CFCore API Request Failed: {response.status_code}")
		else:
			logger.warning(f"Skipping data collection for project <{project['slug']}> because the download_count ({int(project['downloadCount'])}) didn't change")
	else:
		logger.error(f"CFCore API Request Failed: {response.status_code}")

	db.close()


def _collect_dependents_data(db: Database, api_helper: ApiHelper, dependency: dict, timestamp: int, max_file_length: float = 4e7):
	dependents_ids = api_helper.get_mod_dependents(dependency['id'], dependency['name'])
	if not dependents_ids:
		logger.warning("No Dependents Found")
		return

	logger.info(f'Found {len(dependents_ids)} dependents')
	for dependant_id in dependents_ids:

		response = api_helper.cf_api.get_mod(dependant_id)
		if response:
			project = response.json()["data"]
			logger.info(f'Checking dependant <{project["name"]}>...')
			if project['downloadCount'] == 0:
				logger.warning(f"Skipping dependant <{project['name']}> -> Project has 0 downloads")
				continue

			store_project_info(db, project, timestamp)
			store_authors(db, project, timestamp)
			store_download_count(db, project, timestamp)

			response = api_helper.cf_api.get_mod_files(dependant_id)  # TODO: handle pagination
			if not response:
				logger.error(f"CFCore API Request Failed: {response.status_code}")
				continue

			files = response.json()["data"]
			logger.info(f'found {len(files)} files')
			for file in files:
				if file['downloadCount'] < 1:
					logger.warning(f"Skipping file <{file['fileName']}> -> File has 0 downloads")
					continue

				file_length = file['fileLength']
				if file_length > max_file_length:
					logger.warning(f"Skipping file <{file['fileName']}> -> File length of {file_length/1e6} MB is larger than {max_file_length/1e6} MB")
					continue

				result, file_dependency_id = is_file_depending_on_mod(db, file, max_file_length, dependency['id'])
				if result is None:
					logger.warning(f"Skipping file <{file['fileName']}> -> Unable to determine the files dependencies")
					continue

				if file_dependency_id > -1:
					store_file(db, file, timestamp)
					store_file_dependency(db, file, {'project_id': dependency['id'], 'file_id': file_dependency_id})
				else:
					logger.warning(f"Skipping file <{file['fileName']}> -> File is does not depend on <{dependency['slug']}>")


def is_file_depending_on_mod(db: Database, file: dict, max_file_length: float, mod_id: int) -> (Optional[bool], int):
	logger.debug("Checking if the file dependency is already resolved")
	table: Table = db['file_dependencies']
	results = table.find(project_id=file['modId'], file_id=file['id'], dependency_id=mod_id)
	for row in results:
		dep_id = row['file_dependency_id']  # we have to check if the id is set (legacy reasons, db could be missing this value)
		if dep_id:
			logger.debug("Found resolved file dependency")
			return True, dep_id

	# download the file to parse the manifest.json file for dependencies
	file_url = file['downloadUrl']
	response = requests.head(file_url, allow_redirects=True, timeout=5)
	if response:
		header = response.headers
		content_length = header.get('content-length', None)
		if content_length and int(content_length) > max_file_length:
			return None, -1
	else:
		logger.error(f"Unable to download headers for file <{file['fileName']}>")
		return None, -1

	result = None
	file_id = -1
	start_time = time.perf_counter()
	response = requests.get(file_url, allow_redirects=True, timeout=5)
	if response:
		temp_file = "temp.file"
		with open(temp_file, 'wb') as f:
			f.write(response.content)

		logger.debug(f"Downloading file <{file['fileName']}> took {time.perf_counter() - start_time} seconds")
		start_time = time.perf_counter()

		with zipfile.ZipFile(temp_file) as z:
			for f_name in z.namelist():
				if f_name == 'manifest.json':
					result = False
					with z.open(f_name) as f:
						data = json.load(f)
						if "files" in data:
							for project in data["files"]:
								if project["projectID"] == mod_id:
									result = True
									file_id = project["fileID"]
									break
					break

		logger.debug(f"Parsing file <{file['fileName']}> took {time.perf_counter() - start_time} seconds")

		# delete temp file
		if os.path.exists(temp_file):
			os.remove(temp_file)

	return result, file_id
