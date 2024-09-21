import csv
import os
import time

from dotenv import load_dotenv
from loguru import logger
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

load_dotenv()

BASE_URL = "https://defillama.com/chains"
DOWNLOAD_INTERVAL = int(os.getenv("DOWNLOAD_INTERVAL", default=300))
PROXY = os.getenv("PROXY")

logger.add("logs_info.log", level="INFO", format="{time} - {level} - {message}")


class WebDriverHandler:
    def __init__(self, proxy_address: str = None):
        self.proxy_address = proxy_address

    def initialize_webdriver(self) -> webdriver.Chrome:
        driver_options = Options()
        if self.proxy_address:
            driver_options.add_argument(f"--proxy-server={self.proxy_address}")
            driver = webdriver.Chrome(options=driver_options)
            try:
                driver.get(BASE_URL)
                logger.info("Proxy is working")
            except WebDriverException as e:
                logger.error(f"Proxy is not working: {e}")
                driver.quit()
                logger.info("Initializing WebDriver without proxy")
                driver_options = Options()
                driver = webdriver.Chrome(options=driver_options)
        else:
            driver = webdriver.Chrome(options=driver_options)
        return driver


class ChainDataExtractor:
    def __init__(self, chrome_driver: webdriver.Chrome):
        self.chrome_driver = chrome_driver

    def get_chain_data(self, target_url: str) -> dict[int, list]:
        # Load the target URL
        self.chrome_driver.get(target_url)
        time.sleep(5)  # Wait for the page to load

        # Find and scroll to the chain element
        chain_element = self.chrome_driver.find_element(By.CSS_SELECTOR, ".sc-d6729567-2.fIaosP")
        self.chrome_driver.execute_script("arguments[0].scrollIntoView(true);", chain_element)
        time.sleep(1)  # Allow time for the scroll

        # Extract headers for the data table
        header_labels = self.extract_headers()

        # Initialize data storage and counters
        extracted_data = {}
        current_count = 0
        total_chains = int(chain_element.text)
        logger.info(f"Total chains: {total_chains}")

        # Loop to extract data for each chain
        while current_count < total_chains:
            row_elements = self.extract_row_elements()

            for row_element in row_elements:
                # Extract data from the row
                row_number, chain_name, protocol_count, total_value_locked = self.extract_row_values(header_labels,
                                                                                                     row_element)

                # Store the extracted data if the row number is new
                if row_number not in extracted_data:
                    current_count += 1
                    logger.info(f"Parsed chain #: {current_count} successfully")
                    extracted_data[row_number] = [chain_name, protocol_count, total_value_locked]

            # Scroll down to load more rows
            self.scroll_down_page(len(row_elements) * 30)

        logger.info("Data extraction completed!")
        return extracted_data

    def extract_headers(self) -> list[str]:
        try:
            header_elements = self.chrome_driver.find_elements(
                By.CSS_SELECTOR,
                ":nth-child(1)>div>div>span>button",
            )
            return [element.text for element in header_elements]
        except (NoSuchElementException, AttributeError):
            return []

    def extract_row_elements(self) -> list[WebElement]:
        try:
            elements = self.chrome_driver.find_elements(
                By.CSS_SELECTOR,
                "div.sc-5a00cfd2-0.dHYMLV >div:nth-child(2)>div"
            )
            return elements
        except (NoSuchElementException, AttributeError):
            logger.info("There is no selector and list of elements is empty")
            return []

    def extract_row_values(self, headers: list[str], row: WebElement) -> tuple:
        try:
            columns = row.find_elements(By.CSS_SELECTOR, "div")
            row_number = self.get_row_number(columns)
            chain_name = self.get_chain_name(columns)
            protocol_count = self.get_protocol_count(headers, columns)
            total_value_locked = self.get_total_value_locked(headers, columns)
            return row_number, chain_name, protocol_count, total_value_locked
        except (NoSuchElementException, AttributeError):
            return None, None, None, None

    def get_row_number(self, columns: list[WebElement]) -> int:
        try:
            return int(
                columns[0]
                .find_element(By.CSS_SELECTOR, '[class="sc-f61b72e9-0 iphTVP"] span')
                .text
            )
        except (NoSuchElementException, AttributeError):
            return 0

    def get_header_index(self, headers: list[str], header_label: str) -> int:
        return headers.index(header_label) + 1

    def get_chain_name(self, columns: list[WebElement]) -> str:
        try:
            return columns[0].find_element(By.CSS_SELECTOR, ".sc-8c920fec-3.dvOTWR").text
        except (NoSuchElementException, AttributeError):
            return ""

    def get_protocol_count(self, headers: list[str], columns: list[WebElement]) -> int:
        try:
            return int(columns[self.get_header_index(headers, "Protocols")].text)
        except (NoSuchElementException, AttributeError):
            return 0

    def get_total_value_locked(self, headers: list[str], columns: list[WebElement]) -> str:
        try:
            return columns[self.get_header_index(headers, "TVL")].text
        except (NoSuchElementException, AttributeError):
            return ""

    def scroll_down_page(self, scroll_distance: int):
        self.chrome_driver.execute_script(f"window.scrollBy(0, {scroll_distance});")
        time.sleep(0.5)


class CSVFileWriter:
    @staticmethod
    def save_data_to_csv(file_path: str, extracted_data: dict[int, list]) -> None:
        logger.info("Saving extracted data to CSV")
        with open(file_path, "w", newline="") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Name", "Protocols", "TVL"])
            csv_writer.writerows(extracted_data.values())
        logger.info(f"Saving {len(extracted_data)} chains to CSV completed!")


class DeFiLlamaDataScraper:
    def __init__(self, base_url: str, proxy: str = None):
        self.base_url = base_url
        self.proxy = proxy
        self.web_driver_handler = WebDriverHandler(proxy)
        self.chrome_driver = self.web_driver_handler.initialize_webdriver()
        self.data_extractor = ChainDataExtractor(self.chrome_driver)
        self.csv_writer = CSVFileWriter()

    def run_scraper(self) -> None:
        try:
            extracted_data = self.data_extractor.get_chain_data(self.base_url)
            self.csv_writer.save_data_to_csv("defillama_data.csv", extracted_data)
        except Exception as e:
            logger.error(f"Error occurred during data extraction: {str(e)}")
        finally:
            self.chrome_driver.quit()


if __name__ == "__main__":
    while True:
        data_scraper = DeFiLlamaDataScraper(BASE_URL, PROXY)
        data_scraper.run_scraper()
        logger.info(f"Waiting for {DOWNLOAD_INTERVAL} seconds before the next scraping cycle.")
        time.sleep(DOWNLOAD_INTERVAL)
