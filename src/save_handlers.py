import abc
from datetime import datetime
import dataset


def parse_datetime_string(datetime_str: str) -> float:
	datetime_object = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S.%fZ')
	return datetime_object.timestamp()


class SaveHandlerInterface(metaclass=abc.ABCMeta):

	@classmethod
	def __subclasshook__(cls, subclass):
		return hasattr(subclass, 'save_project_info') and callable(subclass.save_project_info) or NotImplemented

	@abc.abstractmethod
	def is_saved_project_outdated(self, project_id: int, project_date_modified: str, project_download_count: int) -> bool:
		"""
		Check if the saved Project Data is outdated
		:param project_id:
		:param project_date_modified:
		:param project_download_count:
		:return:
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def save_project_info(self, p_id: int, slug: str, name: str, p_type: str, mc_versions: list[str], summary: str, logo_url: str, date_created: str, date_modified: str):
		"""
		Save Project Info
		:param p_id:
		:param slug:
		:param name:
		:param p_type:
		:param mc_versions:
		:param summary:
		:param logo_url:
		:param date_created:
		:param date_modified:
		:return:
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def save_project_authors(self, project_id: int, authors: list[dict]):
		"""
		Save Project Authors
		:param project_id:
		:param authors:
		:return:
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def save_project_download_count(self, project_id: int, download_count: int):
		"""
		Save Project Downloads
		:param project_id:
		:param download_count:
		:return:
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def save_file_info(self, project_id: int, file_id: int, release_type: str, mc_versions: list[str], display_name: str, file_name: str, date_created: int, file_length: int):
		"""
		Save Project Downloads
		:param project_id:
		:param file_id:
		:param release_type: Unknown, Release, Beta, Alpha
		:param mc_versions:
		:param display_name:
		:param file_name:
		:param date_created:
		:param file_length: in bytes
		:return:
		"""
		raise NotImplementedError

	@abc.abstractmethod
	def save_file_download_count(self, project_id: int, file_id: int, download_count: int):
		"""
		Save File Downloads
		:param project_id:
		:param file_id:
		:param download_count:
		:return:
		"""
		pass

	def save_file_dependency(self, project_id: int, file_id: int, dependency_project_id: int, dependency_file_id: int):
		"""
		Save File Dependency
		:param project_id:
		:param file_id:
		:param dependency_project_id:
		:param dependency_file_id:
		:return:
		"""
		pass


# TODO create JsonSaveHandler
# class JsonSaveHandler(SaveHandlerInterface)


class DatasetSaveHandler(SaveHandlerInterface):

	def __init__(self, db_url: str, timestamp: int):
		"""
		:param db_url: SQLite, PostgreSQL or MySQL
		:param timestamp: when was the data collected/saved
		"""
		self.timestamp = timestamp

		# TODO: use transactions? e.g. transaction can be used through context manager, db changes will be thrown away when an exception occurs
		self.db = dataset.connect(db_url)
		self._setup_db()

	def _setup_db(self):
		import db_util
		if 'dependant_downloads' not in self.db.views:
			db_util.create_view_dependant_downloads(self.db)

	def is_saved_project_outdated(self, project_id: int, project_date_modified: str, project_download_count: int) -> bool:
		if self.db.has_table('project'):
			result = self.db['project'].find_one(id=project_id)
			if result and parse_datetime_string(project_date_modified) > result['date_modified']:
				return True

		if self.db.has_table('project_downloads'):
			import db_util
			for row in db_util.get_project_download_count_latest(self.db, project_id):
				return row['download_count'] != project_download_count

		return True

	def save_project_info(self, p_id: int, slug: str, name: str, p_type: str, mc_versions: list[str], summary: str, logo_url: str, date_created: str, date_modified: str):
		self.db['project'].upsert(dict(
			id=p_id,  # primary key
			slug=slug, name=name,
			type=p_type,
			mc_version=", ".join(mc_versions),
			summary=summary,
			logo=logo_url,
			date_created=parse_datetime_string(date_created),
			date_modified=parse_datetime_string(date_modified),
			date_collected=self.timestamp  # when was the mod info collected/updated
		), ['id'])

	def save_project_authors(self, project_id: int, authors: list[dict]):
		for author in authors:
			self.db['project_authors'].upsert(dict(
				project_id=project_id,
				author_id=author['id'],
				timestamp=self.timestamp  # if not up-to-date with newest project timestamp the member was removed
			), ['project_id', 'author_id'])

			self._save_author(author['id'], author['name'])

	def _save_author(self, a_id: int, name: str):
		# upsert because the name could change
		self.db['author'].upsert(dict(id=a_id, name=name), ['id'])

	def save_project_download_count(self, project_id: int, download_count: int):
		self.db['project_downloads'].insert(dict(
			project_id=project_id,
			download_count=download_count,
			timestamp=self.timestamp
		))

	def save_file_info(self, project_id: int, file_id: int, release_type: str, mc_versions: list[str], display_name: str, file_name: str, date_created: int, file_length: int):
		self.db['file'].upsert(dict(
			project_id=project_id, file_id=file_id,  # both ids are needed to uniquely identified a file
			display_name=display_name, file_name=file_name,
			release_type=release_type,
			mc_versions=", ".join(mc_versions),
			date_created=date_created,
			size=file_length
		), ['project_id', 'file_id'])

	def save_file_download_count(self, project_id: int, file_id: int, download_count: int):
		self.db['file_downloads'].insert(dict(
			project_id=project_id, file_id=file_id,
			download_count=download_count,
			timestamp=self.timestamp
		))

	def save_file_dependency(self, project_id: int, file_id: int, dependency_project_id: int, dependency_file_id: int):
		self.db['file_dependencies'].insert_ignore(dict(
			project_id=project_id, file_id=file_id,
			dependency_project_id=dependency_project_id, dependency_file_id=dependency_file_id
		), ['id', 'project_id', 'dependency_project_id', 'dependency_file_id'])
