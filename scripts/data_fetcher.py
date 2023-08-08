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


class DataFetcher:

    def __init__(self, username: str, password: str):
        dotenv.load_dotenv()
        self._username = username
        self._password = password
        self._ocr = ddddocr.DdddOcr(show_ad=False)
        self._chromium_version = self._get_chromium_version()

        # 获取 ENABLE_DATABASE_STORAGE 的值，默认为 False
        enable_database_storage = os.getenv("ENABLE_DATABASE_STORAGE", "false").lower() == "true"

        if enable_database_storage:
            # 将数据存储到数据库
            logging.debug("enable_database_storage为true，将会储存到数据库")
            self.test_mongodb_connection()
            self.db = self.client[os.getenv("DB_NAME")] # 创建数据库
        else:
            # 将数据存储到其他介质，如文件或内存
            self.client = None
            self.db = None
            logging.info("enable_database_storage为false，不会储存到数据库")

        self.DRIVER_IMPLICITY_WAIT_TIME = int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME"))
        self.RETRY_TIMES_LIMIT = int(os.getenv("RETRY_TIMES_LIMIT"))
        self.LOGIN_EXPECTED_TIME = int(os.getenv("LOGIN_EXPECTED_TIME"))
        self.RETRY_WAIT_TIME_OFFSET_UNIT = int(os.getenv("RETRY_WAIT_TIME_OFFSET_UNIT"))

    def test_mongodb_connection(self):
        """测试数据库连接情况"""
        try:
            MONGO_URL = os.getenv("MONGO_URL")
            # 创建 MongoDB 客户端
            self.client = pymongo.MongoClient(MONGO_URL)

            # 检查连接是否可用
            self.client.admin.command('ping')

            logging.info("MongoDB connection test successful")
        except Exception as e:
            logging.error("Failed to connect to MongoDB: " + str(e))

    def connect_user_collection(self, user_id):
        """创建数据库集合，collection_name = electricity_daily_usage_{user_id}
        :param user_id: 用户ID"""
        # 创建集合
        collection_name = f"electricity_daily_usage_{user_id}"
        try:
            collection = self.db.create_collection(collection_name)
            logging.info(f"集合: {collection_name} 创建成功")
            self.create_col_index(collection)
        # 如果集合已存在，则不会创建
        except:
            collection = self.db[collection_name]
            logging.debug("集合: {collection_name} 集合已存在")
        finally:
            return collection

    def create_col_index(self, collection):
            # 创建索引
            try:
                collection.create_index([('date', pymongo.DESCENDING)], unique=True)
                logging.info(f"创建索引'date'成功")
            except:
                logging.debug("索引'date'已存在")

    def fetch(self):
        """the entry, only retry logic here """
        for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):
            try:
                return self._fetch()
            except Exception as e:
                if retry_times == self.RETRY_TIMES_LIMIT:
                    raise e
                traceback.print_exc()
                logging.error(
                    f"Webdriver quit abnormly, reason: {e}. {self.RETRY_TIMES_LIMIT - retry_times} retry times left.")
                wait_time = retry_times * self.RETRY_WAIT_TIME_OFFSET_UNIT
                time.sleep(wait_time)

    def _fetch(self):
        """main logic here"""

        driver = self._get_webdriver()
        logging.info("Webdriver initialized.")

        try:
            self._login(driver)
            logging.info(f"Login successfully on {LOGIN_URL}")

            user_id_list = self._get_user_ids(driver)
            logging.info(f"将获取{len(user_id_list)}户数据，user_id: {user_id_list}")


            balance_list = self._get_electric_balances(driver, user_id_list)  #
            ### get data except electricity charge balance
            last_daily_date_list, last_daily_usage_list, yearly_charge_list, yearly_usage_list = self._get_other_data(driver, user_id_list)

            driver.quit()

            logging.info("Webdriver quit after fetching data successfully.")
            logging.info("浏览器已退出")
            return user_id_list, balance_list, last_daily_date_list, last_daily_usage_list, yearly_charge_list, yearly_usage_list

        finally:
            driver.quit()

    def _get_webdriver(self):
        chrome_options = Options()
        chrome_options.add_argument('--incognito')
        chrome_options.add_argument('--window-size=4000,1600')
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-dev-shm-usage')
        driver = uc.Chrome(driver_executable_path="/usr/bin/chromedriver", options=chrome_options, version_main=self._chromium_version)
        driver.implicitly_wait(self.DRIVER_IMPLICITY_WAIT_TIME)
        return driver

    def _login(self, driver):

        driver.get(LOGIN_URL)

        # swtich to username-password login page
        driver.find_element(By.CLASS_NAME, "user").click()

        # input username and password
        input_elements = driver.find_elements(By.CLASS_NAME, "el-input__inner")
        input_elements[0].send_keys(self._username)
        input_elements[1].send_keys(self._password)

        captcha_element = driver.find_element(By.CLASS_NAME, "code-mask")

        # sometimes ddddOCR may fail, so add retry logic)
        for retry_times in range(1, self.RETRY_TIMES_LIMIT + 1):

            img_src = captcha_element.find_element(By.TAG_NAME, "img").get_attribute("src")
            img_base64 = img_src.replace("data:image/jpg;base64,", "")
            orc_result = str(self._ocr.classification(ddddocr.base64_to_image(img_base64)))

            if (not self._is_captcha_legal(orc_result)):
                logging.debug(
                    f"The captcha is illegal, which is caused by ddddocr, {self.RETRY_TIMES_LIMIT - retry_times} retry times left.")
                WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.element_to_be_clickable(captcha_element))
                driver.execute_script("arguments[0].click();", captcha_element)
                time.sleep(2)
                continue

            input_elements[2].send_keys(orc_result)

            # click login button
            self._click_button(driver, By.CLASS_NAME, "el-button.el-button--primary")
            try:
                return WebDriverWait(driver, self.LOGIN_EXPECTED_TIME).until(EC.url_changes(LOGIN_URL))
            except:
                logging.debug(
                    f"Login failed, maybe caused by invalid captcha, {self.RETRY_TIMES_LIMIT - retry_times} retry times left.")

        raise Exception(
            "Login failed, maybe caused by 1.incorrect phone_number and password, please double check. or 2. network, please mnodify LOGIN_EXPECTED_TIME in .env and run docker compose up --build.")

    def _get_electric_balances(self, driver, user_id_list):

        balance_list = []

        # switch to electricity charge balance page
        driver.get(BALANCE_URL)

        # get electricity charge balance for each user id
        for i in range(1, len(user_id_list) + 1):
            balance = self._get_eletric_balance(driver)
            if (balance is None):
                logging.info(f"Get electricity charge balance for {user_id_list[i - 1]} failed, Pass.")
            else:
                logging.info(
                    f"Get electricity charge balance for {user_id_list[i - 1]} successfully, balance is {balance} CNY.")
            balance_list.append(balance)

            # swtich to next userid
            if (i != len(user_id_list)):
                self._click_button(driver, By.CLASS_NAME, "el-input__inner")
                self._click_button(driver, By.XPATH,
                                   f"//ul[@class='el-scrollbar__view el-select-dropdown__list']/li[{i + 1}]")

        return balance_list

    def _get_other_data(self, driver, user_id_list):
        last_daily_date_list = []
        last_daily_usage_list = []
        yearly_usage_list = []
        yearly_charge_list = []

        # swithc to electricity usage page
        driver.get(ELECTRIC_USAGE_URL)

        # get data for each user id
        for i in range(1, len(user_id_list) + 1):

            yearly_usage, yearly_charge = self._get_yearly_data(driver)

            if yearly_usage is None:
                logging.error(f"Get year power usage for {user_id_list[i - 1]} failed, pass")
            else:
                logging.info(
                    f"Get year power usage for {user_id_list[i - 1]} successfully, usage is {yearly_usage} kwh")
            if yearly_charge is None:
                logging.error(f"Get year power charge for {user_id_list[i - 1]} failed, pass")
            else:
                logging.info(
                    f"Get year power charge for {user_id_list[i - 1]} successfully, yealrly charge is {yearly_charge} CNY")

            # get yesterday usage
            last_daily_datetime, last_daily_usage = self._get_yesterday_usage(driver)

            # 新增储存30天用电量
            if self.client is not None:
                self.save_30_days_usage(driver, user_id_list[i - 1])

            if last_daily_usage is None:
                logging.error(f"Get daily power consumption for {user_id_list[i - 1]} failed, pass")
            else:
                logging.info(
                    f"Get daily power consumption for {user_id_list[i - 1]} successfully, , {last_daily_datetime} usage is {last_daily_usage} kwh.")

            last_daily_date_list.append(last_daily_datetime)
            last_daily_usage_list.append(last_daily_usage)
            yearly_charge_list.append(yearly_charge)
            yearly_usage_list.append(yearly_usage)

            # switch to next user id
            if i != len(user_id_list):
                self._click_button(driver, By.CLASS_NAME, "el-input.el-input--suffix")
                self._click_button(driver, By.XPATH,
                                   f"//body/div[@class='el-select-dropdown el-popper']//ul[@class='el-scrollbar__view el-select-dropdown__list']/li[{i + 1}]")

        return last_daily_date_list, last_daily_usage_list, yearly_charge_list, yearly_usage_list

    def _get_user_ids(self, driver):

        # click roll down button for user id
        self._click_button(driver, By.XPATH, "//div[@class='el-dropdown']/span")
        # wait for roll down menu displayed
        target = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_element(By.TAG_NAME, "li")
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(
            EC.text_to_be_present_in_element((By.XPATH, "//ul[@class='el-dropdown-menu el-popper']/li"), ":"))

        # get user id one by one
        userid_elements = driver.find_element(By.CLASS_NAME, "el-dropdown-menu.el-popper").find_elements(By.TAG_NAME,
                                                                                                         "li")
        userid_list = []
        for element in userid_elements:
            userid_list.append(re.findall("[0-9]+", element.text)[-1])
        return userid_list

    def _get_eletric_balance(self, driver):
        try:
            balance = driver.find_element(By.CLASS_NAME, "num").text
            return float(balance)
        except:
            return None

    def _get_yearly_data(self, driver):

        try:
            self._click_button(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-first']")

            # wait for data displayed
            target = driver.find_element(By.CLASS_NAME, "total")
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(target))
        except:
            return None, None

        # get data
        try:
            yearly_usage = driver.find_element(By.XPATH, "//ul[@class='total']/li[1]/span").text

        except:
            yearly_usage = None

        try:
            yearly_charge = driver.find_element(By.XPATH, "//ul[@class='total']/li[2]/span").text
        except:
            yearly_charge = None

        return yearly_usage, yearly_charge

    def _get_yesterday_usage(self, driver):
        """获取最近一次用电量"""
        try:
            # 点击日用电量
            self._click_button(driver, By.XPATH, "//div[@class='el-tabs__nav is-top']/div[@id='tab-second']")
            # wait for data displayed
            usage_element = driver.find_element(By.XPATH,
                                                "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div")
            WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(usage_element)) # 等待用电量出现

            # 增加是哪一天
            date_element = driver.find_element(By.XPATH,
                                               "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[1]/div")
            last_daily_date = date_element.text # 获取最近一次用电量的日期
            return last_daily_date, float(usage_element.text)
        except:
            return None

    # 增加储存30天用电量的到mongodb的函数
    def save_30_days_usage(self, driver, user_id):
        """储存30天用电量"""
        self._click_button(driver, By.XPATH, "//*[@id='pane-second']/div[1]/label[2]/span[2]")
        # 等待30天用电量的数据出现
        usage_element = driver.find_element(By.XPATH,
                                            "//div[@class='el-tab-pane dayd']//div[@class='el-table__body-wrapper is-scrolling-none']/table/tbody/tr[1]/td[2]/div")
        WebDriverWait(driver, self.DRIVER_IMPLICITY_WAIT_TIME).until(EC.visibility_of(usage_element))
        # 30天用电量的数据
        days_element = driver.find_elements(By.XPATH,
                                            "//*[@id='pane-second']/div[2]/div[2]/div[1]/div[3]/table/tbody/tr")  # 30天的值 列表 2023-05-0511.98


        # 连接数据库集合
        collection = self.connect_user_collection(user_id)

        # 将30天的用电量保存为字典
        for i in days_element:
            day = i.find_element(By.XPATH, "td[1]/div").text
            usage = i.find_element(By.XPATH, "td[2]/div").text
            dic = {'date': day, 'usage': float(usage)}
            # 插入到数据库
            try:
                collection.insert_one(dic)
                logging.info(f"{day}的用电量{usage}KWh已经成功存入数据库")
            except:
                logging.debug(f"{day}的用电量存入数据库失败,可能已经存在")


    @staticmethod
    def _click_button(driver, button_search_type, button_search_key):
        '''wrapped click function, click only when the element is clickable'''
        click_element = driver.find_element(button_search_type, button_search_key)
        WebDriverWait(driver, int(os.getenv("DRIVER_IMPLICITY_WAIT_TIME"))).until(EC.element_to_be_clickable(click_element))
        driver.execute_script("arguments[0].click();", click_element)

    @staticmethod
    def _is_captcha_legal(captcha):
        ''' check the ddddocr result, justify whether it's legal'''
        if (len(captcha) != 4):
            return False
        for s in captcha:
            if (not s.isalpha() and not s.isdigit()):
                return False
        return True

    @staticmethod
    def _get_chromium_version():
        result = str(subprocess.check_output(["chromium", "--product-version"]))
        version = re.findall(r"(\d*)\.", result)[0]
        logging.info(f"chromium-driver version is {version}")
        return int(version)