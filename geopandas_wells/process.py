import os
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, box
import numpy
import math
import warnings
import datetime
from shapely.errors import ShapelyDeprecationWarning
from pandas.core.common import SettingWithCopyWarning
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)
warnings.simplefilter(action="ignore", category=SettingWithCopyWarning)


# funciton used during procedure
def get_bearing(lat1, long1, lat2, long2):
    dLon = (long2 - long1)
    x = math.cos(math.radians(lat2)) * math.sin(math.radians(dLon))
    y = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) -
         math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.cos(math.radians(dLon)))
    brng = numpy.arctan2(x, y)
    brng = numpy.degrees(brng)
    brng = brng if brng > 0 else 360+brng
    return round(brng, 1)


def which_part(bear, lgeom, bgeom):
    if bear == 0:
        if bgeom.bounds[0] < lgeom.bounds[0]:
            return 'L'
        return 'R'
    if bear == 180:
        if bgeom.bounds[0] < lgeom.bounds[0]:
            return 'R'
        return 'L'
    if bear < 180:
        if bgeom.bounds[1] > lgeom.bounds[1]:
            return 'L'
        return 'R'
    else:
        if bgeom.bounds[1] > lgeom.bounds[1]:
            return 'R'
        return 'L'


def find_closest(buff, cntr):
    sel = gdf.sindex.query(box(*buff.bounds))
    sel = gdf.loc[sel, :]
    sel = sel[sel.centro.intersects(buff)]
    if sel.shape[0] == 0:
        return 2650, ''

    sel.loc[:, 'dist'] = sel.apply(
        lambda xx: math.sqrt(
            (cntr.x-xx.centro.x)**2+(cntr.y-xx.centro.y)**2
        ),
        1)
    sel = sel.sort_values(by='dist', ascending=True)
    return sel.dist.values[0], sel.api_number.values[0]


if __name__ == '__main__':
    df = pd.read_excel(
        'l48-well_evaluator_attributes_use.xlsx',
        converters={'api_number': str}
    )

    geom = [LineString(
        (Point((xx.tophole_longitude__deg, xx.tophole_latitude__deg)),
         Point(xx.bottomhole_longitude__deg, xx.bottomhole_latitude__deg))
    ) for _, xx in df.iterrows()]
    gdf = gpd.GeoDataFrame(df, geometry=geom, crs="EPSG:4326")
    gdf = gdf.to_crs(3672)

    # find middle point of line
    gdf['centro'] = gdf.centroid

    # calculate bearing
    gdf['bearing'] = gdf.apply(lambda rr: get_bearing(
        rr.tophole_latitude__deg,
        rr.tophole_longitude__deg,
        rr.bottomhole_latitude__deg,
        rr.bottomhole_longitude__deg
    ), 1)

    # define needed fields
    gdf.loc[:, 'buff_all'] = gdf.geometry.buffer(
        2640, 1, cap_style=2).difference(gdf.geometry.buffer(0.01, 3))
    gdf.loc[:, 'buff_L'] = Polygon()
    gdf.loc[:, 'buff_R'] = Polygon()
    gdf.loc[:, 'LEFT_DIST'] = 2650
    gdf.loc[:, 'RIGHT_DIST'] = 2650
    gdf.loc[:, 'LEFT_API'] = ''
    gdf.loc[:, 'RIGHT_API'] = ''

    jj = 0
    for ii, row in gdf.iterrows():
        if jj % 1000 == 0:
            print(datetime.datetime.now(), jj)
        jj += 1

        buffl = Polygon()
        buffr = Polygon()
        for geom in row.buff_all.geoms:
            if which_part(row.bearing, row.geometry, geom) == 'L':
                gdf.loc[ii, 'buff_L'] = geom
                buffl = geom
            else:
                gdf.loc[ii, 'buff_R'] = geom
                buffr = geom

        dst, api = find_closest(buffl, row.centro)
        gdf.loc[ii, 'LEFT_DIST'] = dst
        gdf.loc[ii, 'LEFT_API'] = api
        dst, api = find_closest(buffr, row.centro)
        gdf.loc[ii, 'RIGHT_DIST'] = dst
        gdf.loc[ii, 'RIGHT_API'] = api

    # save calculations
    if not os.path.isdir('out'):
        os.mkdir('out')
    flds = ['LEFT_DIST', 'LEFT_API', 'RIGHT_DIST', 'RIGHT_API']
    gdf.to_crs(3672)

    aa = gdf[['api_number', 'bearing', 'buff_L']+flds]
    aa = aa.set_geometry('buff_L')
    aa.set_crs(3672)
    aa.to_file('out/buff_l.gpkg', driver='GPKG')

    aa = gdf[['api_number', 'bearing', 'buff_R']+flds]
    aa = aa.set_geometry('buff_R')
    aa.set_crs(3672)
    aa.to_file('out/buff_r.gpkg', driver='GPKG')

    aa = gdf[['api_number', 'centro']+flds]
    aa = aa.set_geometry('centro')
    aa.set_crs(3672)
    aa.to_file('out/centro.gpkg', driver='GPKG')

    aa = gdf[['api_number', 'geometry', 'bearing']+flds]
    aa = aa.set_geometry('geometry')
    aa.set_crs(3672)
    aa.to_file('out/lines.gpkg', driver='GPKG')

    aa = gdf[['api_number', 'bearing'] + flds].to_csv('out/output.csv',
                                                      index=False)
