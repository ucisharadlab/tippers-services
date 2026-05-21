from orchestration.assets.occupancy import occupancy_model
from orchestration.assets.thermal import thermal_em_model, thermal_etotal_model

all_assets = [occupancy_model, thermal_em_model, thermal_etotal_model]

__all__ = ["all_assets", "occupancy_model", "thermal_em_model", "thermal_etotal_model"]
