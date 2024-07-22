import streamlit as st
import pandas as pd
from datetime import datetime
import random
import re
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Document, StorageContext, load_index_from_storage
import os
from time import sleep

# Set the OpenAI API key
import openai
openai.api_key = st.secrets["OPENAI_API_KEY"]

# Function to split the data
def split_data(df, progress_bar, status_text, test_mode=False):
    print("Starting split_data function")
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
            raise ValueError("SKU format validation failed. Ensure the SKU format is XX-XXXX-XXXX.")

    # Identify B2B columns
    b2b_columns = [col for col in df.columns[2:] if "B2B" in col]

    # Identify B2C columns
    b2c_columns = [col for col in df.columns[2:] if col not in b2b_columns]

    print("Columns identified. Starting sport analysis.")
    # Add sport analysis
    index = get_or_create_index(df)
    query_engine = index.as_query_engine()

    all_sports = []
    batch_size = 30 if not test_mode else 1
    for i in range(0, len(df), batch_size):
        batch = df['Title'].iloc[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1}")
        for title in batch:
            response = query_engine.query(f"What sport or activity is this product related to: {title}")
            all_sports.append(str(response))
            print(f"Processed title: {title}")
            print(f"Sport identified: {response}")
        
        # Update progress
        progress = min((i + batch_size) / len(df), 1.0)
        progress_bar.progress(progress)
        status_text.text(f"Processed {min(i + batch_size, len(df))} out of {len(df)} products")
        
        if test_mode:
            print("Test mode active. Stopping after one batch.")
            break

    df['Sport'] = all_sports

    # Construct DataFrames
    b2c_df = df[title_sku_columns + ['Sport'] + b2c_columns]
    b2b_df = df[title_sku_columns + ['Sport'] + b2b_columns]

    print("Data split complete.")
    return b2c_df, b2b_df

# Function to filter data by product type
def filter_data(df, product_type):
    print(f"Filtering data for product type: {product_type}")
    if product_type == "Medals":
        filtered_df = df[df['Title'].str.contains('medal', case=False, na=False)]
    elif product_type == "Trophies":
        filtered_df = df[df['Title'].str.contains('trophy|award', case=False, na=False)]
    elif product_type == "All":
        filtered_df = df
    else:
        filtered_df = df[~df['Title'].str.contains('medal', case=False, na=False) & 
                         ~df['Title'].str.contains('trophy|award', case=False, na=False)]
    print(f"Filtered data shape: {filtered_df.shape}")
    return filtered_df

# Function to perform the analysis and return top and bottom 20 based on the selected metric
def analyze_data(df, metric):
    print(f"Analyzing data for metric: {metric}")
    # Determine if it's B2B or B2C by checking for B2B columns
    if any("B2B" in col for col in df.columns):
        units_ordered_col = 'Units ordered - B2B'
        ordered_product_sales_col = 'Ordered product sales - B2B'
        sessions_total_col = 'Sessions – Total – B2B'
    else:
        units_ordered_col = 'Units ordered'
        ordered_product_sales_col = 'Ordered product sales'
        sessions_total_col = 'Sessions - Total'
    
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
        df[ordered_product_sales_col] = df[ordered_product_sales_col].apply(lambda x: float(re.sub(r'[^\d.]', '', x)))
        revenue_by_product = df[['Title', ordered_product_sales_col]].groupby('Title').sum().sort_values(by=ordered_product_sales_col, ascending=False)
        top_products = revenue_by_product.head(20)
        bottom_products = revenue_by_product.tail(20)
    elif metric == "Conversion Rate":
        conversion_rates = df[['Title', units_ordered_col, sessions_total_col]].copy()
        conversion_rates[units_ordered_col] = pd.to_numeric(conversion_rates[units_ordered_col], errors='coerce')
        conversion_rates[sessions_total_col] = pd.to_numeric(conversion_rates[sessions_total_col], errors='coerce')
        conversion_rates['Conversion Rate'] = (conversion_rates[units_ordered_col] / conversion_rates[sessions_total_col]) * 100
        top_products = conversion_rates.sort_values(by='Conversion Rate', ascending=False).head(20)
        bottom_products = conversion_rates.sort_values(by='Conversion Rate', ascending=False).tail(20)
    
    print("Analysis complete.")
    return top_products, bottom_products

@st.cache_resource
def get_or_create_index(df):
    print("Getting or creating index")
    PERSIST_DIR = "./storage"
    if not os.path.exists(PERSIST_DIR):
        print("Creating new index")
        documents = [Document(text=title) for title in df['Title']]
        index = VectorStoreIndex.from_documents(documents)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        print("Loading existing index")
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
    return index

@st.cache_data
def load_and_process_data(uploaded_file):
    print("Loading and processing data")
    df = pd.read_csv(uploaded_file)
    df['Title'] = df['Title'].apply(lambda x: ' '.join(x.split()[2:]))
    print(f"Data shape after loading: {df.shape}")
    return df

@st.cache_data
def process_sports_data(df, test_mode=False):
    print("Processing sports data")
    st.subheader("Processing Sports Data")
    progress_bar = st.progress(0)
    status_text = st.empty()

    b2c_df, b2b_df = split_data(df, progress_bar, status_text, test_mode)
    print(f"B2C data shape: {b2c_df.shape}")
    print(f"B2B data shape: {b2b_df.shape}")
    return b2c_df, b2b_df

# Streamlit app layout
st.title("CSV Splitter App")
st.write("Upload a CSV file and view B2C or B2B data.")

# Test mode checkbox
test_mode = st.checkbox("Test Mode (Process only one batch)")

# File upload
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    try:
        df = load_and_process_data(uploaded_file)

        with st.spinner('Analyzing sports for each product...'):
            b2c_df, b2b_df = process_sports_data(df, test_mode)

        # Display radio buttons for B2C and B2B selection
        option = st.radio("Select data type:", ["B2C", "B2B"], horizontal=True)
        
        current_date = datetime.now().strftime("%Y-%m-%d")

        if option == "B2C":
            selected_df = b2c_df
            filename = f"{current_date}_b2c.csv"
        else:  # B2B
            selected_df = b2b_df
            filename = f"{current_date}_b2b.csv"

        # Convert DataFrame to CSV for download
        csv = selected_df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label=f"Download {option} Data",
            data=csv,
            file_name=filename,
            mime='text/csv'
        )

        # Display radio buttons for product type selection
        product_type = st.radio("Select product type:", ["All", "Medals", "Trophies", "Other"], horizontal=True)

        filtered_df = filter_data(selected_df, product_type)

        with st.expander("View Data"):
            st.write(f"Number of rows: {len(filtered_df)}")
            st.dataframe(filtered_df)

        # Analysis section
        st.subheader("Product Analysis")
        analysis_metric = st.radio("Select Analysis Metric", ["Units Ordered", "Revenue", "Conversion Rate"], horizontal=True)

        top_products, bottom_products = analyze_data(filtered_df, analysis_metric)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"Top 20 Products by {analysis_metric}")
            st.dataframe(top_products)
        with col2:
            st.subheader(f"Bottom 20 Products by {analysis_metric}")
            st.dataframe(bottom_products)

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        print(f"Error: {str(e)}")
else:
    st.info("Please upload a CSV file to begin.")