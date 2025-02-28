import os
import streamlit as st
import pandas as pd
from scraping import scrape_product_range
from backend import (
    insert_products_to_supabase,
    upload_images_to_supabase,
    insert_sizes_and_update_sizes_table,
)

# Define the materials dictionary
materials_dict = {
    'trophies': ['acrylic', 'wood', 'glass', 'metal', 'test'],
    'medals': ['acrylic', 'wood', 'metal'],
    'test': ['test']
}

def format_product_type(product_type):
    return product_type.replace("_", " ").title()

st.title("Upload New Products")

# Reset button: clears all session state and cached data.
if st.button("Reset Upload"):
    st.session_state.clear()
    st.cache_data.clear()
    st.rerun()
    
# Use a session state variable to control workflow.
if "current_step" not in st.session_state:
    st.session_state.current_step = "input"  # Options: "input", "preview", "final"

# STEP 1: Initial Input Form
if st.session_state.current_step == "input":
    with st.form("upload_form"):
        st.text_input("Enter the Bauer URL (from https://www.pohary-bauer.cz/):", key="url_input")
        st.text_input("Enter the Range Name:", key="range_name_input")
        st.text_input("Enter the Range Code:", key="range_code_input")
        
        selected_category = st.selectbox(
            "Select Product Category:",
            list(materials_dict.keys()),
            key="product_category_input"
        )
        options = materials_dict[selected_category]
        current_material = st.session_state.get("product_material_input", options[0])
        if current_material not in options:
            current_material = options[0]
        selected_index = options.index(current_material)
        st.selectbox(
            "Select Material:",
            options,
            key="product_material_input",
            index=selected_index
        )
        
        st.text_input("Enter Sizes (in descending order, separated by spaces e.g. 80 70 60):", key="sizes_input")
        
        if st.form_submit_button("Submit"):
            st.session_state.final_sizes = st.session_state.sizes_input
            st.session_state.current_step = "preview"
            st.rerun()

# STEP 2: Preview and Edit Products
if st.session_state.current_step == "preview":
    # If scraping hasn't been done yet, perform it.
    if "df" not in st.session_state:
        url = st.session_state.url_input
        range_name = st.session_state.range_name_input
        range_code = st.session_state.range_code_input
        product_category = st.session_state.product_category_input
        product_material = st.session_state.product_material_input
        sizes_list = st.session_state.final_sizes.split() if st.session_state.final_sizes else []
        
        # st.write("User Inputs:")
        # st.write({
        #     "url": url,
        #     "range_name": range_name,
        #     "range_code": range_code,
        #     "product_category": product_category,
        #     "product_material": product_material,
        #     "sizes": sizes_list,
        # })
        
        st.write("Scraping products from the provided URL. Please wait...")
        # Create a progress bar for scraping products.
        progress_bar = st.progress(0)
        df, temp_dir = scrape_product_range(url, range_name, range_code, product_category, product_material, progress_bar)
        st.session_state.df = df
        st.session_state.temp_dir = temp_dir

    st.write("Scraped Product Data:")
    st.dataframe(st.session_state.df)
    
    with st.form("preview_form"):
        for idx, row in st.session_state.df.iterrows():
            st.markdown("---")
            st.write(f"**Model:** {row['model']}")
            st.write(f"**Name:** {row['name']}")
            st.write(f"**Product Code:** {row['product_code']}")
            st.write(f"**Type:** {row['type']}")
            
            # Editable sport field.
            key = f"edit_sport_{idx}"
            default_sport = st.session_state.get(key, row['sport'])
            st.text_input("Sport:", value=default_sport, key=key)
            
            if row['temp_image_path'] and os.path.exists(row['temp_image_path']):
                st.image(row['temp_image_path'], caption=row['model'], width=150)
            else:
                st.write("No image available.")
        
        if st.form_submit_button("Proceed to Final Confirmation"):
            # Update the dataframe with the edited sports.
            updated_rows = []
            for idx, row in st.session_state.df.iterrows():
                key = f"edit_sport_{idx}"
                new_sport = st.session_state.get(key, row['sport'])
                row['sport'] = new_sport
                updated_rows.append(row)
            st.session_state.df = pd.DataFrame(updated_rows)
            st.session_state.current_step = "final"
            st.rerun()

# STEP 3: Final Confirmation & Combined Backend Upload with Progress
if st.session_state.current_step == "final":
    st.write("Final product data ready for upload:")
    updated_products = []
    for idx, row in st.session_state.df.iterrows():
        key = f"edit_sport_{idx}"
        new_sport = st.session_state.get(key, row['sport'])
        updated_products.append({
            "model": row['model'],
            "name": row['name'],
            "sport": new_sport,
            "product_code": row['product_code'],
            "raw_type": row['type'],  # For insertion into Supabase
            "formatted_type": format_product_type(row['type']),  # For display
            "image_url": row['image_url'],
            "temp_image_path": row['temp_image_path'],
        })
    st.session_state.updated_products = updated_products
    # st.write(updated_products)
    
    # Combined backend step with progress and status text.
    if st.button("Upload to Supabase"):
        backend_progress = st.progress(0)
        st.write("Uploading product details...")
        insert_products_to_supabase(updated_products)
        backend_progress.progress(0.33)
        
        st.write("Uploading product images...")
        upload_images_to_supabase(updated_products)
        backend_progress.progress(0.66)
        
        st.write("Uploading sizes...")
        sizes_str = st.session_state.get("final_sizes", "")
        sizes_list = sizes_str.split() if sizes_str else []
        insert_sizes_and_update_sizes_table(updated_products, sizes_list)
        backend_progress.progress(1.0)
        
        st.success("All backend steps completed!")
    
    if st.button("Start Over"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
