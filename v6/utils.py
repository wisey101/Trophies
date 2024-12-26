# utils.py
import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection, execute_query

# Initialize Supabase connection
supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]

# Mapping from singular to plural for categories
singular_to_plural = {
    'trophy': 'trophies',
    'medal': 'medals',
    'cup': 'cups'  # Added for consistency
}

@st.cache_data(ttl=1200)
def load_data(materials_dict):
    data_frames = []

    # Process standard product tables (e.g., trophies_acrylic, medals_wood, etc.)
    for category, materials in materials_dict.items():
        for material in materials:
            table = f'{category}_{material}'
            size_table = f'{table}_sizes'

            # Fetch data from Supabase
            response = execute_query(supabase.table(table).select("*"), ttl=0)
            size_response = execute_query(supabase.table(size_table).select("*"), ttl=0)

            # Base URL for image storage
            base_url = f"{supabase_url}/storage/v1/object/public/{table}/"

            # Check if both responses have data
            if hasattr(response, 'data') and hasattr(size_response, 'data'):
                data = response.data
                size_data = size_response.data
                if data and size_data:
                    prod_df = pd.DataFrame(data)
                    sizes_df = pd.DataFrame(size_data)

                    # Merge product and size data
                    ungrouped_df = pd.merge(prod_df, sizes_df, on='model', how='left')
                    grouped = ungrouped_df.groupby('model').agg({
                        'size': lambda x: list(x.dropna()),
                        'size_code': lambda x: list(x.dropna())
                    }).reset_index()

                    # Merge back to get sizes and size_codes
                    df = pd.merge(prod_df, grouped, on='model', how='left')

                    # Construct image URL
                    df['model_code_clean'] = df['model'].str.replace(" ", "_")
                    df['image url'] = base_url + df['model_code_clean'] + '.jpg'

                    # Construct product name
                    df['product name'] = df.apply(
                        lambda row: f"{row['name']} {row['sport']} {row['type']}" if row['name'] else None, axis=1
                    )

                    # Assign 'range'
                    df['range'] = df['name']

                    # Select and rename columns for consistency
                    df = df[['product name', 'model', 'image url', 'size', 'size_code', 'product_code', 'range', 'sport']]
                    df.rename(columns={
                        'model': 'code',
                        'size': 'sizes',
                        'size_code': 'size_codes'
                    }, inplace=True)

                    # Append to the list of DataFrames
                    data_frames.append(df)

    # Process the new 'metal_cups' table separately
    metal_cups_response = execute_query(supabase.table("metal_cups").select("*"), ttl=0)
    if hasattr(metal_cups_response, 'data') and metal_cups_response.data:
        metal_cups_data = metal_cups_response.data
        metal_cups_df = pd.DataFrame(metal_cups_data)

        # Verify that required columns exist
        required_columns = {'name', 'colour', 'code', 'image_url', 'sizes'}
        if not required_columns.issubset(metal_cups_df.columns):
            st.error(f"Missing columns in metal_cups table. Required columns: {required_columns}")
            return pd.DataFrame()

        # Construct 'product name' as "name + colour + Metal Cup"
        metal_cups_df['product name'] = metal_cups_df.apply(
            lambda row: f"{row['name']} {row['colour']} Metal Cup", axis=1
        )

        # Assign 'image url' directly from 'image_url' column
        metal_cups_df['image url'] = metal_cups_df['image_url']

        # 'sizes' are already present; since there are no size codes, set 'size_codes' same as 'sizes'
        metal_cups_df['size_codes'] = metal_cups_df['sizes']

        # Assign 'product code' as 'code'
        metal_cups_df['product_code'] = metal_cups_df['code']

        # Fill in other required columns with placeholders or appropriate values
        metal_cups_df['range'] = metal_cups_df['name']
        metal_cups_df['sport'] = None  # Assuming 'metal_cups' don't have a 'sport' category

        # Select and reorder columns to match the standard format
        metal_cups_df = metal_cups_df[[
            'product name',
            'code',
            'image url',
            'sizes',
            'size_codes',
            'product_code',
            'range',
            'sport'
        ]]

        # Append to the list of DataFrames
        data_frames.append(metal_cups_df)

    # Combine all DataFrames into one
    if data_frames:
        all_data = pd.concat(data_frames, ignore_index=True)

        # Ensure 'product code' exists in all entries
        if 'product_code' not in all_data.columns:
            st.error("'product_code' column is missing from the combined DataFrame.")
            return pd.DataFrame()

        # Rename 'product_code' to 'product code' for consistency
        all_data.rename(columns={'product_code': 'product code'}, inplace=True)

        # Assign to session state
        st.session_state['products'] = all_data
        return all_data
    else:
        st.error("No data found in any of the product tables.")
        return pd.DataFrame()
