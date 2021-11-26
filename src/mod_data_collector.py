import logging

import requests

from dependency_resolver import DependencyResolverInterface, Dependency
from save_handlers import SaveHandlerInterface
from web_apis import ApiHelper


def store_project_info(save_handler: SaveHandlerInterface, data: dict):
	save_handler.save_project_info(
		p_id=data['id'], slug=data['slug'], name=data['name'], summary=data['summary'],
		p_type=data['links']['websiteUrl'].split("/")[-2],
		logo_url=data['logo']['thumbnailUrl'],
		mc_versions=[lfi['gameVersion'] for lfi in data['latestFilesIndexes']],  # data['latestFilesIndexes'][0]['gameVersion']
		date_created=data['dateCreated'], date_modified=data['dateModified']
	)
	store_project_authors(save_handler, data)
	store_download_count(save_handler, data)


def store_download_count(save_handler: SaveHandlerInterface, data: dict):
	save_handler.save_project_download_count(data['id'], int(data['downloadCount']))


def store_project_authors(save_handler: SaveHandlerInterface, data: dict):
	save_handler.save_project_authors(data['id'], data['authors'])


def parse_release_type(type_id: int) -> str:
	names = ["Unknown", "Release", "Beta", "Alpha"]
	if type_id > 3 or type_id < 1:
		type_id = 0
	return names[type_id]


def store_files(save_handler: SaveHandlerInterface, files: dict):
	for file in files:
		store_file_info(save_handler, file)


def store_file_info(save_handler: SaveHandlerInterface, data: dict):
	save_handler.save_file_info(
		project_id=data['modId'], file_id=data['id'],
		release_type=parse_release_type(data['releaseType']),
		display_name=data['displayName'],
		file_name=data['fileName'],
		mc_versions=data['gameVersions'],
		date_created=data['fileDate'],
		file_length=data['fileLength']
	)
	store_file_download_count(save_handler, data)


def store_file_download_count(save_handler: SaveHandlerInterface, data: dict):
	save_handler.save_file_download_count(project_id=data['modId'], file_id=data['id'], download_count=int(data['downloadCount']))


def store_file_dependency(save_handler: SaveHandlerInterface, data: dict, dependency: Dependency):
	save_handler.save_file_dependency(
		project_id=data['modId'], file_id=data['id'],
		dependency_project_id=dependency.project_id, dependency_file_id=dependency.file_id
	)


def is_stored_project_outdated(save_handler: SaveHandlerInterface, data: dict):
	return save_handler.is_saved_project_outdated(data['id'], data['dateModified'], int(data['downloadCount']))


def collect_data(logger: logging.Logger, save_handler: SaveHandlerInterface, dependency_resolver: DependencyResolverInterface, api_helper: ApiHelper, mod_id: int, max_file_length: float = 4e7, force=False) -> bool:
	"""
	:param logger:
	:param api_helper:
	:param dependency_resolver:
	:param save_handler: save handler for storing the collected mod data
	:param mod_id: CurseForge mod id
	:param max_file_length: the max file size that is allowed to be downloaded (e.g. 4e7 = 40MB)
	:param force: force the script to anyways collect the data even if the download count hasn't changed
	:return:
	"""

	try:
		response = api_helper.cf_api.get_mod(mod_id)
		response.raise_for_status()
		project = response.json()["data"]
	except requests.RequestException as error:
		logger.error(f"Failed to query project info for id <{mod_id}> -> CFCore API: {error}")
		return False

	if not force and not is_stored_project_outdated(save_handler, project):
		logger.warning(f"Skipping data collection for project <{project['slug']}> because the project data didn't change")
		return False

	logger.info("Storing Project Info...")
	store_project_info(save_handler, project)

	logger.info("Fetching Project Files Info...")
	try:
		response = api_helper.cf_api.get_mod_files(mod_id)  # TODO: handle pagination
		response.raise_for_status()
		files = response.json()["data"]
	except requests.RequestException as error:
		logger.error(f"Failed to query files info for project <{project['slug']}> -> CFCore API: {error}")
		return False

	if len(files) > 0:
		store_files(save_handler, files)
	else:
		logger.warning("No Project Files Found")
		return False

	_collect_data_for_project_dependents(logger, save_handler, dependency_resolver, api_helper, project['id'], project['name'], project['slug'], max_file_length)


def _collect_data_for_project_dependents(logger: logging.Logger, save_handler: SaveHandlerInterface, dependency_resolver: DependencyResolverInterface, api_helper: ApiHelper, project_id: int, project_name: str, project_slug: str, max_file_length: float = 4e7) -> bool:
	dependents, files = dependency_resolver.get_project_dependents(project_id, project_name)

	if len(dependents) > 0:
		logger.info("Storing dependents Info...")
		for dependant in dependents:
			store_project_info(save_handler, dependant)

	for file_identifier in files:
		try:
			response = api_helper.cf_api.get_mod_file(file_identifier.project_id, file_identifier.file_id)
			response.raise_for_status()
			file = response.json()["data"]
		except requests.RequestException as error:
			logger.error(f"Failed to query file info for <{file_identifier}> -> CFCore API: {error}")
			continue

		logger.debug(f"Checking if the file <{file['fileName']}> depends on the project <{project_name}>")
		dependency = dependency_resolver.get_file_dependency(file_identifier, project_id)
		if dependency:
			store_file_info(save_handler, file)
			store_file_dependency(save_handler, file, dependency)
		else:
			logger.warning(f"Skipping file <{file['fileName']}> -> Unable to determine the files dependencies")
			logger.warning(f"Skipping file <{file['fileName']}> -> File is does not depend on <{project_slug}>")
