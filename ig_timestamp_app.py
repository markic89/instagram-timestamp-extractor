#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from tqdm.auto import tqdm
import random
import time
import io
import base64
import json
from streamlit.components.v1 import html

st.set_page_config(page_title="Instagram Timestamp Extractor", layout="centered")
st.title("Instagram Timestamp Extractor")
st.markdown(
    """
    **Instructions**:  
    1. Upload a CSV with Instagram URLs (and optional Influencer Names).  
    2. Click "Extract Timestamps."  
    3. The output CSVs will automatically download at the end.  
    *Example*: `Influencer Name,url` or just `url` (with or without headers).  
    """
)

# Initialize Selenium driver with headless Chrome
@st.cache_resource
def init_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=options)
    return driver

driver = init_driver()

# Helper: Extract timestamp from URL using Selenium and JSON parsing
def get_instagram_timestamp_via_selenium(url: str) -> str:
    try:
        # Navigate to URL
        driver.get(url)
        # Wait for page to load with extra delay
        time.sleep(random.uniform(5, 10))
        # Scroll to load metadata
        for _ in range(4):
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(random.uniform(2, 4))
        # Wait for page content
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        # Extract page source and search for JSON data
        page_source = driver.page_source
        # Look for Instagram's embedded JSON (common pattern)
        json_match = re.search(r'window\.__additionalDataLoaded\((.*?)\);', page_source)
        if json_match:
            json_data = json.loads(json_match.group(1))
            # Navigate to post data (adjust based on structure)
            if "data" in json_data and "graphql" in json_data["data"]:
                post_data = json_data["data"]["graphql"]["shortcode_media"]
                timestamp = post_data.get("taken_at_timestamp")
                if timestamp:
                    dt = datetime.fromtimestamp(timestamp)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
        # Fallback to HTML if JSON fails
        soup = BeautifulSoup(page_source, "html.parser")
        time_tag = soup.find("time", {"datetime": True})
        if time_tag:
            datetime_str = time_tag["datetime"]
            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return "NO TIMESTAMP FOUND"
    except Exception as e:
        return f"ERROR: {str(e)}"

# File uploader for CSV input
uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file is not None:
    try:
        df_in = pd.read_csv(uploaded_file, header=0)
        url_col = next((col for col in df_in.columns if col.lower() == "url"), None)
        username_col = next((col for col in df_in.columns if col.lower() in ["username", "influencer name"]), None)

        if not url_col:
            df_in.columns = ["url"] + list(df_in.columns)[1:]
            url_col = "url"
        if not username_col:
            df_in["username"] = "unknown"
        else:
            df_in = df_in.rename(columns={username_col: "username"})

        df_urls = df_in[["username", url_col]].rename(columns={url_col: "url"})
    except pd.errors.ParserError:
        df_in = pd.read_csv(uploaded_file, header=None, names=["username", "url"])
        if len(df_in.columns) < 2:
            df_in["url"] = df_in["username"]
            df_in["username"] = "unknown"
        df_urls = df_in[["username", "url"]]
    except Exception as e:
        st.error(f"Error reading CSV: {e}")
        st.stop()

    df_urls["url"] = df_urls["url"].astype(str).str.strip()
    df_urls["username"] = df_urls["username"].astype(str).str.strip()
    df_urls = df_urls[df_urls["url"] != ""].reset_index(drop=True)

    st.write(f"Found {len(df_urls)} URLs")
    st.dataframe(df_urls.head(), use_container_width=True)

    if st.button("Extract Timestamps"):
        with st.spinner("Processing..."):
            timestamps = []
            progress_bar = st.progress(0)
            for idx, u in enumerate(tqdm(df_urls["url"], desc="Fetching", leave=False)):
                ts = get_instagram_timestamp_via_selenium(u)
                timestamps.append(ts)
                progress_bar.progress((idx + 1) / len(df_urls))
                time.sleep(random.uniform(5, 10))  # Extra delay for human mimicry

            df_urls["timestamp"] = timestamps
            df_success = df_urls[~df_urls["timestamp"].str.startswith("ERROR")]
            df_errors = df_urls[df_urls["timestamp"].str.startswith("ERROR")]

            st.success(f"Done! {len(df_success)} successes, {len(df_errors)} errors")
            if len(df_success) > 0:
                st.subheader("Successful Timestamps")
                st.dataframe(df_success, use_container_width=True)
            if len(df_errors) > 0:
                st.subheader("Errors")
                st.dataframe(df_errors, use_container_width=True)

            # Automatic download using JavaScript
            success_csv = df_success.to_csv(index=False).encode("utf-8")
            errors_csv = df_errors.to_csv(index=False).encode("utf-8")

            success_b64 = base64.b64encode(success_csv).decode()
            errors_b64 = base64.b64encode(errors_csv).decode()

            html(
                f"""
                <script>
                    function download_file(name, contents) {{
                        const a = document.createElement('a');
                        a.href = 'data:text/csv;base64,' + contents;
                        a.download = name;
                        a.click();
                    }}
                    download_file('ig_timestamps_success.csv', '{success_b64}');
                    download_file('ig_timestamps_errors.csv', '{errors_b64}');
                </script>
                """,
                height=0
            )
else:
    st.info("Upload a CSV to start.")

st.markdown("**Note**: Only public posts work. Random delays mimic human behavior.")
