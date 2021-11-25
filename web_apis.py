from typing import Optional

import requests
from requests import Response


class CFCoreApi:
	"""A simple helper class for the CurseForge Core API"""

	_api_key: str = None

	base_url: str = "https://api.curseforge.com"
	game_ids: dict = {
		"minecraft": 432,
	}

	def __init__(self, api_key):
		self._api_key = api_key

	def _get_standard_headers(self) -> dict:
		return {
			'Accept': 'application/json',
			'x-api-key': self._api_key
		}

	def get_mod(self, mod_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/mods/{mod_id}', headers=self._get_standard_headers(), timeout=5)

	def find_mod(self, query: dict) -> Response:
		return requests.get(f'{self.base_url}/v1/mods/search', headers=self._get_standard_headers(), params=query, timeout=5)

	def find_minecraft_mod(self, query: dict) -> Response:
		query['gameId'] = self.game_ids['minecraft']
		return self.find_mod(query)

	def find_minecraft_mod_by_name(self, mod_name: str) -> Response:
		query = {'gameId': self.game_ids['minecraft'], 'searchFilter': mod_name}
		return self.find_mod(query)

	def get_mod_desc(self, mod_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/mods/{mod_id}/description', headers=self._get_standard_headers(), timeout=5)

	def get_mod_file(self, mod_id: int, file_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/mods/{mod_id}/files/{file_id}', headers=self._get_standard_headers(), timeout=5)

	def get_mod_files(self, mod_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/mods/{mod_id}/files', headers=self._get_standard_headers(), timeout=5)


class ModpackIndexApi:
	"""A simple helper class for the Modpack Index API"""

	base_url: str = "https://www.modpackindex.com/api"

	def __init__(self):
		pass

	def _get_standard_headers(self) -> dict:
		return {
			'Accept': 'application/json'
		}

	def get_mod(self, mod_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/mod/{mod_id}', headers=self._get_standard_headers(), timeout=5)

	def find_mods(self, query: dict) -> Response:
		return requests.get(f'{self.base_url}/v1/mods', headers=self._get_standard_headers(), params=query, timeout=5)

	def find_mods_by_name(self, name: str) -> Response:
		query = {
			'name': name,
			'limit': '100',	'page': '1'
		}
		return self.find_mods(query)

	def get_mod_dependents(self, mod_id: int) -> Response:
		"""Returns the mod-packs that include this mod"""
		query = {'limit': '100', 'page': '1'}
		return requests.get(f'{self.base_url}/v1/mod/{mod_id}/modpacks', headers=self._get_standard_headers(), params=query, timeout=5)

	def get_modpack(self, modpack_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/modpack/{modpack_id}', headers=self._get_standard_headers(), timeout=5)

	def get_modpack_dependencies(self, modpack_id: int) -> Response:
		return requests.get(f'{self.base_url}/v1/modpack/{modpack_id}/mods', headers=self._get_standard_headers(), timeout=5)


class ApiHelper:
	"""A helper class that contains both apis and provides helper methods"""

	cf_api: CFCoreApi = None
	mpi_api: ModpackIndexApi = None

	def __init__(self, cf_api_key):
		self.cf_api = CFCoreApi(cf_api_key)
		self.mpi_api = ModpackIndexApi()

	def get_cf_modpack_ids(self, mpi_mod_id) -> Optional[list[int]]:
		response = self.mpi_api.get_mod_dependents(mpi_mod_id)  # TODO: handle pagination
		if response:
			result = response.json()
			if len(result['data']) > 0:
				modpack_ids = []
				for modpack in result['data']:
					modpack_ids.append(modpack['curse_info']['curse_id'])
				return modpack_ids
		return None

	def get_mpi_mod_id(self, cf_mod_id: int, cf_mod_name: str) -> Optional[int]:
		response = self.mpi_api.find_mods_by_name(cf_mod_name)
		if response:
			result = response.json()
			# we don't care about pagination
			# if the mod isn't in the first 100 entries, we can assume it can't be found
			if len(result['data']) > 0:
				for mod in result['data']:
					if mod['curse_info']['curse_id'] == cf_mod_id:
						return mod['id']
		return None

	def get_mod_dependents(self, cf_mod_id: int, cf_mod_name: str) -> Optional[list[int]]:
		mpi_mod_id = self.get_mpi_mod_id(cf_mod_id, cf_mod_name)
		if mpi_mod_id:
			return self.get_cf_modpack_ids(mpi_mod_id)
		return None
