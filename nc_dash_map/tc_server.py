import os
import terracotta as tc
from terracotta_toolbelt.extensions import point

from terracotta import update_settings
from terracotta.server import create_app
from config import DRIVER_PATH, GEOTIFF_DIR, TC_PORT, TC_HOST


def init_db(keys, key_descriptions=None, nuke=False):
    driver = tc.get_driver(DRIVER_PATH)
    # Create an empty database if it doesn't exist
    os.makedirs(os.path.dirname(DRIVER_PATH), exist_ok=True)
    if nuke and os.path.isfile(DRIVER_PATH):
        os.remove(DRIVER_PATH)
    if not os.path.isfile(DRIVER_PATH):
        driver.create(keys=keys, key_descriptions=key_descriptions)
    # Insert the parameters.
    with driver.connect():
        for entry in [entry for entry in sorted(os.listdir(GEOTIFF_DIR))
                      if entry[-4:] == ".tif"]:
            tiff_path = os.path.join(GEOTIFF_DIR, entry)
            tiff_dict = {'dset': 'era5', 'param': entry[:-4]}
            driver.insert(tiff_dict, tiff_path)
            print(tiff_dict, tiff_path)


init_db(keys=["dset", "param"], nuke=True)
# Create terracotta server.
update_settings(DRIVER_PATH=DRIVER_PATH, REPROJECTION_METHOD="nearest")
server = create_app()
# Bind custom stuff.
point.register(server)

if __name__ == '__main__':
    server.run(port=TC_PORT, host=TC_HOST, threaded=False)
