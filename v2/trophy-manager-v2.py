import streamlit as st
import pandas as pd
import os
import csv
import io

# Title of the app
st.title("Trophy Manager v2")

# Define file paths for saving the DataFrame
local_data_file = "sections_info.pkl"

def process_csv(uploaded_file):
    sections = {}
    
    # Decode the uploaded file content to a string
    content = uploaded_file.getvalue().decode("utf-8")
    
    # Use io.StringIO to treat the string content as a file
    csv_reader = csv.reader(io.StringIO(content))
    
    # Extract model name from the first row
    model_name = next(csv_reader)[0].strip()
    
    # Extract sizes from the second row
    size_row = next(csv_reader)[1:]  # Skip the first cell, take the rest as sizes
    sizes = [(size.strip(), chr(65 + i)) for i, size in enumerate(size_row) if size.strip()]

    products = []

    # Iterate over the product rows
    for row in csv_reader:
        if len(row) < 2 or not row[0].strip():  # Skip empty or malformed rows
            continue

        product_name = row[0].strip()
        code_model = row[1].strip() if len(row) > 1 else ""

        # Split the code_model into product_code and product_model based on the last space
        if " " in code_model:
            product_code, product_model = code_model.rsplit(" ", 1)
        else:
            product_code = code_model
            product_model = ""

        # Check if the first cell contains a special category (Gold, Silver, Colour, Bronze)
        if product_code.lower() in ["colour", "gold", "silver", "bronze"]:
            full_product_name = f"{model_name} {product_name} {product_code.lower()}"
            combined_model = product_model
        else:
            full_product_name = f"{model_name} {product_name}"
            combined_model = f"{product_code} {product_model}".strip()

        # Adjust to ensure the correct CZ Code is stored
        cz_code = product_code

        product_entry = {
            "Product Name": full_product_name,
            "Code & Model": combined_model,
            "CZ Code": cz_code  # Ensure CZ Code is stored separately
        }

        if sizes:
            product_entry["Sizes"] = {}
            for size, letter in sizes:
                product_entry["Sizes"][size] = f"{combined_model} {letter}"

        products.append(product_entry)

    sections[model_name] = {
        "subsections": {
            "MAIN": products
        },
        "sizes": sizes
    }

    return sections

def save_sections_info(sections_info, file_path):
    pd.to_pickle(sections_info, file_path)

def load_sections_info(file_path):
    return pd.read_pickle(file_path)

def search_products_by_name(sections, search_query):
    results = []
    search_terms = search_query.lower().split()

    for main_section, content in sections.items():
        for subsection, products in content['subsections'].items():
            for product in products:
                product_name_words = product["Product Name"].lower().split()

                # Check if the search contains only one word
                if len(search_terms) == 1:
                    if search_terms[0] in product_name_words:
                        results.append(product)

                # If search contains multiple words
                else:
                    # Check if all search terms are in the product name words
                    if all(term in product_name_words for term in search_terms):
                        results.append(product)

    return results

def search_products_by_cz_code(sections, cz_code):
    results = []

    for main_section, content in sections.items():
        for subsection, products in content['subsections'].items():
            for product in products:
                # Search by checking if the cz_code exists in the full combined_model string
                if cz_code.lower() in product["Code & Model"].lower():
                    results.append(product)
    
    return results

def display_search_results(results):
    for result in results:
        st.write(f"**Product Name:** {result['Product Name']}")
        st.write(f"**Code & Model:** {result['Code & Model']}")
        sizes = result.get("Sizes")
        if sizes:
            for size, code in sizes.items():
                st.write(f"Size: {size}, Code: {code}")
        st.write("---")

# Check if the local data file exists
if os.path.exists(local_data_file):
    # Load the DataFrame from the local file
    sections_info = load_sections_info(local_data_file)
    st.write("Loaded data from local file.")
else:
    sections_info = {}

# Ask the user to upload one or more CSV files
uploaded_files = st.file_uploader("Choose CSV files", type="csv", accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        # Process the CSV to extract model and products
        new_sections = process_csv(uploaded_file)

        # Merge the new sections into the existing sections_info
        sections_info.update(new_sections)

    # Save the processed data for future use
    save_sections_info(sections_info, local_data_file)
    st.write("Data processed and saved locally.")

# Search options
search_option = st.selectbox("Select search option", ["UK Name", "UK Model", "CZ Code"])

if search_option == "UK Name":
    search_term = st.text_input("Enter the UK name of the trophy or medal to search:")
    if search_term:
        search_results = search_products_by_name(sections_info, search_term)
        if search_results:
            st.write(f"Search results for '{search_term}':")
            display_search_results(search_results)
        else:
            st.write(f"No results found for '{search_term}'.")

elif search_option == "UK Model":
    models = sorted([model for model in sections_info.keys()])  # Sort models alphabetically
    selected_model = st.selectbox("Select a UK model", models)
    if selected_model:
        st.write(f"Displaying all products for model: {selected_model}")
        display_search_results(sections_info[selected_model]['subsections']['MAIN'])

elif search_option == "CZ Code":
    cz_code = st.text_input("Enter the CZ code to search:")
    if cz_code:
        search_results = search_products_by_cz_code(sections_info, cz_code)
        if search_results:
            st.write(f"Search results for CZ code '{cz_code}':")
            display_search_results(search_results)
        else:
            st.write(f"No results found for CZ code '{cz_code}'.")
