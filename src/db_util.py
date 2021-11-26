from dataset import Database, Table
from dataset.util import ResultIter


def create_view_dependant_downloads(db: Database):
	db.query("""
	CREATE VIEW dependant_downloads AS
	SELECT project_id, name, dependency_project_id, SUM(download_count) AS download_count, timestamp
	FROM (
		SELECT b.project_id, c.name, b.file_id, a.dependency_project_id, download_count, timestamp
		FROM file_downloads b
			JOIN file_dependencies a ON b.project_id = a.project_id AND b.file_id = a.file_id
			JOIN project c ON b.project_id = c.id
		GROUP BY b.project_id, b.file_id, a.dependency_project_id, timestamp
	)
	GROUP BY timestamp, dependency_project_id, project_id
	""")


def get_tracked_projects_with_logo(db: Database):
	return db.query(f"""
		SELECT a.*, b.logo
			FROM tracked_project a
			JOIN project b ON a.id = b.id
	""")


def get_project_download_count_latest(db: Database, mod_id: int):
	return db.query(f"""
		SELECT download_count, MAX(timestamp) AS timestamp
			FROM project_downloads
		WHERE project_id = {mod_id}
	""")


def get_project_downloads_by_composition(db: Database, mod_id: int):
	return db.query(f"""
	SELECT a.dependency_project_id AS project_id, b.download_count AS total_download_count, SUM(a.download_count) AS dependant_download_count, b.download_count - SUM(a.download_count) AS direct_download_count, b.timestamp
		FROM
			(dependant_downloads a INNER JOIN project_downloads b ON a.dependency_project_id = b.project_id AND a.timestamp = b.timestamp)
		WHERE a.dependency_project_id = {mod_id}
		GROUP BY a.dependency_project_id, a.timestamp;
	""")


def get_project_downloads_by_origin(db: Database, mod_id: int):
	return db.query(f"""
	SELECT project_id, name, download_count, 100 * CAST(download_count AS FLOAT) / SUM(download_count) OVER (PARTITION BY timestamp) AS percentage, timestamp
	FROM
		(
		SELECT project_id, name, SUM(download_count) AS download_count, timestamp
			FROM dependant_downloads
			WHERE dependency_project_id = {mod_id}
			GROUP BY dependency_project_id, project_id, timestamp
		UNION ALL
		SELECT a.dependency_project_id AS project_id, "CurseForge Mod Page" AS name, b.download_count - SUM(a.download_count) AS download_count, b.timestamp
			FROM dependant_downloads a
				INNER JOIN project_downloads b ON a.dependency_project_id = b.project_id AND a.timestamp = b.timestamp
			WHERE a.dependency_project_id = {mod_id}
			GROUP BY a.dependency_project_id, a.timestamp
		)
	""")


def get_project_authors(db: Database, mod_id: int):
	return db.query(f"""
	SELECT pa.author_id, a.name, pa.timestamp
		FROM project_authors pa
			JOIN author a ON a.id = pa.author_id
		WHERE pa.project_id = {mod_id}
	""")


def get_project_downloads_by_file(db: Database, mod_id: int):
	return db.query(f"""
	SELECT fd.project_id, f.file_id, f.file_name, download_count, timestamp
		FROM file_downloads fd
			JOIN file f ON f.file_id = fd.file_id AND f.project_id = fd.project_id
		WHERE fd.project_id = {mod_id}
		GROUP BY fd.file_id, timestamp;
	""")


def get_project_file_downloads_total(db: Database, mod_id: int):
	return db.query(f"""
	SELECT project_id, SUM(download_count) AS download_count, timestamp
		FROM file_downloads
		WHERE project_id = {mod_id}
		GROUP BY project_id, timestamp;
	""")


def get_project_dependents(db: Database, mod_id: int):
	return db.query(f"""
	SELECT a.id AS project_id, a.name
		FROM
			(project a INNER JOIN file_dependencies b ON a.id = b.project_id)
		WHERE dependency_project_id = {mod_id}
		GROUP BY a.id, dependency_project_id;
	""")


def get_dependant_downloads_total(db: Database, mod_id: int):
	return db.query(f"""
	SELECT project_id, name, SUM(download_count) AS download_count, timestamp
		FROM dependant_downloads
		WHERE dependency_project_id = {mod_id}
		GROUP BY dependency_project_id, project_id, timestamp;
	""")
