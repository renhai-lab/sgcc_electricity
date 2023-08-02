import logging
import os
import re
import subprocess
import time
import traceback

import ddddocr
import dotenv
import pymongo
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from const import *


def _get_chromium_version():
    result = str(subprocess.check_output(["chromium", "--product-version"]))
    return re.findall(r"(\d*)\.", result)[0]

print(_get_chromium_version())

time.sleep(1000000000)