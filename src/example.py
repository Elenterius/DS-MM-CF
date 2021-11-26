import logging
import time

import mod_data_collector
from dependency_resolver import DependencyResolver
from save_handlers import DatasetSaveHandler
from web_apis import ApiHelper


def main():
	# configure logger
	console_handler = logging.StreamHandler()
	console_handler.setLevel(logging.DEBUG)
	console_handler.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s]:: %(message)s'))
	logger = logging.getLogger("Mod")
	logger.setLevel(logging.DEBUG)
	logger.addHandler(console_handler)

	cf_api_key = "YOUR_API_KEY"
	mod_id = 492939  # Project Id (you can find it on the cf mod page) or use the CFCoreAPI to search for the mod by name
	timestamp = int(time.time())

	api_helper = ApiHelper(cf_api_key)
	dependency_resolver = DependencyResolver(api_helper, logger.getChild("DependencyResolver"))

	# save handler implementation of your choice
	save_handler = DatasetSaveHandler("sqlite:///mod_stats.db", timestamp)

	mod_data_collector.collect_data(logger.getChild("DataCollector"), save_handler, dependency_resolver, api_helper, mod_id)


if __name__ == '__main__':
	main()
