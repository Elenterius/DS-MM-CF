import logging
import time

import dataset
from dataset import Table

import mod_data_collector
from dependency_resolver import DependencyResolver, SkipReason
from save_handlers import DatasetSaveHandler
from web_apis import ApiHelper


def create_logger():
	# configure logger
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.DEBUG)
	console_handler.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s]:: %(message)s'))
	logger = logging.getLogger("Mod")
	logger.setLevel(logging.DEBUG)
	logger.addHandler(console_handler)
	return logger


def main():
	logger = create_logger()

	cf_api_key = "CF_CORE_API_KEY"
	mod_id = 492939  # Project Id (you can find it on the cf mod page) or use the CFCoreAPI to search for the mod by name
	timestamp = int(time.time())

	api_helper = ApiHelper(cf_api_key)
	with DependencyResolver(api_helper, logger.getChild("DependencyResolver")) as dependency_resolver:
		# SaveHandler implementation of your choice
		with DatasetSaveHandler("sqlite:///mod_stats.db", timestamp) as save_handler:
			save_handler.db.begin()
			if mod_data_collector.collect_data(logger.getChild("DataCollector"), save_handler, dependency_resolver, api_helper, mod_id):
				logger.info("committing changes to db...")
				save_handler.db.commit()
			else:
				logger.info("rollback db changes...")
				save_handler.db.rollback()


def resolve_skipped_dependencies():
	logger = create_logger()
	api_helper = ApiHelper("CF_CORE_API_KEY")
	with DependencyResolver(api_helper, logger.getChild("DependencyResolver")) as dependency_resolver:
		dependency_resolver.resolve_skipped_file_dependencies(SkipReason.DOWNLOAD_TOO_LARGE)


def dumb_db_info(db_url: str):
	db = dataset.connect(db_url)
	print("dumping database info...")
	print("---")
	tables = db.tables
	for table_id in tables:
		table: Table = db[table_id]
		print("Table:", table_id, "\n  Columns:", table.columns, "\n  Rows:", len(table))
	print("---")
	db.close()


if __name__ == '__main__':
	main()
	# resolve_skipped_dependencies()
	# dumb_db_info("sqlite:///dependencies.db")
	# dumb_db_info("sqlite:///mod_stats.db")
	#
	# db = dataset.connect("sqlite:///dependencies.db")
	# for row in db['skipped_file']:
	# 	print("reason:", SkipReason(row['reason']).name, "url:", row['url'])
	# db.close()
