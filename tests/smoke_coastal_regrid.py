"""Verify that the built image applies the fork's coastal HEALPix fallback."""

import subprocess
import sys

import numpy as np
import xarray as xr
import xdggs
from pangeo_fish.helpers import (
    BilinearResampler,
    CloughTocherResampler,
    regrid_dataset_hpresample,
)


def check_coastal_regrid():
    lon, lat = np.meshgrid(np.arange(-8.0, -3.0, 0.1), np.arange(47.0, 51.0, 0.1))
    ocean = lon < -5.5
    ds = xr.Dataset(
        {
            "thetao": (("time", "yi", "xi"), np.where(ocean, 17.0, np.nan)[None]),
            "ocean_mask": (("yi", "xi"), ocean),
        },
        coords={
            "time": [0],
            "longitude": (("yi", "xi"), lon),
            "latitude": (("yi", "xi"), lat),
        },
    )
    ct = CloughTocherResampler(
        lon_deg=lon[ocean], lat_deg=lat[ocean], level=8, ellipsoid="sphere"
    )
    bilinear = BilinearResampler(
        lon_deg=lon[ocean],
        lat_deg=lat[ocean],
        level=8,
        ellipsoid="sphere",
        threshold=0.5,
        ring_search_max=4,
    )
    result, info = regrid_dataset_hpresample(ds=ds, refinement_level=8)
    assert np.isin(result.ocean_mask, [0, 1]).all(), "Target ocean mask was overwritten"
    sea = result.ocean_mask.values.astype(bool)
    fallback = (
        sea
        & ~np.isin(result.cell_ids, ct.get_cell_ids())
        & np.isin(result.cell_ids, bilinear.get_cell_ids())
    )
    assert fallback.any(), "Synthetic coast did not exercise the fallback"
    np.testing.assert_allclose(result.thetao.values[:, fallback], 17.0)
    assert np.isnan(result.thetao.values[:, ~sea]).all(), "Values leaked onto land"
    result = result.swap_dims({"cells": "cell_ids"})
    result.cell_ids.attrs["ellipsoid"] = info["ellipsoid"]
    result = xdggs.decode(result)
    assert result.thetao.dims == ("time", "cell_ids")
    print(
        f"PASS: {fallback.sum()} coastal cells recovered; grid: {result.dggs.grid_info}"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        commit = subprocess.check_output(
            ["git", "-C", "/srv/pangeo-fish", "rev-parse", "HEAD"], text=True
        ).strip()
        assert commit == sys.argv[1], f"Unexpected source commit: {commit}"
        print(f"Pangeo-Fish source commit: {commit}")
    check_coastal_regrid()
