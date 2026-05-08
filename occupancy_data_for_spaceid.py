import csv
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from datawhisk_shared.orm import Occupancy, Sensor

"""This file is to allow a user to create a CSV file containing all the data
for a given space_id. The CSV files are what are used to train the models. 
Additionally, the data ALREADY has to be in the occupancy table first."""

_OUTPUT_DIR = "by_room_data"


def _export(space_id: int, session: Session) -> tuple[int, str]:
    wifi_zone = session.scalar(
        select(Sensor.sensor_name)
        .where(Sensor.space_id == space_id)
        .order_by(Sensor.sensor_id)
        .limit(1)
    )
    if wifi_zone is None:
        raise ValueError(f"No sensor found for space_id {space_id}")

    rows = session.scalars(
        select(Occupancy).where(Occupancy.spaceid == space_id)
    ).all()
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    output_file = f"{_OUTPUT_DIR}/output_{wifi_zone}_1.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["spaceid", "starttime", "endtime", "occupancy"])
        for row in rows:
            writer.writerow([row.spaceid, row.starttime, row.endtime, row.occupancy])
    return len(rows), output_file


# Dagster asset — only defined when dagster and orchestration are available.
try:
    import dagster as dg
    from orchestration.resources import DataWhiskSessionResource

    @dg.asset(
        description="Exports occupancy data for a specific space ID to CSV.",
        group_name="occupancy",
    )
    def occupancy_data_for_spaceid(db: DataWhiskSessionResource) -> dg.MaterializeResult:
        space_id = int(os.environ.get("SPACE_ID", 473))
        with db.session() as session:
            row_count, output_file = _export(space_id, session)
        return dg.MaterializeResult(metadata={"row_count": row_count, "space_id": space_id, "file": output_file})

except ImportError:
    pass


if __name__ == "__main__":
    from dotenv import load_dotenv
    from datawhisk_shared.session import make_sessionmaker

    load_dotenv()
    space_id = int(os.environ.get("SPACE_ID", 473))
    sm = make_sessionmaker(os.environ["DATABASE_URL"])
    with sm() as session:
        row_count, output_file = _export(space_id, session)
    print(f"{row_count}|{output_file}")
