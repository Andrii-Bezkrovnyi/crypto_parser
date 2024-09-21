import csv
import logging
import os
import time

import schedule
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

load_dotenv()

BASE_URL = "https://defillama.com/chains"
DOWNLOAD_INTERVAL = int(os.getenv("DOWNLOAD_INTERVAL", default=300))
PROXY = os.getenv("PROXY")
ROW_HEIGHT = 30

logging.basicConfig(
    filename="scraper.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def parse_chains(driver: webdriver.Chrome, url: str) -> dict[int, list]:
    driver.get(url)
    time.sleep(5)
    chains_element = driver.find_element(By.CSS_SELECTOR, "span.sc-d6729567-2.fIaosP")
    driver.execute_script("return arguments[0].scrollIntoView(true);", chains_element)
    time.sleep(1)
    headers = get_headers(driver)
    data = {}
    i = 0
    total = int(chains_element.text)
    logging.info(f"Total chains: {total}")
    while i < total:
        rows = driver.find_elements(
            By.CSS_SELECTOR, "div.sc-5a00cfd2-0.dHYMLV >div:nth-child(2)>div"
        )
        for row in rows:
            row_num, name, protocol, tvl = parse_row_data(headers, row)
            if row_num not in data:
                i += 1
                logging.info(f"Parsed chain #: {i} successfully")
                data[row_num] = [name, protocol, tvl]
        scroll_height = len(rows) * ROW_HEIGHT
        driver.execute_script(f"window.scrollBy(0, {scroll_height});")
        time.sleep(0.5)

    logging.info(f"Parsing chains done!")
    return data


def get_headers(driver: webdriver.Chrome) -> list[str]:
    header_elements = driver.find_elements(
        By.CSS_SELECTOR,
        "div.sc-5a00cfd2-0.dHYMLV > div:nth-child(1) > div > div > span > button",
    )
    return [element.text for element in header_elements]


def parse_row_data(headers: list[str], row: WebElement) -> tuple:
    columns = row.find_elements(By.CSS_SELECTOR, "div")
    row_num = get_row_num(columns)
    name = get_name(columns)
    protocol = get_protocols(headers, columns)
    tvl = get_tvl(headers, columns)
    return row_num, name, protocol, tvl


def get_row_num(columns: list[WebElement]) -> int:
    return int(
        columns[0]
        .find_element(By.CSS_SELECTOR, "span.sc-f61b72e9-0.iphTVP > span")
        .text
    )


def get_index(headers: list[str], header_name: str) -> int:
    return headers.index(header_name) + 1


def get_name(row: list[WebElement]) -> str:
    return row[0].find_element(By.CSS_SELECTOR, ".sc-8c920fec-3.dvOTWR").text


def get_protocols(headers: list[str], row: list[WebElement]) -> int:
    return int(row[get_index(headers, "Protocols")].text)


def get_tvl(headers: list[str], row: list[WebElement]) -> str:
    return str(row[get_index(headers, "TVL")].text)


def write_to_csv(output_csv_path: str, data: dict[int, list]) -> None:
    logging.info("Writing parsed chains to csv...")
    with open(output_csv_path, "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Name", "Protocols", "TVL"])
        csvwriter.writerows(data.values())
    logging.info(f"Writing {len(data)} chains to csv done!")


def scrape_and_write() -> None:
    web_driver = get_webdriver()
    try:
        parsed_data = parse_chains(web_driver, BASE_URL)
        write_to_csv("defillama.csv", parsed_data)
    except Exception as e:
        logging.error(f"Error occurred while parsing chains: {str(e)}")
    finally:
        web_driver.quit()


def get_webdriver() -> webdriver.Chrome:
    chrome_options = Options()
    # if PROXY:
    #     chrome_options.add_argument("--proxy-server=%s" % PROXY)
    return webdriver.Chrome(options=chrome_options)


if __name__ == "__main__":
    scrape_and_write()
    schedule.every(DOWNLOAD_INTERVAL).minutes.do(scrape_and_write)
    while True:
        schedule.run_pending()
        time.sleep(1)
