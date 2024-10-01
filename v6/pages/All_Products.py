import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection
from utils import load_data  # Import load_data from utils

st.set_page_config(layout="wide")

supabase = st.connection("supabase", type=SupabaseConnection)

st.title("All products")
st.page_link("Trophy_manager.py", label="**Back**", icon="⬅️")

# Check if 'products' is in session_state
if 'products' not in st.session_state:
    st.warning("Product data not found. Loading data now...")
    materials_dict = {
        'trophies': ['acrylic', 'wood'],
        'medals': ['acrylic', 'wood', 'metal']
    }
    load_data(materials_dict)

# Access the final DataFrame from session state
products_df = st.session_state['products']

# Create two lists: one for product codes with a range, one without
with_range_df = products_df[products_df['range'].notna()]
without_range_df = products_df[products_df['range'].isna()]

view_as_table = st.toggle("Switch views", value=True)

# Need this for streamlit to do something with hashes or some bs
def execute_query(_query):
    try:
        response = _query.execute()
        return response
    except Exception as e:
        st.error(f"Failed to execute query: {e}")
        return None

# Updates product name for the products without UK name table
def update_product_name(code, new_name):
    try:
        # Step 1: Update name_reference table with new name
        update_name_ref = supabase.table("name_reference").update({"name": new_name}).eq("code", code)
        testresp = execute_query(update_name_ref)
        print(f"Executed update name ref, {testresp.data}")
        
        # Step 2: Fetch the source from name_reference
        fetch_source = supabase.table("name_reference").select("source").eq("code", code)
        response = execute_query(fetch_source)
        print(f"Executed fetch source, response: {response.data}")
        
        # Step 3: Check if response contains data and access 'source'
        if response and len(response.data) > 0 and 'source' in response.data[0]:
            source_table = response.data[0]['source']
            print(f"Source table: {source_table}")
            
            # Step 4: Update the name in the source table using product_code
            update_source_table = supabase.table(source_table).update({"name": new_name}).eq("product_code", code)
            
            # Log the query for debugging
            print(f"Updating source table: {source_table} with product_code: {code} and new_name: {new_name}")
            
            source_update_resp = execute_query(update_source_table)
            print(f"Executed update source table, response: {source_update_resp.data}")
            
            if source_update_resp and source_update_resp.data:
                st.success(f"Source table '{source_table}' updated for code: {code}")
            else:
                st.error(f"Failed to update source table '{source_table}' for code: {code}. No changes made.")
        else:
            st.error("Source information not found for the given code.")
    except Exception as e:
        st.error(f"Failed to update source table: {e}")

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
        st.header("On UK site", )
        edited_df = st.data_editor(
            with_range_summary, 
            column_config={"range": "Enter new name"},  # Makes the "range" column editable
            num_rows="fixed",  # Prevent row addition/removal
            hide_index=True
        )
        
        # Check for changes in the "range" column (new names)
        for idx, row in edited_df.iterrows():
            new_name = row['range']  # New name entered by the user
            product_code = row['product code']  # Get product code to reference original df

            # Use product_code to retrieve the original name
            original_row = df_with_range[df_with_range['product code'] == product_code]
            
            # Ensure there is an original row to compare
            if not original_row.empty:
                original_name = original_row.iloc[0]['range'] if pd.notna(original_row.iloc[0]['range']) else None
                
                # If the name has been changed, update in the database
                if new_name != original_name and new_name:
                    print(f"new_name = {new_name}, original_name = {original_name}")
                    update_product_name(product_code, new_name)
    
    with col2:
        st.header("Not on UK site")
        edited_df = st.data_editor(
            without_range_summary, 
            column_config={"range": "Enter new name"},  # Makes the "range" column editable
            num_rows="fixed",  # Prevent row addition/removal
            hide_index=True
        )
        
        # Check for changes in the "range" column (new names)
        for idx, row in edited_df.iterrows():
            new_name = row['range']  # New name entered by the user
            original_name = df_without_range.iloc[idx]['range'] if pd.notna(df_without_range.iloc[idx]['range']) else None
            
            # If the name has been changed, update in the database
            if new_name != original_name and new_name:
                print(f"new_name = {new_name}, original_name = {original_name}")
                update_product_name(row['product code'], new_name)


# Display content based on the toggle state
if view_as_table:
    # If the toggle is on, display the table view
    display_tables(with_range_df, without_range_df)
else:
    # If the toggle is off, display the full page (card view)
    a, col1, col2, b = st.columns([1, 3, 3, 1])

    # Display cards for products with range in column 1
    col1.header("Products without model")
    display_cards(with_range_df, col1)

    # Display cards for products without range in column 2
    col2.header("Products without model")
    display_cards(without_range_df, col2)
