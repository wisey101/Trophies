# trophy-manager-v1.py

import streamlit as st
import pandas as pd
import os

# Title of the app
st.title("Trophy Manager v1")

# Define file paths for saving the DataFrame
local_data_file = "sections_info.pkl"

def identify_sections_with_products(data):
    sections = {}
    current_main_section = None
    current_subsection = None
    current_size_info = []
    current_price_info = []

    for i, row in data.iterrows():
        # Identify main sections
        if isinstance(row[0], str) and row[3] == 'A':
            current_main_section = row[0]
            sections[current_main_section] = {"subsections": {}, "sizes": [], "prices": []}
            current_subsection = "MAIN"  # Default subsection
            sections[current_main_section]['subsections'][current_subsection] = []
        
        elif current_main_section:
            # Identify sizes
            if row[0] == 'Size':
                current_size_info = [x for x in row[3:].tolist() if pd.notna(x)]
                sections[current_main_section]['sizes'] = current_size_info
            
            # Identify selling prices
            elif row[0] == 'Selling price':
                current_price_info = [x for x in row[3:].tolist() if pd.notna(x)]
                sections[current_main_section]['prices'] = current_price_info
            
            # Identify subsections
            elif isinstance(row[0], str) and pd.isna(row[1]):
                current_subsection = row[0]
                sections[current_main_section]['subsections'][current_subsection] = []
            
            # Identify products
            elif isinstance(row[0], str) and isinstance(row[1], str) and isinstance(row[2], str):
                product_name = row[0]
                product_code = row[1]
                product_model = row[2]
                full_product_name = f"{current_main_section} {current_subsection} {product_name}"
                product_entry = {
                    "Product Name": full_product_name,
                    "Code": product_code,
                    "Model": product_model
                }
                for size, price in zip(current_size_info, current_price_info):
                    product_entry[f"Size_{size}"] = price
                
                sections[current_main_section]['subsections'][current_subsection].append(product_entry)

    return sections

def save_sections_info(sections_info, file_path):
    pd.to_pickle(sections_info, file_path)

def load_sections_info(file_path):
    return pd.read_pickle(file_path)

def search_products(sections, search_query):
    results = []
    search_terms = search_query.lower().split()
    
    for main_section, content in sections.items():
        for subsection, products in content['subsections'].items():
            for product in products:
                product_name_words = product["Product Name"].lower().split()
                
                # Check if the search contains only one word
                if len(search_terms) == 1:
                    if search_terms[0] in product_name_words:
                        result_entry = {
                            "Main Section": main_section,
                            "Subsection": subsection,
                            "Product Name": product["Product Name"],
                            "Code": product["Code"],
                            "Model": product["Model"]
                        }
                        results.append(result_entry)
                else:
                    # Count how many search terms match product name words
                    match_count = sum(1 for term in search_terms if term in product_name_words)
                    if match_count >= 2:
                        result_entry = {
                            "Main Section": main_section,
                            "Subsection": subsection,
                            "Product Name": product["Product Name"],
                            "Code": product["Code"],
                            "Model": product["Model"]
                        }
                        results.append(result_entry)
    
    return results

# Check if the local data file exists
if os.path.exists(local_data_file):
    # Load the DataFrame from the local file
    sections_info = load_sections_info(local_data_file)
    st.write("Loaded data from local file.")
else:
    # Ask the user to upload a file if local data is not available
    st.write("Upload your CSV file to identify sections, subsections, and product details.")

    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        # Read the uploaded CSV file
        data = pd.read_csv(uploaded_file, header=None)

        # Identify sections, subsections, and products
        sections_info = identify_sections_with_products(data)

        # Save the processed data for future use
        save_sections_info(sections_info, local_data_file)
        st.write("Data processed and saved locally.")

# Display the identified sections with their details
if 'sections_info' in locals():

    # Search functionality
    search_term = st.text_input("Enter the name, code, or model of the trophy or medal to search:")

    if search_term:
        search_results = search_products(sections_info, search_term)
        
        if search_results:
            st.write(f"Search results for '{search_term}':")
            st.write(pd.DataFrame(search_results))
        else:
            st.write(f"No results found for '{search_term}'.")
