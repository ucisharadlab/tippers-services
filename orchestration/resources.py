from dagster import ConfigurableResource

from datawhisk_shared import DataWhiskDB


class DataWhiskDBResource(ConfigurableResource):
    database_url: str

    def get_client(self) -> DataWhiskDB:
        return DataWhiskDB(self.database_url)
