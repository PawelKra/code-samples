import geopandas as gpd
import pandas as pd
from shapely.wkt import loads
import pyodbc
from loguru import logger

# this is used to suppress Warnings from pandas, log looks clearer
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)


class ProcessPLSS:
    USER = 'urs'
    PASSWORD = 'pass'
    DB = 'PLSSPilotPawel'
    HOST = 'dsatabase.windows.net'

    LOT_TABLE = 'QQLOTPILOT'
    TESTRECORDS = 'TestRecords'
    PART_COL = 'PART'
    CORRECTSECDIVID = 'CorrectSecDivID'

    # codes in columns from W to E
    CODES = pd.Series(
        ['NWNW', 'SWNW', 'NWSW', 'SWSW',
         'NENW', 'SENW', 'NESW', 'SESW',
         'NWNE', 'SWNE', 'NWSE', 'SWSE',
         'NENE', 'SENE', 'NESE', 'SESE',
         ]
    )

    # arrange lots in columns
    ACOLUMNS = pd.Series([0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, ])

    def __init__(self):
        self.con = False
        self.cur = False
        self.test_records = []
        self.testrecords_done = []

    def setup_connection(self):
        """Connect to DB"""
        drv = ''
        # I've got one of these on my laptops. Best is to check this on Your
        # machine by opening python console and type:
        # >>>import pydobc
        # >>>pyodbc.drivers()
        # here You will got all drivers that pyodbc has access to, on list
        # should be one of these or with diferent version number, in that case
        # You should add anoter elif option
        if 'ODBC Driver 18 for SQL Server' in pyodbc.drivers():
            drv = 'ODBC Driver 18 for SQL Server'
        elif 'SQL Server Native Client 10.0' in pyodbc.drivers():
            drv = 'SQL Server Native Client 10.0'
        else:
            logger.error(
                'No driver for SqlServer found! Check if pyodbc has dirver'
                ' to connect to SqlServer. END'
            )
            return False
        self.con = pyodbc.connect(
            'DRIVER={};SERVER={};DATABASE={};UID={};PWD={}'.format(
                drv,
                self.HOST,
                self.DB,
                self.USER,
                self.PASSWORD
            )
        )
        self.cur = self.con.cursor()
        return True

    def update_db(self, row):
        """Updates db table, by row
            row - geodataframe
        """
        if row.SECDIVID_x in self.testrecords_done:
            # logger.warning(f'Duplicated testrecord: {row.SECDIVID_x}')
            return

        # prepare lab value
        lab = str(row.SECDIVNO).strip()
        if len(lab) > 0:
            lab = 'L' + lab

        sql = 'update {} set {}=\'{}\' where SECDIVID=\'{}\';'.format(
            self.TESTRECORDS,
            self.CORRECTSECDIVID,
            lab,
            row.SECDIVID_x,
        )
        self.cur.execute(sql)
        self.con.commit()
        # add this test record to not repeat this procedure
        # I do not remove duplicates - by that way You will not be able to seen
        # them in log.
        self.testrecords_done.append(row.SECDIVID_x)

    def get_test_records_db(self):
        """Downloads TestRecords from db"""
        sql = f'select {self.PART_COL}, SECDIVID from TestRecords;'
        try:
            self.test_records = pd.read_sql(sql, self.con)
            self.test_records['section'] = self.test_records.apply(
                lambda x: x['SECDIVID'][:20], axis=1
            )
            logger.info(f'Fetched {self.test_records.shape[0]} test records')
            return True

        except Exception:
            logger.error('Cannot fetch TestRecords from db! END')
            return False

    def fetch_lots(self, key):
        """Download lots from section:
           key - string(20)
        """
        sql = f'select shape.ToString() as geom_wkt, SECDIVID, FRSTDIVID, SECDIVTXT, SECDIVLAB, SECDIVNO from QQLOTSPILOT where FRSTDIVID=\'{key}\';'
        gdf = pd.read_sql(sql, self.con)
        geometry = [loads(x) for x in gdf.geom_wkt]
        gdflots = gpd.GeoDataFrame(gdf,
                                   geometry=geometry,
                                   crs={'init': 'epsg:' + str(4326)})
        return gdflots

    def setup_section(self, lots):
        """Arranges 16 lots in array 4x4
        lots - Geodataframe with 16 rows
        """
        # I use bounds intead centroid, this is faster
        lots.loc[:, 'left'] = lots.bounds.minx
        lots.loc[:, 'top'] = lots.bounds.maxy
        # sorting all to be in proper places
        vert = lots.sort_values(by='left')
        vert = vert.reset_index()  # reset index to concat with with series
        vert.loc[:, 'org_index'] = vert['index']  # store index in separate col
        # add columns no
        vert.loc[:, 'cols'] = self.ACOLUMNS
        vert.sort_values(by=['cols', 'top'],
                         ascending=[True, False],
                         inplace=True)
        vert = vert.reset_index()
        # add codes of qq to lots
        vert.loc[:, self.PART_COL] = self.CODES
        return vert

    def clean_lots(self, lots):
        """If there is more than 16 lots and some of them are geometry
        duplicates, this method remove them from batch
        lots: gdf
        return: gdf
        """
        def check(row, dup):
            if row.geometry not in dup:
                return True
            if row.geometry in dup:
                if row.SECDIVNO.isdigit():
                    return True
            return False

        dupl = lots.bounds.duplicated(['minx', 'miny'])
        dup = list(lots.loc[dupl, 'geometry'])
        lots['ok'] = lots.apply(lambda row: check(row, dup), axis=1)
        return lots[lots['ok'] == True]

    def process(self):
        """ Main procedure for updating test records in db"""
        if not self.setup_connection():
            return
        if not self.get_test_records_db():
            return

        # arrange testrecords in groups
        groups = self.test_records.groupby('section')
        logger.info(f'Test records grouped in {len(groups)} sections')
        for sec_name, section in groups:
            lots = self.fetch_lots(sec_name)

            if lots.shape[0] < 16:
                logger.warning(
                    f'In section {sec_name} found {lots.shape[0]} ' +
                    'lots - Omitting!'
                )
                continue

            if lots.shape[0] > 16:
                clots = self.clean_lots(lots)
                if clots.shape[0] != 16:
                    logger.warning(
                        f'In section {sec_name} found {lots.shape[0]} ' +
                        'cleaning failed - Omitting!'
                    )
                    continue
                else:
                    logger.info('  └--> Section cleaned! Processing!')

                lots = clots

            logger.info(
                f'Processing section: {sec_name} [{section.shape[0]} rows]'
            )
            qqlots = self.setup_section(lots)  # assign QQ for lots
            # left merge with testrecords
            merged = pd.merge(section, qqlots, how='inner', on=self.PART_COL)
            # for every row in gdf modyfi database
            merged.apply(
                lambda row: self.update_db(row), axis=1
            )

        # close connection to db
        self.con.close()


if __name__ == '__main__':
    pp = ProcessPLSS()
    pp.process()
