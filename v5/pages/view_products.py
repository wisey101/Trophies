import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("All products")
st.page_link("Trophy_manager.py", label="**Back**", icon="⬅️")

# Access the final DataFrame from session state
products_df = st.session_state['products']

# Create two lists: one for product codes with a range, one without
with_range_df = products_df[products_df['range'].notna()]
without_range_df = products_df[products_df['range'].isna()]

view_as_table = st.toggle("Switch views", value=True)

# Function to display cards
def display_cards(df, col):
    # Iterate over unique product codes
    for product_code in df['product code'].unique():
        # Filter the DataFrame for the current product code
        product_subset = df[df['product code'] == product_code]
        
        # Get the first row for product details
        row = product_subset.iloc[0]
        
        # Count how many products have this product code
        product_count = len(product_subset)
        
        # Extract details from the row
        range_value = row['range'] if pd.notna(row['range']) else "No range available"
        image_url = row['image url']
        
        # Display card-like layout with product details
        with col:
            st.markdown(f"### Product Code: {product_code}")
            st.markdown(f"**Number of Products:** {product_count}")
            st.markdown(f"**UK Name:** {range_value}")
            with st.popover("View example image"):
                st.image(image_url, width=200)
            st.markdown("---")  # Divider between cards

# Function to display tables
def display_tables(df_with_range, df_without_range):
    # Reduce both DataFrames to display only the necessary columns: code, number of products, name (range)
    
    # For products with a UK name, we can safely count the 'product name' since 'range' is not null
    with_range_summary = df_with_range.groupby('product code').agg({
        'product code': 'first',
        'product name': 'count',  # This works because there are no missing 'product name' values
        'range': 'first'
    }).rename(columns={'product name': 'Number of Products'}).reset_index(drop=True)

    # For products without a UK name, we should use size() to count all rows, even if 'product name' is NaN
    without_range_summary = df_without_range.groupby('product code').agg({
        'product code': 'first',
        'code': 'count',  # This counts all occurrences of 'product code' regardless of NaN values
        'range': 'first'
    }).rename(columns={'code': 'Number of Products'}).reset_index(drop=True)

    # Display tables side by side
    a, col1, col2, b = st.columns([1.5, 2, 2, 1.5])
    
    with col1:
        st.header("Products with UK name", )
        st.dataframe(with_range_summary, use_container_width=True)
    
    with col2:
        st.header("Products without UK name")
        st.dataframe(without_range_summary, use_container_width=True)


# Display content based on the toggle state
if view_as_table:
    # If the toggle is on, display the table view
    display_tables(with_range_df, without_range_df)
else:
    # If the toggle is off, display the full page (card view)
    a, col1, col2, b = st.columns([1, 3, 3, 1])

    # Display cards for products with range in column 1
    col1.header("Products with UK name")
    display_cards(with_range_df, col1)

    # Display cards for products without range in column 2
    col2.header("Products without UK name")
    display_cards(without_range_df, col2)
