import csv

import dagster as dg
from sqlalchemy import select

from datawhisk_shared.orm import Occupancy
from orchestration.resources import DataWhiskSessionResource

SPACE_ID = 473
OUTPUT_FILE = "by_room_data/output_3141_clwb_1300_1.csv"


@dg.asset(
    description="Exports occupancy data for a specific space ID to CSV.",
    group_name="occupancy",
)
def occupancy_data_for_spaceid(db: DataWhiskSessionResource) -> dg.MaterializeResult:
    with db.session() as session:
        rows = session.scalars(
            select(Occupancy).where(Occupancy.spaceid == SPACE_ID)
        ).all()

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["spaceid", "starttime", "endtime", "occupancy"])
        for row in rows:
            writer.writerow([row.spaceid, row.starttime, row.endtime, row.occupancy])

    return dg.MaterializeResult(metadata={"row_count": len(rows), "space_id": SPACE_ID})


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()
    dg.materialize(
        [occupancy_data_for_spaceid],
        resources={"db": DataWhiskSessionResource(database_url=os.environ["DATABASE_URL"])},
    )
