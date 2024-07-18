import streamlit as st
import pandas as pd
from datetime import datetime
import random

# Function to split the data
def split_data(df):
    # Extract Title and SKU based on the assumption that the first two columns are Title and SKU
    title_sku_columns = df.columns[:2].tolist()
    title_column = title_sku_columns[0]
    sku_column = title_sku_columns[1]

    # Check the format of the SKU column
    for i in random.sample(range(len(df)), 3):
        sku = df.iloc[i, 1]
        if not isinstance(sku, str) or not len(sku.split('-')) == 3:
            st.error("SKU format validation failed. Ensure the SKU format is XX-XXXX-XXXX.")
            return None, None

    # Identify B2B columns
    b2b_columns = [col for col in df.columns[2:] if "B2B" in col]

    # Identify B2C columns
    b2c_columns = [col for col in df.columns[2:] if col not in b2b_columns]

    # Construct DataFrames
    b2c_df = df[title_sku_columns + b2c_columns]
    b2b_df = df[title_sku_columns + b2b_columns]

    return b2c_df, b2b_df

# Streamlit app layout
st.title("CSV Splitter App")
st.write("Upload a CSV file and get two separate files for B2C and B2B data.")

# File upload
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file)

    # Split the data
    b2c_df, b2b_df = split_data(df)

    if b2c_df is not None and b2b_df is not None:
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Generate filenames
        b2c_filename = f"{current_date}_b2c.csv"
        b2b_filename = f"{current_date}_b2b.csv"

        # Convert DataFrames to CSV for download
        b2c_csv = b2c_df.to_csv(index=False).encode('utf-8')
        b2b_csv = b2b_df.to_csv(index=False).encode('utf-8')

        # Provide download buttons
        st.download_button(
            label="Download B2C Data",
            data=b2c_csv,
            file_name=b2c_filename,
            mime='text/csv'
        )

        st.download_button(
            label="Download B2B Data",
            data=b2b_csv,
            file_name=b2b_filename,
            mime='text/csv'
        )
