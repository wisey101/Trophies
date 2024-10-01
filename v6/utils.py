# utils.py
import streamlit as st
import pandas as pd
from st_supabase_connection import SupabaseConnection, execute_query

supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]

singular_to_plural = {
    'trophy': 'trophies',
    'medal': 'medals'
}

@st.cache_data(ttl=1200)
def load_data(materials_dict):
    data_frames = []

    for category, materials in materials_dict.items():
        for material in materials:
            table = f'{category}_{material}'
            size_table = f'{table}_sizes'

            response = execute_query(supabase.table(table).select("*"), ttl=0)
            size_response = execute_query(supabase.table(size_table).select("*"), ttl=0)

            base_url = f"{supabase_url}/storage/v1/object/public/{table}/"

            if hasattr(response, 'data') and hasattr(size_response, 'data'):
                data = response.data
                size_data = size_response.data

                if data and size_data:
                    prod_df = pd.DataFrame(data)
                    sizes_df = pd.DataFrame(size_data)
                    ungrouped_df = pd.merge(prod_df, sizes_df, on='model', how='left')
                    grouped = ungrouped_df.groupby('model').agg({
                        'size': lambda x: list(x.dropna()),
                        'size_code': lambda x: list(x.dropna())
                    }).reset_index()
                    df = pd.merge(prod_df, grouped, on='model', how='left')
                    df['model_code_clean'] = df['model'].str.replace(" ", "_")
                    df['image url'] = base_url + df['model_code_clean'] + '.jpg'
                    df['product name'] = df.apply(lambda row: f"{row['name']} {row['sport']} {row['type']}" if row['name'] else None, axis=1)
                    df['range'] = df['name']
                    df = df[['product name', 'model', 'image url', 'size', 'size_code', 'product_code', 'range']]
                    df.rename(columns={'model': 'code', 'size': 'sizes', 'size_code': 'size_codes', 'product_code': 'product code'}, inplace=True)
                    data_frames.append(df)

    if data_frames:
        all_data = pd.concat(data_frames, ignore_index=True)
        st.session_state['products'] = all_data
        return all_data
    else:
        st.write("No data found")
        return pd.DataFrame()
