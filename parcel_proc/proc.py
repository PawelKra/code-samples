import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, LineString, MultiPolygon, box


# ------[ INPUT ]-------

# on windows You need to specify paths like that:
# 'C:\\Users\\output\\out.shp'

# input files locations
pa = 'DATA/PARCELLE.shp'
ba = 'DATA/BATIMENT.shp'
qa = 'DATA/QUARTIER.shp'
ru = 'DATA/ROUTE.shp'
ad = 'DATA/ID_ADRESSE.csv'

# output files locations
route_out_pth = 'out/outr.shp'
pa_out = 'out/outp.shp'
ba_out = 'out/outb.shp'
centro_out = 'out/outb_centr.shp'

min_area = 1.0  # keep polygons with area greater than 1 sq m
# ------[ INPUT ]-------


def inter(row, lyr):
    geom = row.geometry
    empty = LineString() if geom.geom_type == LineString else Polygon()
    pi = lyr.sindex.query(box(*geom.bounds))
    lyri = lyr.loc[pi, :].copy()
    lyri = lyri[lyri.intersects(geom)]
    lyri.loc[:, 'geometry'] = lyri.apply(
        lambda ri: ri.geometry.intersection(geom)
        if ri.geometry.intersects(geom) else empty,
        axis=1)
    lyri.set_geometry(col='geometry', inplace=True)
    if empty.geom_type in [MultiPolygon, Polygon]:
        lyri = lyri[lyri.geometry.area > min_area]
    return lyri


def find_biggest_inter(geom, lyr, col):
    """Find biggest intersection area with geometry and then input value
    from specified column
    Lyr and geom must be Polygon/MultiPolygon geometries
    """
    pi = lyr.sindex.query(box(*geom.bounds))
    lyri = lyr.loc[pi, :].copy()
    lyri = lyri[lyri.intersects(geom)]
    if lyri.shape[0] == 0:
        return "No features intersects"
    elif lyri.shape[0] == 1:
        return lyri[col].values[0]

    lyri['intarea'] = lyri.apply(
        lambda row: row.geometry.intersection(geom).area, axis=1
    )
    return lyri.sort_values(by='intarea', ascending=False)[col].values[0]


if __name__ == '__main__':
    parc = gpd.read_file(pa)
    bat = gpd.read_file(ba)
    qua = gpd.read_file(qa, encoding='UTF-8')
    rou = gpd.read_file(ru)

    address = pd.read_csv(ad, sep=';', converters={'ID_ADRESSE': int})

    # ROUTE file  --------------
    route_out = gpd.GeoDataFrame()
    # check if there is needed column in quartier
    qcol = [xx for xx in qua.columns if xx.upper() == 'QUARTIER']
    if len(qcol) > 0:
        qcol = qcol[0]
    else:
        # if not add xxx for easy spot error
        qua['QUARTIER'] = 'xxx'
        qcol = 'QUARTIER'

    for no, row in qua.iterrows():
        rtemp = inter(row, rou)
        rtemp['QUARTIER'] = row[qcol]
        route_out = pd.concat([rtemp, route_out], ignore_index=True)
    route_out = route_out.merge(address, on='ID', how='left')
    route_out.dropna(subset=['ID_ADRESSE'], inplace=True)
    route_out = route_out[['ID_ADRESSE', 'geometry', 'QUARTIER']]
    route_out = gpd.GeoDataFrame(route_out)
    route_out.set_crs(rou.crs, inplace=True)
    route_out = route_out.dissolve(['ID_ADRESSE', 'QUARTIER'])
    route_out.reset_index(inplace=True)
    route_out['ID_ADRESSE'] = route_out.ID_ADRESSE.astype(int)
    route_out.to_file(route_out_pth, driver='ESRI Shapefile')
    # ------------------

    parc['ID_PARCEL'] = parc.apply(
        lambda row: ''.join(
            [row.CODE_COM, row.SECTION, row.NUMERO.strip().replace(' ', '')]
        ), axis=1)

    outp = gpd.GeoDataFrame()
    outb = gpd.GeoDataFrame()

    for no, row in qua.iterrows():
        parc_calc = inter(row, parc)
        parc_calc['QUARTIER'] = row.Quartier
        outp = pd.concat([outp, parc_calc], ignore_index=True)

        bat_calc = inter(row, bat)
        bat_calc['QUARTIER'] = row.Quartier
        outb = pd.concat([outb, bat_calc], ignore_index=True)

    outp.set_crs(parc.crs, inplace=True)
    outp = outp[['NOM_COM', 'ID_PARCEL', 'QUARTIER', 'geometry']]
    outp = gpd.GeoDataFrame(outp)
    outp.set_crs(parc.crs, inplace=True)
    outp.to_file(pa_out, driver='ESRI Shapefile')

    outb.set_crs(bat.crs, inplace=True)
    outb = outb.merge(address, on='ID', how='left')
    outb.dropna(subset=['ID_ADRESSE'], inplace=True)
    outb = outb[['ID_ADRESSE', 'QUARTIER', 'geometry']]
    outb['IT_PARCEL'] = outb.apply(
        lambda row: find_biggest_inter(row.geometry, outp, 'ID_PARCEL'),
        axis=1)
    outb = gpd.GeoDataFrame(outb)
    outb.set_crs(bat.crs, inplace=True)
    outb['ID_ADRESSE'] = outb.ID_ADRESSE.astype(int)
    outb_diss = outb.dissolve(['ID_ADRESSE', 'IT_PARCEL'])
    outb_diss.reset_index(inplace=True)
    outb_diss.to_file(ba_out, driver='ESRI Shapefile')

    # CENTROIDS
    # this is not centroid but representative point which means it will always
    # lies inside Polygon/MultiPolygon not like centroid
    outb_diss['centro'] = outb_diss.geometry.representative_point()
    centro = outb_diss.copy()
    centro['geometry'] = centro['centro']
    del centro['centro']
    centro = centro.to_crs(4326)  # WGS84
    centro['LAT'] = centro.geometry.y
    centro['LON'] = centro.geometry.x
    # centro = centro.to_crs(outb_diss.crs)  # change crs back to original
    centro.to_file(centro_out, driver='ESRI Shapefile')

    print('END')
