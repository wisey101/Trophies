import streamlit as st
from st_supabase_connection import SupabaseConnection, execute_query
import pandas as pd

# Initialize connection and grab URL from secrets
supabase = st.connection("supabase", type=SupabaseConnection)
supabase_url = st.secrets["connections"]["supabase"]["SUPABASE_URL"]

st.title("Trophy Monster Product Manager")

# Initialize the order in session state
if 'order' not in st.session_state:
    st.session_state['order'] = {}

# Function to add items to the order
def add_to_order(product_code, quantity, notes=""):
    if product_code in st.session_state['order']:
        st.session_state['order'][product_code]['quantity'] += quantity
        st.session_state['order'][product_code]['notes'] = notes
    else:
        st.session_state['order'][product_code] = {"quantity": quantity, "notes": notes}

# Placeholder for order operations
placeholder = st.empty()

# Function to generate the live order table within the placeholder
def display_order_table():
    # Check if the order is not empty
    if st.session_state.get('order', {}):
        # Prepare data for the table
        order_data = {
            "Product": [],
            "Description": [],
            "Quantity": []
        }

        # Populate the table data from the order
        for product_code, details in st.session_state['order'].items():
            order_data["Product"].append(product_code)
            order_data["Description"].append(details.get("notes", ""))
            order_data["Quantity"].append(details.get("quantity", 0))

        # Convert to a DataFrame for displaying
        df = pd.DataFrame(order_data)

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
                del st.session_state['order'][product_code_to_delete]

            st.success("Selected items deleted from order.")
            st.session_state['refresh'] = not st.session_state.get('refresh', False)
            st.rerun()

    else:
        st.write("Your order is empty.")
        # Add a "Refresh" button under the table
        if st.button("Refresh"):
            st.session_state['refresh'] = not st.session_state.get('refresh', False)

@st.cache_data(ttl=1200)
# Load data from Supabase and return a combined DataFrame.
def load_data(materials_dict):
    final_data = []

    # Process data for a single material and category, and append to final_data.
    def process_material_data(category, material):
        table = f'{category}_{material}'
        size_table = f'{table}_sizes'

        response = execute_query(supabase.table(table).select("*"), ttl=0)
        size_response = execute_query(supabase.table(size_table).select("*"), ttl=0)

        base_url = f"{supabase_url}/storage/v1/object/public/{table}/"
        
        if hasattr(response, 'data'):
            data = response.data
            size_data = size_response.data

            if data:
                if size_data:    
                    prod_df = pd.DataFrame(data)
                    sizes_df = pd.DataFrame(size_data)
                    ungrouped_df = pd.merge(prod_df, sizes_df, on='model', how='left')
                    grouped = ungrouped_df.groupby('model').agg({
                        'size': lambda x: list(x.dropna()),
                        'size_code': lambda x: list(x.dropna())
                    })
                    df = pd.merge(prod_df, grouped, on='model', how='left')

                    for _, row in df.iterrows():
                        if row['name']: 
                            product_name = f"{row['name']} {row['sport']} {row['type']}"
                            model_code = row['model']
                            model_code_clean = model_code.replace(" ", "_")
                            image_url = f"{base_url}/{model_code_clean}.jpg"
                            
                            final_data.append({
                                'product name': product_name, 
                                'code': model_code, 
                                'image url': image_url,
                                'sizes': row['size'],
                                'size_codes': row['size_code']
                                })
            else:
                st.write("No data found")
        else:
            st.write("Invalid response structure")
    
    for category, materials in materials_dict.items():
        for material in materials:
            process_material_data(category, material)
    
    return pd.DataFrame(final_data)

# Search for products by name or code.
def search_products(df, search_query):
    if search_query:
        # Split the search query into individual terms
        search_terms = search_query.split()

        # Check if all search terms are present in either 'product name' or 'code'
        filtered_df = df[
            df['product name'].apply(lambda name: all(term.lower() in name.lower() for term in search_terms)) |
            df['code'].apply(lambda code: all(term.lower() in code.lower() for term in search_terms))
        ]
        return filtered_df
    return df

    
# Main function to load data and handle search functionality.
def main():
    materials_dict = {
        'trophies': ['acrylic', 'wood'],
        'medals': ['acrylic', 'wood', 'metal']
    }
    
    final_df = load_data(materials_dict)
    display_order_table()
    search_query = st.text_input("Search for a product by name or code:")
    
    if search_query:
        result_df = search_products(final_df, search_query)
        
        if not result_df.empty:
            for idx, row in result_df.iterrows():
                with st.container():
                    st.write("---")
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.write(f"**Product Name**: {row['product name']}")
                        st.write(f"**Product Code**: {row['code']}")
                        sizes_display = ", ".join([f"{size}mm" for size in row['sizes']])
                        st.write(f"**Available Sizes**: {sizes_display}")
                    
                    with col2:
                        with st.popover(f"Add to Order - {row['product name']}"):
                            # Size selection dropdown
                            size_selected = st.selectbox(
                                f"Select Size for {row['product name']}",
                                options=[f"{size}mm" for size in row['sizes']], 
                                key=f"size_{row['product name']}_{idx}"
                            )

                            # Map the selected size back to the corresponding size_code
                            size_index = [f"{size}mm" for size in row['sizes']].index(size_selected)
                            size_code = row['size_codes'][size_index]  # Get the corresponding size_code

                            # Quantity input
                            quantity = st.number_input(f"Quantity for {row['product name']}", min_value=1, value=1, key=f"qty_{row['product name']}_{idx}")
                            
                            # Text input for notes
                            notes = st.text_input(f"Notes for {row['product name']}", key=f"notes_{row['product name']}_{idx}")
                            
                            # Confirmation button to add to cart
                            if st.button("Confirm Add to Order", key=f"confirm_{row['product name']}_{idx}"):
                                add_to_order(size_code, quantity, notes)  # Add size_code to the order instead of regular code
                                st.rerun()
                    
                    # Display the image below the text and button
                    st.image(row['image url'], width=175)
                    
        else:
            st.write("No products found.")
    else:
        st.write("Please enter a search term.")

# Run the main function
if __name__ == "__main__":
    main()