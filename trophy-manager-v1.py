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
            print(f"New Main Section Identified: {current_main_section}")

        elif current_main_section:
            # Identify sizes
            if row[0] == 'Size':
                print(f"Size row detected in section {current_main_section}: {row[3:].tolist()}")
                current_size_info = [(size.strip(), chr(65 + i)) for i, size in enumerate(row[3:]) if pd.notna(size)]
                sections[current_main_section]['sizes'] = current_size_info
                print(f"Sizes identified: {current_size_info}")
            
            # Identify selling prices
            elif row[0] == 'Selling price':
                current_price_info = [x for x in row[3:].tolist() if pd.notna(x)]
                sections[current_main_section]['prices'] = current_price_info
                print(f"Prices identified: {current_price_info}")
            
            # Identify subsections
            elif isinstance(row[0], str) and pd.isna(row[1]):
                current_subsection = row[0]
                sections[current_main_section]['subsections'][current_subsection] = []
                print(f"Subsection Identified: {current_subsection} under {current_main_section}")
            
            # Identify products
            elif isinstance(row[0], str) and isinstance(row[1], str) and isinstance(row[2], str):
                product_name = row[0]
                product_code = row[1].strip()
                product_model = row[2].strip() if pd.notna(row[2]) else ""

                # Debugging output to check extracted values
                print(f"Product Name: {product_name}, Product Code: {product_code}, Product Model: {product_model}")

                # Check if the code should be appended to the product name
                if product_code.lower() in ["colour", "gold", "silver", "bronze"]:
                    full_product_name = f"{current_main_section} {current_subsection} {product_name} {product_code.lower()}"
                    combined_model = product_model
                    print(f"Matched special code. Full Product Name: {full_product_name}, Model: {combined_model}")
                else:
                    full_product_name = f"{current_main_section} {current_subsection} {product_name}"
                    combined_model = f"{product_code} {product_model}".strip()
                    print(f"Standard processing. Full Product Name: {full_product_name}, Combined Code & Model: {combined_model}")

                # Ensure the "Code & Model" key is always created
                product_entry = {
                    "Product Name": full_product_name,
                    "Code & Model": combined_model
                }

                # Assign size-specific codes only if sizes are available
                if current_size_info:
                    product_entry["Sizes"] = {}
                    for size, letter in current_size_info:
                        product_entry["Sizes"][size] = f"{combined_model} {letter}"
                    print(f"Product sizes and codes assigned: {product_entry['Sizes']}")
                else:
                    print(f"No sizes available for {full_product_name}")

                # Debugging output to check the final product entry
                print(f"Final Product Entry: {product_entry}")

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
                        results.append(product)
                
                # If search contains multiple words
                else:
                    # Check if all search terms are in the product name words
                    if all(term in product_name_words for term in search_terms):
                        results.append(product)
    
    return results

# In the output/display part, show sizes and their relevant codes only if they exist
def display_search_results(results):
    for result in results:
        st.write(f"**Product Name:** {result['Product Name']}")
        st.write(f"**Code & Model:** {result['Code & Model']}")
        sizes = result.get("Sizes")  # Safely get the "Sizes" dictionary, it will be None if not present
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
    # Show All Products button
    if st.button("Show All Products"):
        st.write("All Sections and Subsections:")
        sections_to_delete = []
        for main_section in sections_info.keys():
            st.write(f"**{main_section}**")
            for subsection in sections_info[main_section]['subsections'].keys():
                st.write(f"- {subsection}")
            if st.button(f"Delete section '{main_section}'", key=main_section):
                sections_to_delete.append(main_section)

        # If any sections are marked for deletion, remove them and update the saved file
        if sections_to_delete:
            for section in sections_to_delete:
                del sections_info[section]
            save_sections_info(sections_info, local_data_file)
            st.write("Selected sections have been deleted and data saved locally.")

    # Option to upload a new CSV file and overwrite existing data
    if st.button("Upload a new CSV"):
        uploaded_file = st.file_uploader("Upload a new CSV file to overwrite existing data", type="csv")
        if uploaded_file is not None:
            # Read the new CSV file
            data = pd.read_csv(uploaded_file, header=None)

            # Identify sections, subsections, and products
            sections_info = identify_sections_with_products(data)

            # Save the new processed data, overwriting the old data
            save_sections_info(sections_info, local_data_file)
            st.write("New data processed and saved locally.")

    # Option to download the current stored data
    if st.button("Download stored data"):
        # Convert stored sections info to a DataFrame
        flattened_data = []
        for main_section, content in sections_info.items():
            for subsection, products in content['subsections'].items():
                for product in products:
                    flattened_data.append({
                        "Main Section": main_section,
                        "Subsection": subsection,
                        "Product Name": product["Product Name"],
                        "Code & Model": product.get("Code & Model", "N/A")  # Use "N/A" if the key is missing
                    })
                    sizes = product.get("Sizes")
                    if sizes:  # Only add sizes if they exist
                        for size, code in sizes.items():
                            flattened_data.append({
                                "Size": size,
                                "Size Code": code
                            })
        df = pd.DataFrame(flattened_data)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download data as CSV",
            data=csv,
            file_name='stored_data.csv',
            mime='text/csv',
        )
        

    # Search functionality
    search_term = st.text_input("Enter the name, code, or model of the trophy or medal to search:")

    if search_term:
        search_results = search_products(sections_info, search_term)
        
        if search_results:
            st.write(f"Search results for '{search_term}':")
            display_search_results(search_results)
        else:
            st.write(f"No results found for '{search_term}'.")
