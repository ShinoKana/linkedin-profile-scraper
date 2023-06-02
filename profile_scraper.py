import json
import os
import pickle
import time
from collections import defaultdict
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LAParams, LTTextLine
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def save_cookies(driver, path):
    with open(path, 'wb') as file:
        pickle.dump(driver.get_cookies(), file)


def load_cookies(driver, path):
    with open(path, 'rb') as file:
        cookies = pickle.load(file)
        for cookie in cookies:
            driver.add_cookie(cookie)


def process_pdf(pdf_path, user_id):
    result = defaultdict(list)
    current_title = ""
    titles_set = set()

    laparams = LAParams()

    for page_layout in extract_pages(pdf_path, laparams=laparams):
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                for text_line in element:
                    if isinstance(text_line, LTTextLine):
                        line_text = []
                        line_size = []
                        for character in text_line:
                            if isinstance(character, LTChar):
                                line_text.append(character.get_text())
                                line_size.append(character.size)
                        line_text = "".join(line_text).rstrip()
                        average_size = sum(line_size) / len(line_size) if line_size else None

                        if line_text and average_size >= 9:  # Only include text with size >= 9
                            if average_size >= 13:  # Title
                                title = line_text
                                while title in titles_set:  # Resolve title conflicts
                                    title += "_"
                                current_title = title
                                titles_set.add(title)
                            else:
                                result[current_title].append(line_text)

    # Filter out sections without content
    result = {k: v for k, v in result.items() if v}

    # Saves the results to a JSON file.
    json_path = os.path.join(os.path.dirname(pdf_path), f"{user_id}.json")

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)


def get_profile_info(username, password, user_id):
    # Setup Chrome options
    download_dir = os.path.join(os.getcwd(), 'profile')  # Set download path to current directory/profile
    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    chrome_options = Options()
    
    # Enable headless mode
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    
    # Required to run headless on Docker
    chrome_options.add_argument("--no-sandbox")
    # Set window size
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Set Chrome's download settings
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
    })
    
    driver = webdriver.Chrome(executable_path='<Path to your Chrome Driver>', options=chrome_options)

    # Add command to download files in headless mode
    driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
    params = {'cmd': 'Page.setDownloadBehavior', 'params': {'behavior': 'allow', 'downloadPath': download_dir}}
    driver.execute("send_command", params)

    try:
        driver.get('https://www.linkedin.com')
        load_cookies(driver, 'cookies.pkl')
        driver.get(f"https://www.linkedin.com/in/{user_id}/")
    except:
        driver.get('https://www.linkedin.com/login')
        username_field = driver.find_element(By.NAME, 'session_key')
        username_field.send_keys(username)
        time.sleep(1)
        password_field = driver.find_element(By.NAME, 'session_password')
        password_field.send_keys(password)
        wait = WebDriverWait(driver, 3)
        login_button = wait.until(EC.presence_of_element_located((By.XPATH, '//button[@class="btn__primary--large from__button--floating"]')))
        login_button.click()
        save_cookies(driver, 'cookies.pkl')
        driver.get(f"https://www.linkedin.com/in/{user_id}/")

    wait = WebDriverWait(driver, 3)
    time.sleep(2)
    more_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//button[contains(@class, "artdeco-dropdown__trigger") and contains(@class, "pvs-profile-actions__action") and (contains(@aria-label, "More actions") or contains(@aria-label, "更多動作"))]')))
    driver.execute_script("arguments[0].click();", more_button)
    
    save_to_pdf_button = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "artdeco-dropdown__item")]//span[contains(text(), "Save to PDF") or contains(text(), "存為 PDF")]')))
    driver.execute_script("arguments[0].click();", save_to_pdf_button)

    start_time = time.time()
    pdf_name = None

    # Wait until the PDF has been downloaded.
    while pdf_name is None:
        pdf_name = next((name for name in os.listdir(download_dir) if name.startswith("Profile") and name.endswith(".pdf")), None)
        
        if time.time() - start_time > 10:  # Timeout after 10 seconds.
            raise Exception("Timeout waiting for file to download")

        time.sleep(0.5)  # Wait a bit before trying again.

    # The actual path of the downloaded file.
    pdf_path = os.path.join(download_dir, pdf_name)
    # Rename the file to your desired format
    new_pdf_path = os.path.join(download_dir, f"{user_id}_Profile.pdf")
    os.rename(pdf_path, new_pdf_path)
    print(f"Found PDF at: {new_pdf_path}")  # Debug: print actual path

    # Process the PDF.
    process_pdf(new_pdf_path, user_id)
    # Delete the PDF.
    os.remove(new_pdf_path)

    driver.quit()


def main():
    # Loads the configuration data from the JSON file.
    with open("config.json") as f:
        config = json.load(f)

    # Gets the profile data.
    get_profile_info(config["username"], config["password"], config["user_id"])


if __name__ == "__main__":
    main()
