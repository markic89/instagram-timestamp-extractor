#!/usr/bin/env python
# coding: utf-8

# In[5]:


#!/usr/bin/env python
# coding: utf-8

import streamlit as st
import pandas as pd
import instaloader
from datetime import datetime
from tqdm.auto import tqdm
import re
import io
import time

st.set_page_config(page_title="Instagram Timestamp Extractor", layout="centered")
st.title("Instagram Timestamp Extractor")
st.markdown(
    """
    Owned and Created by Marco Marinone 
    
    **Instructions**:  
    1. Upload a CSV with Instagram URLs (and optional usernames).  
    2. Click "Extract Timestamps."  
    3. Download the two output CSVs.  
    *Example*: `username,url` or just `url` (ALWAYS WITH headers).  
    """
)

@st.cache_resource
def init_instaloader():
    L = instaloader.Instaloader()
    L.download_comments = False
    L.save_metadata = False
    L.download_geotags = False
    return L

L = init_instaloader()

def get_instagram_timestamp_via_instaloader(post_url: str) -> str:
    url = post_url.strip()
    m = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#]+)/?", url)
    if not m:
        return "ERROR_BAD_URL"
    shortcode = m.group(1)
    try:
        time.sleep(12)
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except instaloader.exceptions.QueryReturnedNotFoundException:
        return "ERROR_NOT_FOUND"
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        return "ERROR_PRIVATE"
    except Exception as e:
        return f"ERROR_INSTALOADER: {e}"
    dt = post.date_utc
    return dt.strftime("%Y-%m-%d %H:%M:%S")

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
        # Fix for headerless CSV: map first column to username, second to url
        df_in = pd.read_csv(uploaded_file, header=None, names=["username", "url"])
        if len(df_in.columns) < 2:
            df_in["url"] = df_in["username"]  # If only one column, treat as url
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
                ts = get_instagram_timestamp_via_instaloader(u)
                timestamps.append(ts)
                progress_bar.progress((idx + 1) / len(df_urls))

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

st.markdown("**Note**: Only public posts work. Private posts return errors.")


# In[ ]:




