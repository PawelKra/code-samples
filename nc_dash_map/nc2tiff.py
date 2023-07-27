import os
import xarray as xr
import rioxarray
import numpy as np
from collections import Counter


PTH = 'reanalysis_era5_land_2m_temperature_IRAto1hourly_mean_2016-2021_.nc'
OUTDIR = f'{os.path.dirname(__file__)}/data/'


def setup_proper_xds(
    vals: np.array,
    lat: np.array,
    lon: np.array,
    pth: str
):
    x = xr.Dataset(
        {
            "temp": (("lat", "lon"), vals),
        },
        coords={
            'lon': lon,
            'lat': lat
        }
    )
    x = x.rio.set_spatial_dims(x_dim='lon', y_dim='lat')
    x = x.rename({'lon': 'x', 'lat': 'y'})
    x = x.rio.write_crs(4326)
    print(f'saving: {pth}')
    x.rio.to_raster(pth)


def reprocess_nc(pth: str):
    xds = xr.open_dataset(PTH)
    dts = dict(Counter([str(xx)[:7] for xx in xds.time.data]))

    xst = 0
    xen = 0
    for dt, cnt in dts.items():
        xst = xen
        xen = xen + cnt

        stab = np.sum(xds.t2m.data[xst:xen], axis=0) / cnt
        vals = np.array(stab) - 273
        vals[vals > 100] = np.nan

        setup_proper_xds(
            vals,
            np.unique(np.array(xds.lat).reshape(1, 11928)[0])[::-1],
            np.unique(np.array(xds.lon).reshape(1, 11928)[0]),
            os.path.join(pth, f'era5_{dt}_b1.tif')
        )


if __name__ == '__main__':
    reprocess_nc(OUTDIR)
