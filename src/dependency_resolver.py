import abc
import json
import logging
import os
import time
import zipfile
from typing import Optional

import dataset
import requests
from dataset import Database, Table

from web_apis import ApiHelper


class FileIdentifier:
	def __init__(self, project_id: int, file_id: int):
		self.project_id: int = project_id
		self.file_id: int = file_id


class Dependency(FileIdentifier):
	def __init__(self, project_id: int, file_id: int):
		super().__init__(project_id, file_id)


class Dependant(FileIdentifier):
	def __init__(self, project_id: int, file_id: int):
		super().__init__(project_id, file_id)


class DependencyResolverInterface(metaclass=abc.ABCMeta):

	@abc.abstractmethod
	def is_file_depending_on_project(self, file: FileIdentifier, project_id: int) -> bool:
		raise NotImplementedError

	@abc.abstractmethod
	def get_project_dependents(self, project_id: int, project_name: str) -> [list, list[FileIdentifier]]:
		"""
		Get all files that depend on this project

		:param project_id:
		:param project_name:
		:return: list of file dependents
		"""
		raise NotImplementedError

	# @abc.abstractmethod
	# def get_file_dependents(self, file: FileIdentifier) -> list[Dependant]:
	# 	raise NotImplementedError

	@abc.abstractmethod
	def get_file_dependency(self, file: FileIdentifier, project_id: int) -> Optional[Dependency]:
		"""
		If the file depends on the given project returns the exact file dependency

		:param file:
		:param project_id:
		:return:
		"""
		raise NotImplementedError


class DependencyResolver(DependencyResolverInterface):

	def __init__(self, api_helper: ApiHelper, logger: logging.Logger, db_url="sqlite:///dependencies.db", temp_download_folder_path: str = "/temp"):
		self.logger: logging.Logger = logger
		self.apiHelper = api_helper
		self.tempFolderPath = temp_download_folder_path
		self.db: Database = dataset.connect(db_url)
		self._init_db()

	def _init_db(self):
		db = self.db
		if not db.has_table('file'):
			table: Table = db.create_table('file')
			table.create_column('project_id', db.types.integer)
			table.create_column('file_id', db.types.integer)
			table.create_column('dependency_count', db.types.integer)

		if not db.has_table('dependency'):
			table: Table = db.create_table('dependency', primary_id=False)
			table.create_column('project_id', db.types.integer)
			table.create_column('file_id', db.types.integer)
			table.create_column('dependency_project_id', db.types.integer)
			table.create_column('dependency_file_id', db.types.integer)
			table.create_index(['project_id', 'file_id', 'dependency_project_id'])

	def is_file_depending_on_project(self, file: FileIdentifier, project_id: int) -> bool:
		if self.db['dependency'].find_one(project_id=file.project_id, file_id=file.file_id, dependency_project_id=project_id):
			return True
		return False

	def get_file_dependency(self, file: FileIdentifier, project_id: int) -> Optional[Dependency]:
		result = self.db['dependency'].find_one(project_id=file.project_id, file_id=file.file_id, dependency_project_id=project_id)
		if result:
			return Dependency(project_id, result['dependency_file_id'])
		return None

	def get_project_dependents(self, project_id: int, project_name: str) -> [list, list[FileIdentifier]]:
		dependents_ids = self.apiHelper.get_mod_dependents(project_id, project_name)
		if not dependents_ids:
			self.logger.warning("No Dependents Found")
			return [], []

		self.logger.info(f'Found {len(dependents_ids)} dependents')
		try:
			response = self.apiHelper.cf_api.get_mods(dependents_ids)
			response.raise_for_status()
			dependents = response.json()["data"]
		except requests.RequestException as error:
			self.logger.error(f"Failed to query dependents info for project id <{project_id}> -> CFCore API: {error}")
			return [], []

		resolved_files = []
		resolved_dependents = []
		for dependant in dependents:
			dependencies = self._resolve_project_dependencies(dependant)
			if len(dependencies) > 0:
				resolved_dependents.append(dependant)
				for dependency in dependencies:
					resolved_files.append(dependency)

		return resolved_dependents, resolved_files

	def _are_file_dependencies_resolved(self, file: FileIdentifier) -> bool:
		result = self.db['file'].find_one(project_id=file.project_id, file_id=file.file_id)
		if result:
			target = result['dependency_count']
			resolved = self.db['dependency'].count(project_id=file.project_id, file_id=file.file_id)
			if resolved != target:
				return False
		else:
			return False

	def _resolve_project_dependencies(self, dependant: dict, skip_zero_downloads=False, max_file_length: float = 4e7) -> list[FileIdentifier]:
		self.logger.info(f'Checking dependant <{dependant["name"]}>...')
		if skip_zero_downloads and dependant['downloadCount'] == 0:
			self.logger.warning(f"Skipping project <{dependant['name']}> with 0 downloads -> 'skip_zero_downloads' is set to True")

		try:
			response = self.apiHelper.cf_api.get_mod_files(dependant['id'])  # TODO: handle pagination
			response.raise_for_status()
			files = response.json()["data"]
		except requests.RequestException as error:
			self.logger.error(f"Failed to query project files for id <{dependant['id']}> -> CFCore API: {error}")
			return []

		self.logger.info(f'found {len(files)} files')
		resolved_dependencies = []

		for file in files:
			file_identifier = FileIdentifier(file['modId'], file['id'])

			self.logger.debug("Checking if the file dependencies are already resolved")
			if self._are_file_dependencies_resolved(file_identifier):
				resolved_dependencies.append(file_identifier)
				self.logger.debug(f"Skipping file <{file['fileName']}> -> dependencies are resolved")
				continue

			if skip_zero_downloads and file['downloadCount'] == 0:
				self.logger.warning(f"Skipping file <{file['fileName']}> with 0 downloads -> 'skip_zero_downloads' is set to True")
				continue

			if not self._resolve_file_dependencies(file_identifier, file['fileName'], file['downloadUrl'], file['fileLength'], max_file_length):
				self.logger.error(f"Failed to properly resolve dependencies for <{file['fileName']}>")
				continue

			resolved_dependencies.append(file_identifier)

		return resolved_dependencies

	def _resolve_file_dependencies(self, file: FileIdentifier, file_name: str, file_url: str, file_length: float, max_file_length: float, delete_temp_file=True) -> bool:
		if file_length > max_file_length:
			self.logger.warning(f"Skipping file <{file['fileName']}> -> File length of {file_length / 1e6} MB is larger than {max_file_length / 1e6} MB")
			return False

		success: bool = False
		if self._download_file(file, file_name, file_url, max_file_length):
			start_time = time.perf_counter()
			if self._parse_file(file):
				self.logger.debug(f"Parsing file <{file_name}> took {time.perf_counter() - start_time} seconds")
				success = True

		if delete_temp_file:
			file_path = f"{self.tempFolderPath}/{file.project_id}_{file.file_id}"
			if os.path.exists(file_path):
				os.remove(file_path)

		return success

	def _download_file(self, file: FileIdentifier, file_name: str, file_url: str, max_file_length: float) -> bool:
		try:
			response = requests.head(file_url, allow_redirects=True, timeout=5)
			response.raise_for_status()
			header = response.headers
			content_length = header.get('content-length', None)
			if content_length and int(content_length) > max_file_length:
				self.logger.error(f"Skipping download of file <{file_name}> -> File length of {int(content_length) / 1e6} MB is larger than {max_file_length / 1e6} MB")
				return False
		except requests.RequestException as error:
			self.logger.error(f"Failed to download headers for file <{file_name}> -> {error}")
			return False

		os.makedirs(self.tempFolderPath, exist_ok=True)
		file_path = f"{self.tempFolderPath}/{file.project_id}_{file.file_id}"

		start_time = time.perf_counter()
		try:
			response = requests.get(file_url, allow_redirects=True, timeout=5)
			response.raise_for_status()
			with open(file_path, 'wb') as f:
				f.write(response.content)
				self.logger.debug(f"Downloading file <{file_name}> took {time.perf_counter() - start_time} seconds")
				return True
		except requests.RequestException as error:
			self.logger.error(f"Failed to download file <{file_name}> -> {error}")
			pass
		except IOError as error:
			self.logger.error(f"Failed to save file <{file_name}> as <{file_path}> -> {error}")
			pass

		return False

	def _parse_file(self, file: FileIdentifier) -> bool:
		file_path = f"{self.tempFolderPath}/{file.project_id}_{file.file_id}"
		assert os.path.exists(file_path)

		with zipfile.ZipFile(file_path) as z:
			if 'manifest.json' in z.namelist():
				return self._parse_file_manifest(file, z)
			else:
				# TODO: find mod jars and get fingerprints and identify mod file with CF Core API
				self.logger.error("Missing manifest.json")
				return False

	def _parse_file_manifest(self, file: FileIdentifier, zip_file: zipfile.ZipFile) -> bool:
		with zip_file.open('manifest.json') as f:
			data = json.load(f)
			if "files" in data:
				projects = data["files"]

				self.db['file'].upsert(dict(
					project_id=file.project_id, file_id=file.file_id, dependency_count=len(projects)
				))

				for project in projects:
					self.db['dependency'].insert_ignore(dict(
						project_id=file.project_id, file_id=file.file_id,
						dependency_project_id=project["projectID"], dependency_file_id=project["fileID"]
					), ['project_id', 'file_id', 'dependency_project_id', 'dependency_file_id'])
				return True

		return False
