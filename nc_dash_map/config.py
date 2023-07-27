import os
import glob


# Paths.
GEOTIFF_DIR = "data"
DATA_DIR = "data"
DRIVER_PATH = "data/db.sqlite"

# Server config.
TC_PORT = 5000
TC_HOST = "localhost"
TC_URL = f"http://{TC_HOST}:{TC_PORT}"

# Data stuff.
PARAMS = [os.path.basename(xx)[:-4] for xx in
          sorted(glob.glob(os.path.join(GEOTIFF_DIR, "*.tif")))]
