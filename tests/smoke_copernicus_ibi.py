"""Exercise the installed split-dataset loader without credentials or network."""

from unittest.mock import patch

import numpy as np
import xarray as xr
from pangeo_fish.helpers import compute_diff, load_model


def main():
    temperature_id = "cmems_mod_ibi_phy-temp_my_0.027deg_P1D-m"
    ssh_id = "cmems_mod_ibi_phy-ssh_my_0.027deg_P1D-m"
    static_id = "cmems_mod_ibi_phy_my_0.027deg-3D_static"
    source = xr.Dataset(
        {
            "thetao": (
                ("time", "depth", "latitude", "longitude"),
                np.full((3, 2, 2, 2), 14.0),
                {"units": "degree_Celsius"},
            ),
            "zos": (("time", "latitude", "longitude"), np.zeros((3, 2, 2))),
            "deptho": (("latitude", "longitude"), np.full((2, 2), 100.0)),
            "mask": (("depth", "latitude", "longitude"), np.ones((2, 2, 2))),
        },
        coords={
            "time": np.array(
                ["2021-06-01", "2021-06-02", "2021-06-03"], dtype="datetime64[ns]"
            ),
            "depth": [0.5, 10.0],
            "latitude": [48.0, 48.1],
            "longitude": [-5.0, -4.9],
        },
    )
    datasets = {
        temperature_id: source[["thetao"]],
        ssh_id: source[["zos"]],
        static_id: source[["deptho", "mask"]],
    }
    tag = xr.Dataset(
        {"temperature": ("time", [13.0] * 3), "pressure": ("time", [5.0] * 3)},
        coords={"time": source.time},
    )
    with patch(
        "pangeo_fish.helpers.copernicusmarine.open_dataset",
        side_effect=lambda **kw: datasets[kw["dataset_id"]],
    ) as client:
        model = load_model(
            uri=None,
            tag_log=tag,
            time_slice=slice("2021-06-01", "2021-06-03"),
            bbox={"latitude": [48.0, 48.1], "longitude": [-5.0, -4.9], "max_depth": 20},
            chunk_time=1,
            remote_options={},
            copernicus_model_name=temperature_id,
        )
    assert [c.kwargs["variables"] for c in client.call_args_list] == [
        ["thetao"],
        ["zos"],
        ["deptho", "mask"],
    ]
    assert client.call_args_list[-1].kwargs["dataset_part"] == "bathy"
    assert model["mask"].dims == ("depth", "lat", "lon")
    diff, _ = compute_diff(
        reference_model=model, tag_log=tag, relative_depth_threshold=0, chunk_time=1
    )
    assert diff["diff"].notnull().all().compute().item()
    print("PASS: installed IBI load_model + compute_diff (mocked Copernicus calls)")


if __name__ == "__main__":
    main()
