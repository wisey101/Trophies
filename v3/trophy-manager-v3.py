import streamlit as st
import pandas as pd
import os
import csv
import io

# Title of the app
st.title("Trophy Monster Product Manager")

# Define file paths for saving the DataFrame
local_data_file = "sections_info.pkl"

# Initialize the cart in session state
if 'cart' not in st.session_state:
    st.session_state['cart'] = {}

# Function to add items to the cart
def add_to_cart(product_code, quantity, notes=""):
    # Check if the product is already in the cart
    if product_code in st.session_state['cart']:
        # If it is, increase the quantity
        st.session_state['cart'][product_code]['quantity'] += quantity
        st.session_state['cart'][product_code]['notes'] = notes  # Update notes as well
    else:
        # If it's not, add it to the cart with the specified quantity and notes
        st.session_state['cart'][product_code] = {"quantity": quantity, "notes": notes}

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
                product_entry["Sizes"][size] = f"{combined_model}{letter}"

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

def unified_search(sections, search_query):
    results = []
    search_terms = search_query.lower().split()

    for main_section, content in sections.items():
        for subsection, products in content['subsections'].items():
            for product in products:
                product_name_words = product["Product Name"].lower().split()
                model_words = product["Code & Model"].lower().split()

                # Single word search (similar to CZ Code search)
                if len(search_terms) == 1:
                    if any(search_terms[0] in word for word in product_name_words + model_words):
                        results.append(product)

                # Multi-word search (similar to UK Name search)
                else:
                    if all(term in product_name_words for term in search_terms):
                        results.append(product)

    return results

def display_search_results(results):
    for idx, result in enumerate(results):
        st.write(f"**Product Name:** {result['Product Name']}")
        st.write(f"**Code & Model:** {result['Code & Model']}")
        sizes = result.get("Sizes")
        
        
        # Popover for Add to Cart
        with st.popover(f"Add to Order - {result['Product Name']}"):
            if sizes:
                # Create a dropdown for selecting size
                selected_size = st.selectbox("Select Size", options=[size for size, code_letter in sizes.items()], key=f"size_{result['Product Name']}_{idx}")
                
                # Create a number input for selecting quantity
                quantity = st.number_input(f"Quantity for {result['Product Name']}", min_value=1, value=1, key=f"qty_{result['Product Name']}_{selected_size}_{idx}")
                
                # Text input for notes
                notes = st.text_input(f"Notes for {result['Product Name']}", key=f"notes_{result['Product Name']}_{idx}")
                
                # Get the letter code for the selected size
                final_code = sizes[selected_size]
                
                # Confirmation button to add to cart
                if st.button("Confirm Add to Order", key=f"confirm_{result['Product Name']}_{selected_size}_{idx}"):
                    add_to_cart(final_code, quantity, notes)
                    st.rerun()
        
        st.write("---")

placeholder = st.empty()

# Function to generate the live cart table within the placeholder
def display_cart_table():
    # Check if the cart is not empty
    if st.session_state.get('cart', {}):
        # Prepare data for the table
        cart_data = {
            "Product": [],
            "Description": [],
            "Quantity": []
        }

        # Populate the table data from the cart
        for product_code, details in st.session_state['cart'].items():
            cart_data["Product"].append(product_code)
            cart_data["Description"].append(details.get("notes", ""))
            cart_data["Quantity"].append(details.get("quantity", 0))

        # Convert to a DataFrame for displaying
        df = pd.DataFrame(cart_data)

        
        # Display the table with checkbox selection using the event-based API
        event = st.dataframe(
            df,
            key="data",
            on_select="rerun",
            selection_mode=["multi-row"],
            hide_index="true",
            use_container_width=True
        )

        # Create a horizontal layout for buttons
        delete_button_clicked = st.button("Delete selected items", key="delete_button")

        # Handle button actions
        if delete_button_clicked and event and 'rows' in event.selection:
            selected_indices = event.selection['rows']
            for index in selected_indices:
                product_code_to_delete = df.iloc[index]['Product']
                del st.session_state['cart'][product_code_to_delete]

            st.success("Selected items deleted from cart.")
            st.session_state['refresh'] = not st.session_state.get('refresh', False)
            st.rerun()

    else:
        st.write("Your order is empty.")
        # Add a "Refresh" button under the table
        if st.button("Refresh"):
            st.session_state['refresh'] = not st.session_state.get('refresh', False)
            

# Initial display of the cart table
display_cart_table()



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

# Single search input for both name and code/model
search_term = st.text_input("Enter the name or code of the product to search:")

if search_term:
    search_results = unified_search(sections_info, search_term)
    if search_results:
        st.write(f"Search results for '{search_term}':")
        display_search_results(search_results)
    else:
        st.write(f"No results found for '{search_term}'.")
