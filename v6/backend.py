import os
import io
import streamlit as st
import mimetypes
from st_supabase_connection import SupabaseConnection, execute_query

# Initialize Supabase connection
supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]

class UploadFile(io.BytesIO):
    """A subclass of BytesIO to allow setting extra attributes."""
    pass

def insert_products_to_supabase(products):
    grouped = {}
    for product in products:
        table_name = product["raw_type"]
        if table_name not in grouped:
            grouped[table_name] = []
        grouped[table_name].append({
            "model": product["model"],
            "name": product["name"],
            "sport": product["sport"],
            "product_code": product["product_code"],
            "type": product["formatted_type"]
        })
    for table_name, data_list in grouped.items():
        _ = execute_query(supabase.table(table_name).insert(data_list), ttl=0)

def upload_images_to_supabase(products):
    for product in products:
        bucket_name = product["raw_type"]
        if product["temp_image_path"] and os.path.exists(product["temp_image_path"]):
            file_name = os.path.basename(product["temp_image_path"])
            with open(product["temp_image_path"], "rb") as f:
                file_bytes = f.read()
            mime_type, _ = mimetypes.guess_type(file_name)
            if mime_type is None:
                mime_type = "application/octet-stream"
            file_buffer = UploadFile(file_bytes)
            file_buffer.name = file_name
            file_buffer.type = mime_type
            _ = supabase.upload(
                bucket_name,
                source='local',
                file=file_buffer,
                destination_path=file_name,
                overwrite='true'
            )

def insert_sizes_and_update_sizes_table(products, sizes):
    grouped = {}
    for product in products:
        product_type = product["raw_type"]
        if product_type not in grouped:
            grouped[product_type] = []
        grouped[product_type].append(product)
    
    for product_type, product_list in grouped.items():
        product_code = product_list[0]["product_code"]
        _ = execute_query(supabase.table("product_sizes").insert({"product_code": product_code, "sizes": sizes}), ttl=0)
        sizes_table = f"{product_type}_sizes"
        for product in product_list:
            model = product["model"]
            for idx, size in enumerate(sizes):
                size_code_suffix = chr(65 + idx)
                size_code = model + size_code_suffix
                row_data = {"model": model, "size_code": size_code, "size": size}
                try:
                    _ = execute_query(supabase.table(sizes_table).insert(row_data), ttl=0)
                except Exception as e:
                    st.error(f"Error inserting into '{sizes_table}' for model '{model}': {e}")
