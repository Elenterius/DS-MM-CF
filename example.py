import mod_data_collector


def main():
	db_path = "sqlite:///db/mod_stats.db"
	cf_api_key = "YOUR_CURSE_FORGE_CORE_API_KEY"
	mod_id = 420_420  # Project Id (you can find it on the cf mod page) or use the CFCoreAPI to search for the mod by name

	# NOTE:
	# ATM the resulting database is created with the dataset library (https://dataset.readthedocs.io/en/latest/) which does not create a proper relational DB.
	# It's a derpy db that is more akin to a nosql-db and has no proper primary/foreign key relationships, constraints, etc. setup.
	mod_data_collector.collect_data(mod_id, db_path, cf_api_key, force=True)


if __name__ == '__main__':
	main()
