import streamlit as st
from st_supabase_connection import SupabaseConnection, execute_query

# Initialize connection.
conn = st.connection("supabase",type=SupabaseConnection)

supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]
bucket_name = "test"

test = conn.list_objects(bucket_name)

# Base URL for your Supabase storage
base_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/"

for image in test:
    image_url = base_url + image["name"]
    st.image(image_url, caption=image["name"], use_column_width=True)



