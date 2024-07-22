import streamlit as st
import pandas as pd
from datetime import datetime
import random
import re

# Function to split the data
def split_data(df):
    # Remove the first two columns
    df = df.iloc[:, 2:]
    
    # Extract Title and SKU based on the assumption that the new first two columns are Title and SKU
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

# Function to filter data by product type
def filter_data(df, product_type):
    if product_type == "Medals":
        filtered_df = df[df['Title'].str.contains('medal', case=False, na=False)]
    elif product_type == "Trophies":
        filtered_df = df[df['Title'].str.contains('trophy|award', case=False, na=False)]
    elif product_type == "All":
        filtered_df = df
    else:
        filtered_df = df[~df['Title'].str.contains('medal', case=False, na=False) & 
                         ~df['Title'].str.contains('trophy|award', case=False, na=False)]
    return filtered_df

# Function to perform the analysis and return top and bottom 20 based on the selected metric
def analyze_data(df, metric):
    # Determine if it's B2B or B2C by checking for B2B columns
    if any("B2B" in col for col in df.columns):
        units_ordered_col = 'Units ordered - B2B'
        ordered_product_sales_col = 'Ordered product sales - B2B'
        sessions_total_col = 'Sessions – Total – B2B'
    else:
        units_ordered_col = 'Units ordered'
        ordered_product_sales_col = 'Ordered product sales'
        sessions_total_col = 'Sessions - Total'
    
    # Debug print to check available columns
    print("Available columns in DataFrame:", df.columns)

    if units_ordered_col not in df.columns:
        st.error(f"Column '{units_ordered_col}' not found in the data.")
        return pd.DataFrame(), pd.DataFrame()
    if ordered_product_sales_col not in df.columns:
        st.error(f"Column '{ordered_product_sales_col}' not found in the data.")
        return pd.DataFrame(), pd.DataFrame()
    if sessions_total_col not in df.columns:
        st.error(f"Column '{sessions_total_col}' not found in the data.")
        return pd.DataFrame(), pd.DataFrame()

    if metric == "Units Ordered":
        top_products = df[['Title', units_ordered_col]].sort_values(by=units_ordered_col, ascending=False).head(20)
        bottom_products = df[['Title', units_ordered_col]].sort_values(by=units_ordered_col, ascending=False).tail(20)
    elif metric == "Revenue":
        # Remove non-numeric characters and convert to float
        df[ordered_product_sales_col] = df[ordered_product_sales_col].apply(lambda x: float(re.sub(r'[^\d.]', '', x)))
        revenue_by_product = df[['Title', ordered_product_sales_col]].groupby('Title').sum().sort_values(by=ordered_product_sales_col, ascending=False)
        top_products = revenue_by_product.head(20)
        bottom_products = revenue_by_product.tail(20)
    elif metric == "Conversion Rate":
        conversion_rates = df[['Title', units_ordered_col, sessions_total_col]].copy()
        # Ensure columns are numeric
        conversion_rates[units_ordered_col] = pd.to_numeric(conversion_rates[units_ordered_col], errors='coerce')
        conversion_rates[sessions_total_col] = pd.to_numeric(conversion_rates[sessions_total_col], errors='coerce')
        conversion_rates['Conversion Rate'] = (conversion_rates[units_ordered_col] / conversion_rates[sessions_total_col]) * 100
        top_products = conversion_rates.sort_values(by='Conversion Rate', ascending=False).head(20)
        bottom_products = conversion_rates.sort_values(by='Conversion Rate', ascending=False).tail(20)
    return top_products, bottom_products

# Streamlit app layout
st.title("CSV Splitter App")
st.write("Upload a CSV file and view B2C or B2B data.")

# File upload
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    # Read the uploaded file
    df = pd.read_csv(uploaded_file)
    
    # Remove the first two words from the "Title" column
    df['Title'] = df['Title'].apply(lambda x: ' '.join(x.split()[2:]))

    # Split the data
    b2c_df, b2b_df = split_data(df)

    if b2c_df is not None and b2b_df is not None:
        # Display radio buttons for B2C and B2B selection
        option = st.radio("", ["B2C", "B2B"], horizontal=True, key="radio_selection", label_visibility="collapsed")
        
        # Get current date
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Generate filenames
        b2c_filename = f"{current_date}_b2c.csv"
        b2b_filename = f"{current_date}_b2b.csv"

        # Convert DataFrames to CSV for download
        b2c_csv = b2c_df.to_csv(index=False).encode('utf-8')
        b2b_csv = b2b_df.to_csv(index=False).encode('utf-8')

        if option == "B2C":
            st.subheader("B2C Data")
            selected_df = b2c_df
            st.download_button(
                label="Download B2C Data",
                data=b2c_csv,
                file_name=b2c_filename,
                mime='text/csv'
        )
        elif option == "B2B":
            st.subheader("B2B Data")
            selected_df = b2b_df
            st.download_button(
                label="Download B2B Data",
                data=b2b_csv,
                file_name=b2b_filename,
                mime='text/csv'
        )

        # Display radio buttons for product type selection
        product_type = st.radio("", ["All","Medals", "Trophies", "Other"], horizontal=True, key="product_type_selection", label_visibility="collapsed")

        filtered_df = filter_data(selected_df, product_type)

        # Display the number of rows
        st.write(f"Number of rows: {len(filtered_df)}")
        
        # Display the csv
        st.dataframe(filtered_df)

        # New set of radio buttons for analysis
        analysis_metric = st.radio("Select Analysis Metric", ["Units Ordered", "Revenue", "Conversion Rate"], horizontal=True, key="analysis_metric_selection")

        # Perform analysis based on selected metric
        top_products, bottom_products = analyze_data(filtered_df, analysis_metric)

        st.subheader(f"Top 20 Products by {analysis_metric}")
        st.dataframe(top_products)

        st.subheader(f"Bottom 20 Products by {analysis_metric}")
        st.dataframe(bottom_products)
