#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime
from tqdm.auto import tqdm
import random
import time
import io

st.set_page_config(page_title="Instagram Timestamp Extractor", layout="centered")
st.title("Instagram Timestamp Extractor")
st.markdown(
    """
    **Instructions**:  
    1. Enter Instagram credentials (optional for private posts).  
    2. Upload a CSV with Instagram URLs (and optional Influencer Names).  
    3. Click "Extract Timestamps."  
    4. Download the two output CSVs.  
    *Example*: `Influencer Name,url` or just `url` (with or without headers).  
    """
)

# Form for Instagram credentials (optional)
username = st.text_input("Instagram Username (optional)", type="password")
password = st.text_input("Instagram Password (optional)", type="password")

# ─────────────────────────────────────────────────────────────────────────────
# 1) Initialize Selenium driver with headless Chrome
# ─────────────────────────────────────────────────────────────────────────────
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

# Login if credentials provided
if username and password and st.button("Login to Instagram"):
    with st.spinner("Logging in..."):
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(random.uniform(2, 5))  # Human-like delay
        try:
            user_input = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, "username")))
            user_input.send_keys(username)
            pass_input = driver.find_element(By.NAME, "password")
            pass_input.send_keys(password)
            pass_input.submit()
            time.sleep(random.uniform(5, 10))
            if "challenge" in driver.current_url or "suspicious" in driver.current_url:
                st.error("Login challenge detected. Complete it in a browser or try later.")
            else:
                st.success("Logged in successfully!")
        except Exception as e:
            st.error(f"Login failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# 2) Helper: Extract timestamp from URL using Selenium
# ─────────────────────────────────────────────────────────────────────────────
def get_instagram_timestamp_via_selenium(url: str) -> str:
    try:
        driver.get(url)
        time.sleep(random.uniform(3, 6))  # Mimic human loading time
        # Scroll to mimic human behavior
        driver.execute_script("window.scrollBy(0, 200);")
        time.sleep(random.uniform(1, 3))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        time_tag = soup.find("time")
        if not time_tag:
            return "NO <time> TAG"
        iso_ts = time_tag.get("datetime")
        if not iso_ts:
            return "NO DATETIME ATTR"
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        return f"ERROR: {e}"

# ─────────────────────────────────────────────────────────────────────────────
# 3) File uploader for CSV input
# ─────────────────────────────────────────────────────────────────────────────
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

            success_csv = df_success.to_csv(index=False).encode("utf-8")
            errors_csv = df_errors.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download Successful Timestamps",
                data=success_csv,
                file_name="ig_timestamps_success.csv",
                mime="text/csv",
            )
            st.download_button(
                label="Download Errors",
                data=errors_csv,
                file_name="ig_timestamps_errors.csv",
                mime="text/csv",
            )
else:
    st.info("Upload a CSV to start.")

st.markdown("**Note**: Only public posts work without login. Random delays mimic human behavior.")
